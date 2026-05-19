from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

from outlook_dashboard.auth import (
    _decode_session,
    admin_setup_available,
    admin_user_exists,
    authenticate_user,
    create_session,
    create_first_admin,
    create_reset_token,
    encode_session,
    ensure_admin,
    get_session_user,
)
from outlook_dashboard.database import initialize_database, managed_connect

SUPABASE_URL = "https://example.supabase.co"
USER_ID = "6f70cf38-5321-4c3e-9b28-20d7b0972f60"


class FakeResponse:
    def __init__(self, payload: dict | None = None):
        self.payload = payload or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def close(self) -> None:
        return None


def _http_error(url: str, status: int = 401) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, status, "error", {}, BytesIO(b'{"error":"mock"}'))


def _request_body(request) -> dict:
    data = getattr(request, "data", None)
    return json.loads(data.decode("utf-8")) if data else {}


def _set_supabase_env(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_KEY", "anon-test-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")


def test_authenticate_user_success(monkeypatch) -> None:
    _set_supabase_env(monkeypatch)

    def fake_urlopen(request, timeout=15):
        assert request.full_url == f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
        assert _request_body(request)["email"] == "agent@example.com"
        return FakeResponse(
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "user": {"id": USER_ID, "email": "agent@example.com", "app_metadata": {"role": "admin"}},
            }
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        user = authenticate_user("Agent@Example.com", "secret")

    assert user is not None
    assert user["id"] == USER_ID
    assert user["role"] == "admin"
    assert user["_access_token"] == "access-token"
    assert user["_refresh_token"] == "refresh-token"


def test_authenticate_user_failure_returns_none(monkeypatch) -> None:
    _set_supabase_env(monkeypatch)

    with patch(
        "urllib.request.urlopen",
        side_effect=lambda request, timeout=15: (_ for _ in ()).throw(_http_error(request.full_url)),
    ):
        assert authenticate_user("agent@example.com", "wrong") is None


def test_get_session_user_refreshes_expired_token(monkeypatch) -> None:
    _set_supabase_env(monkeypatch)
    calls: list[str] = []

    def fake_urlopen(request, timeout=15):
        calls.append(request.full_url)
        if request.full_url.endswith("/auth/v1/user"):
            raise _http_error(request.full_url)
        assert request.full_url.endswith("/auth/v1/token?grant_type=refresh_token")
        assert _request_body(request)["refresh_token"] == "old-refresh"
        return FakeResponse(
            {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "user": {"id": USER_ID, "email": "agent@example.com", "app_metadata": {"role": "user"}},
            }
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        user = get_session_user(encode_session("expired-access", "old-refresh"))

    assert user is not None
    assert user["_new_access_token"] == "new-access"
    assert user["_new_refresh_token"] == "new-refresh"
    assert calls == [
        f"{SUPABASE_URL}/auth/v1/user",
        f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
    ]


def test_encode_decode_session_round_trip() -> None:
    cookie = encode_session("access", "refresh")
    assert _decode_session(cookie) == ("access", "refresh")
    assert _decode_session("broken") is None


def test_ensure_admin_create_and_update_paths(monkeypatch) -> None:
    _set_supabase_env(monkeypatch)
    calls: list[tuple[str, str, dict]] = []

    def fake_urlopen(request, timeout=15):
        body = _request_body(request)
        calls.append((request.get_method(), request.full_url, body))
        if request.full_url.endswith("/auth/v1/admin/users?per_page=1000") and len(calls) == 1:
            return FakeResponse({"users": []})
        if request.full_url.endswith("/auth/v1/admin/users") and request.get_method() == "POST":
            assert body["email"] == "admin@example.com"
            assert body["app_metadata"]["role"] == "admin"
            return FakeResponse({"id": USER_ID})
        if request.full_url.endswith("/auth/v1/admin/users?per_page=1000"):
            return FakeResponse(
                {"users": [{"id": USER_ID, "email": "admin@example.com", "app_metadata": {"role": "user"}}]}
            )
        if request.full_url.endswith(f"/auth/v1/admin/users/{USER_ID}") and request.get_method() == "PUT":
            assert body["password"] == "NewPassword123!"
            assert body["app_metadata"]["role"] == "admin"
            return FakeResponse({})
        raise AssertionError(f"unexpected request {request.get_method()} {request.full_url}")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        ensure_admin("admin@example.com", "FirstPassword123!")
        ensure_admin("admin@example.com", "NewPassword123!")

    methods = [method for method, _, _ in calls]
    assert methods == ["GET", "POST", "GET", "PUT"]


def test_admin_setup_available_requires_supabase_service_role(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", SUPABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")
    assert admin_setup_available() is True

    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", " ")
    assert admin_setup_available() is False


def test_admin_user_exists_detects_admin_role(monkeypatch) -> None:
    _set_supabase_env(monkeypatch)

    def fake_urlopen(request, timeout=15):
        assert request.full_url.endswith("/auth/v1/admin/users?per_page=1000")
        return FakeResponse(
            {
                "users": [
                    {"id": "user-id", "email": "user@example.com", "app_metadata": {"role": "user"}},
                    {"id": USER_ID, "email": "admin@example.com", "app_metadata": {"role": "admin"}},
                ]
            }
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert admin_user_exists() is True


def test_create_first_admin_refuses_when_admin_exists(monkeypatch) -> None:
    _set_supabase_env(monkeypatch)

    def fake_urlopen(request, timeout=15):
        assert request.full_url.endswith("/auth/v1/admin/users?per_page=1000")
        return FakeResponse({"users": [{"id": USER_ID, "email": "admin@example.com", "app_metadata": {"role": "admin"}}]})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        try:
            create_first_admin("new@example.com", "StrongPass123!")
        except RuntimeError as exc:
            assert "already exists" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected RuntimeError")


def test_create_reset_token_stores_supabase_uuid(tmp_path, monkeypatch) -> None:
    _set_supabase_env(monkeypatch)
    db_path = tmp_path / "auth.sqlite3"
    initialize_database(db_path)

    def fake_urlopen(request, timeout=15):
        assert request.full_url.endswith("/auth/v1/admin/users?per_page=1000")
        return FakeResponse(
            {"users": [{"id": USER_ID, "email": "guest@example.com", "app_metadata": {"role": "user"}}]}
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        token = create_reset_token("guest@example.com", db_path=db_path)

    assert token
    with managed_connect(db_path) as db:
        row = db.execute("SELECT user_id FROM password_reset_tokens WHERE token = ?", (token,)).fetchone()
    assert row is not None
    assert row["user_id"] == USER_ID


def test_local_sqlite_auth_fallback_when_supabase_unconfigured(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    db_path = tmp_path / "local-auth.sqlite3"
    initialize_database(db_path)

    ensure_admin("Admin@Example.com", "LocalPassword123!", db_path=db_path)
    user = authenticate_user("admin@example.com", "LocalPassword123!", db_path=db_path)

    assert user is not None
    assert user["email"] == "admin@example.com"
    assert user["role"] == "admin"
    assert "_access_token" not in user
    session_id = create_session(str(user["id"]), db_path=db_path)
    session_user = get_session_user(session_id, db_path=db_path)
    assert session_user is not None
    assert session_user["email"] == "admin@example.com"


def test_local_reset_token_fallback_when_supabase_unconfigured(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    db_path = tmp_path / "local-reset.sqlite3"
    initialize_database(db_path)
    ensure_admin("admin@example.com", "LocalPassword123!", db_path=db_path)

    token = create_reset_token("admin@example.com", db_path=db_path)

    assert token
    with managed_connect(db_path) as db:
        row = db.execute("SELECT user_id FROM password_reset_tokens WHERE token = ?", (token,)).fetchone()
    assert row is not None
    assert row["user_id"].isdigit()

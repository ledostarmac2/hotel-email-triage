from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── shared test-client factories ─────────────────────────────────────────────


@contextmanager
def _configured_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    admin_exists: bool,
    needs_creds: bool = False,
) -> Iterator[TestClient]:
    """TestClient with Supabase env vars and lifecycle helpers patched."""
    db_path = tmp_path / "setup-test.sqlite3"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "500")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "anon-test-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")

    import outlook_dashboard.main as main
    from outlook_dashboard.config import get_settings

    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()
    monkeypatch.setattr(main, "ensure_admin", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "download_approved_rules", lambda: [])
    monkeypatch.setattr(main, "download_prompt_versions", lambda: [])
    monkeypatch.setattr(main, "download_known_senders", lambda: [])
    monkeypatch.setattr(main, "flush_feedback_queue", lambda: 0)
    monkeypatch.setattr(main, "start_update_check", lambda: None)
    monkeypatch.setattr(main, "admin_setup_available", lambda: not needs_creds)
    monkeypatch.setattr(main, "needs_credentials_setup", lambda: needs_creds)
    monkeypatch.setattr(main, "admin_user_exists", lambda: admin_exists)

    with TestClient(main.app) as client:
        yield client

    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()


# ── /login routing ────────────────────────────────────────────────────────────


def test_login_redirects_to_credentials_setup_when_supabase_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/credentials-setup"


def test_login_redirects_to_setup_when_no_admin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False) as client:
        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/setup"


def test_login_post_redirects_to_credentials_setup_when_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.post(
            "/login",
            data={"email": "a@b.com", "password": "pass"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/credentials-setup"


# ── /credentials-setup GET ────────────────────────────────────────────────────


def test_credentials_setup_page_renders_when_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.get("/credentials-setup")
        assert response.status_code == 200
        assert b"supabase_service_role_key" in response.content
        assert b"supabase_url" in response.content


def test_credentials_setup_page_renders_no_prefilled_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.get("/credentials-setup")
        body = response.text
        assert "eyJhbGci" not in body
        assert "sk-ant-" not in body
        assert "sk-proj-" not in body


def test_credentials_setup_redirects_to_setup_when_already_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=False) as client:
        response = client.get("/credentials-setup", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] in ("/setup", "/login")


# ── /api/auth/credentials-setup POST ─────────────────────────────────────────


def test_api_credentials_setup_writes_env_and_returns_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        import outlook_dashboard.main as main

        written: list[dict] = []
        monkeypatch.setattr(main, "write_local_env", lambda v: written.append(v) or (tmp_path / ".env"))
        monkeypatch.setattr(main.get_settings, "cache_clear", lambda: None)

        response = client.post(
            "/api/auth/credentials-setup",
            json={
                "supabase_url": "https://abc.supabase.co",
                "supabase_key": "a" * 40,
                "supabase_service_role_key": "s" * 40,
                "anthropic_api_key": "",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["ok"] is True
        assert "SUPABASE_URL" in data["keys_written"]
        assert "SUPABASE_SERVICE_ROLE_KEY" in data["keys_written"]
        assert written, "write_local_env was not called"
        assert "ANTHROPIC_API_KEY" not in written[0]


def test_api_credentials_setup_includes_anthropic_key_when_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        import outlook_dashboard.main as main

        written: list[dict] = []
        monkeypatch.setattr(main, "write_local_env", lambda v: written.append(v) or (tmp_path / ".env"))
        monkeypatch.setattr(main.get_settings, "cache_clear", lambda: None)

        response = client.post(
            "/api/auth/credentials-setup",
            json={
                "supabase_url": "https://abc.supabase.co",
                "supabase_key": "a" * 40,
                "supabase_service_role_key": "s" * 40,
                "anthropic_api_key": "test-ai-key-value-longer-than-20",
            },
        )
        assert response.status_code == 200, response.text
        assert written and "ANTHROPIC_API_KEY" in written[0]


def test_api_credentials_setup_rejects_non_https_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.post(
            "/api/auth/credentials-setup",
            json={
                "supabase_url": "http://insecure.supabase.co",
                "supabase_key": "a" * 40,
                "supabase_service_role_key": "s" * 40,
            },
        )
        assert response.status_code == 400


def test_api_credentials_setup_rejects_short_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.post(
            "/api/auth/credentials-setup",
            json={
                "supabase_url": "https://abc.supabase.co",
                "supabase_key": "short",
                "supabase_service_role_key": "s" * 40,
            },
        )
        assert response.status_code == 400


# ── /setup after credentials are configured ──────────────────────────────────


def test_api_first_run_setup_creates_admin_and_sets_session_cookie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False) as client:
        import outlook_dashboard.main as main

        created: list[tuple[str, str]] = []
        monkeypatch.setattr(
            main,
            "create_first_admin",
            lambda email, password, db_path=None: created.append((email, password)) or "new-admin-id",
        )
        monkeypatch.setattr(
            main,
            "authenticate_user",
            lambda email, password, db_path=None: {
                "id": "new-admin-id",
                "email": email.lower(),
                "role": "admin",
                "_access_token": "setup-access",
                "_refresh_token": "setup-refresh",
            },
        )
        response = client.post(
            "/api/auth/setup",
            json={"email": "Admin@Example.com", "password": "StrongPass123!"},
        )
        assert response.status_code == 200, response.text
        assert response.json() == {"ok": True, "email": "admin@example.com", "role": "admin"}
        assert created == [("Admin@Example.com", "StrongPass123!")]
        assert "rr_session=" in response.headers.get("set-cookie", "")


def test_api_first_run_setup_refuses_when_admin_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=True) as client:
        response = client.post(
            "/api/auth/setup",
            json={"email": "admin@example.com", "password": "StrongPass123!"},
        )
        assert response.status_code == 409


def test_api_first_run_setup_requires_supabase_service_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False) as client:
        import outlook_dashboard.main as main

        monkeypatch.setattr(main, "admin_setup_available", lambda: False)
        response = client.post(
            "/api/auth/setup",
            json={"email": "admin@example.com", "password": "StrongPass123!"},
        )
        assert response.status_code == 503

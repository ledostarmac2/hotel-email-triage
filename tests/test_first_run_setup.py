from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

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
    monkeypatch.setattr(main, "admin_user_exists", lambda: admin_exists)

    with TestClient(main.app) as client:
        yield client

    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()


# ── /login routing ────────────────────────────────────────────────────────────


def test_login_does_not_offer_credentials_setup_when_supabase_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/setup"


def test_login_redirects_to_setup_when_no_admin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False) as client:
        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/setup"


def test_login_post_does_not_redirect_to_credentials_setup_when_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.post(
            "/login",
            data={"email": "a@b.com", "password": "pass"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers.get("location") == "/setup"
        assert response.headers.get("location") != "/credentials-setup"


# ── /credentials-setup retired route ──────────────────────────────────────────


def test_credentials_setup_page_redirects_to_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.get("/credentials-setup", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_api_credentials_setup_is_not_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False, needs_creds=True) as client:
        response = client.post(
            "/api/auth/credentials-setup",
            json={
                "supabase_url": "https://abc.supabase.co",
                "supabase_key": "a" * 40,
                "supabase_service_role_key": "s" * 40,
            },
        )
        assert response.status_code in (401, 404)


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


def test_api_first_run_setup_uses_local_database_when_supabase_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _configured_client(tmp_path, monkeypatch, admin_exists=False) as client:
        import outlook_dashboard.main as main
        from outlook_dashboard.config import get_settings

        monkeypatch.setenv("SUPABASE_URL", " ")
        monkeypatch.setenv("SUPABASE_KEY", " ")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", " ")
        get_settings.cache_clear()
        monkeypatch.setattr(main, "admin_setup_available", lambda: False)
        response = client.post(
            "/api/auth/setup",
            json={"email": "admin@example.com", "password": "StrongPass123!"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True, "email": "admin@example.com", "role": "admin"}
        assert "rr_session=" in response.headers.get("set-cookie", "")


def test_startup_seed_repairs_configured_admin_even_when_no_remote_admin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "startup-seed.sqlite3"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "500")
    monkeypatch.setenv("REPLYRIGHT_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("REPLYRIGHT_ADMIN_PASSWORD", "ConfiguredPassword123!")
    monkeypatch.setenv("SUPABASE_URL", " ")
    monkeypatch.setenv("SUPABASE_KEY", " ")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", " ")

    import outlook_dashboard.main as main
    from outlook_dashboard.config import get_settings

    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()
    monkeypatch.setattr(main, "download_approved_rules", lambda: [])
    monkeypatch.setattr(main, "download_prompt_versions", lambda: [])
    monkeypatch.setattr(main, "download_known_senders", lambda: [])
    monkeypatch.setattr(main, "flush_feedback_queue", lambda: 0)
    monkeypatch.setattr(main, "start_update_check", lambda: None)

    with patch("urllib.request.urlopen", side_effect=AssertionError("Supabase should not be called")):
        with TestClient(main.app) as client:
            response = client.post(
                "/login",
                data={"email": "admin@example.com", "password": "ConfiguredPassword123!"},
                follow_redirects=False,
            )

    assert response.status_code == 303
    assert "rr_session=" in response.headers.get("set-cookie", "")
    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_INTEGRATION_TEST_FILES = {
    "test_api_full_coverage.py",
    "test_api_workflow_pytest.py",
    "test_auth_supabase.py",
    "test_diagnostics_contract.py",
    "test_do178c_compliance.py",
    "test_first_run_setup.py",
    "test_kyc_backend.py",
    "test_kyc_service_full.py",
    "test_training_pipeline.py",
    "test_v1_features.py",
}

_UI_TEST_FILES = {
    "test_desktop_startup.py",
    "test_first_run_setup.py",
    "test_migration_docs_reference_no_qwebengine.py",
    "test_pyside6_no_browser_engine.py",
    "test_pyside6_scaffold.py",
}

_SLOW_TEST_FILES = {
    "test_api_full_coverage.py",
    "test_do178c_compliance.py",
    "test_email_triage_behavior.py",
    "test_recommended_action.py",
    "test_safety_guardrails.py",
    "test_triage_real_world.py",
    "test_v1_features.py",
}

_SAFETY_TEST_FILES = {
    "test_bundled_secrets.py",
    "test_config_contract.py",
    "test_error_hardening.py",
    "test_installer_contract.py",
    "test_platform_guards.py",
    "test_privacy_hygiene.py",
    "test_safety_guardrails.py",
    "test_safety_regression.py",
    "test_secret_hygiene.py",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply coarse-grained markers by file so test selection stays maintainable."""
    for item in items:
        filename = Path(str(item.path)).name
        assigned = False
        if filename in _INTEGRATION_TEST_FILES:
            item.add_marker(pytest.mark.integration)
            assigned = True
        if filename in _UI_TEST_FILES:
            item.add_marker(pytest.mark.ui)
            assigned = True
        if filename in _SLOW_TEST_FILES:
            item.add_marker(pytest.mark.slow)
        if filename in _SAFETY_TEST_FILES:
            item.add_marker(pytest.mark.safety)
            assigned = True
        if not assigned:
            item.add_marker(pytest.mark.unit)


@pytest.fixture(autouse=True)
def _disable_live_services_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unit tests local-first even when the developer shell has live keys."""
    for key in (
        "OPENAI_API_KEY",
        "GOOGLE_AI_API_KEY",
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        monkeypatch.setenv(key, " ")


# ── Settings cache reset ──────────────────────────────────────────────────────
# get_settings() is @lru_cache.  Tests that use monkeypatch.setenv/delenv to
# simulate different configs need a fresh read each time.

@pytest.fixture(autouse=True)
def _reset_settings_cache():
    from outlook_dashboard.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Shared database fixture ───────────────────────────────────────────────────


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Fresh, initialized SQLite database for each test — no real data."""
    from outlook_dashboard.database import initialize_database

    db_path = tmp_path / "test.sqlite3"
    initialize_database(db_path)
    return db_path


# ── Sample email fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def plain_email() -> dict:
    """Minimal valid email with no special urgency signals."""
    return {
        "graph_message_id": "test-plain-001",
        "subject": "Room inquiry",
        "sender_name": "Jane Guest",
        "sender_email": "jane@example.com",
        "body_text": "I would like to inquire about room availability next month.",
        "body_preview": "I would like to inquire about room availability next month.",
        "conversation_id": "conv-plain-001",
        "importance": "normal",
        "source": "test",
    }


@pytest.fixture()
def urgent_email() -> dict:
    """Same-day arrival with VIP, accessibility, and follow-up urgency signals."""
    return {
        "graph_message_id": "test-urgent-001",
        "subject": "URGENT - CEO arriving tonight, need accessible room",
        "sender_name": "Marcus Chen",
        "sender_email": "marcus@corp.example",
        "body_text": (
            "Our CEO is arriving tonight and requires a wheelchair-accessible suite "
            "with a roll-in shower. This is urgent and we are following up for the "
            "third time. Please confirm ASAP."
        ),
        "body_preview": "Our CEO is arriving tonight and requires a wheelchair-accessible suite.",
        "conversation_id": "conv-urgent-001",
        "importance": "high",
        "source": "test",
    }


@pytest.fixture()
def complaint_email() -> dict:
    """Email with complaint and legal escalation language."""
    return {
        "graph_message_id": "test-complaint-001",
        "subject": "Extremely disappointed - need resolution",
        "sender_name": "Upset Guest",
        "sender_email": "upset@example.com",
        "body_text": (
            "I am furious and completely disappointed with the service. "
            "I will contact my attorney and pursue legal action if this is not resolved. "
            "This is absolutely unacceptable."
        ),
        "body_preview": "I am furious and completely disappointed with the service.",
        "conversation_id": "conv-complaint-001",
        "importance": "high",
        "source": "test",
    }


@pytest.fixture()
def cca_completion_email() -> dict:
    """Travel agent has completed a CCA form — should be low urgency, Reservations."""
    return {
        "graph_message_id": "test-cca-001",
        "subject": "Re: CCA form for reservation",
        "sender_name": "Travel Advisor",
        "sender_email": "advisor@travelagency.example",
        "body_text": "Thank you, I completed the credit card authorization form and sent it back.",
        "body_preview": "Thank you, I completed the credit card authorization form.",
        "conversation_id": "conv-cca-001",
        "importance": "normal",
        "source": "test",
    }


@pytest.fixture()
def accessibility_email() -> dict:
    """ADA accommodation request — should trigger accessibility risk flag."""
    return {
        "graph_message_id": "test-ada-001",
        "subject": "Accessible room with roll-in shower",
        "sender_name": "Priya Shah",
        "sender_email": "priya@example.com",
        "body_text": (
            "Please confirm an accessible room with a roll-in shower and shower chair "
            "for our guest who uses a wheelchair."
        ),
        "body_preview": "Please confirm an accessible room with a roll-in shower.",
        "conversation_id": "conv-ada-001",
        "importance": "normal",
        "source": "test",
    }


@pytest.fixture()
def thread_with_quoted_upset() -> str:
    """Full Outlook thread where the latest reply is positive but quoted history is upset."""
    return (
        "Hi Brian,\n\nThank you very much for sending that. I have just completed it.\n"
        "We appreciate your help!\n\nKindest Regards,\nStephanie\n\n"
        "-----Original Message-----\n"
        "From: Guest\nSent: Monday\n"
        "I am furious and want a manager immediately. This is unacceptable."
    )


# ── FastAPI test client ───────────────────────────────────────────────────────


@pytest.fixture()
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    db_path = tmp_path / "replyright-test.sqlite3"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    monkeypatch.setenv("REPLYRIGHT_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("REPLYRIGHT_ADMIN_PASSWORD", "TestPassword123!")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "500")
    monkeypatch.setenv("OPENAI_API_KEY", " ")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", " ")
    monkeypatch.setenv("GEMINI_API_KEY", " ")
    monkeypatch.setenv("ANTHROPIC_API_KEY", " ")
    monkeypatch.setenv("SUPABASE_URL", " ")
    monkeypatch.setenv("SUPABASE_KEY", " ")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", " ")

    import outlook_dashboard.main as main
    from outlook_dashboard.config import get_settings

    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()
    monkeypatch.setattr(main, "ensure_admin", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "admin_user_exists", lambda: True)
    monkeypatch.setattr(main, "download_approved_rules", lambda: [])
    monkeypatch.setattr(main, "download_prompt_versions", lambda: [])
    monkeypatch.setattr(main, "download_known_senders", lambda: [])
    monkeypatch.setattr(main, "flush_feedback_queue", lambda: 0)
    monkeypatch.setattr(main, "start_update_check", lambda: None)
    monkeypatch.setattr(main, "upload_feedback_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "promote_rule_candidates", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main,
        "authenticate_user",
        lambda email, password, db_path=None: (
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "email": email.lower(),
                "role": "admin",
                "_access_token": "test-access",
                "_refresh_token": "test-refresh",
            }
            if email.lower() == "admin@example.com" and password == "TestPassword123!"
            else None
        ),
    )
    monkeypatch.setattr(
        main,
        "get_session_user",
        lambda cookie, db_path=None: (
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "email": "admin@example.com",
                "role": "admin",
            }
            if cookie
            else None
        ),
    )
    monkeypatch.setattr(main, "delete_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        main,
        "list_users",
        lambda db_path=None: [
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "email": "admin@example.com",
                "role": "admin",
                "created_at": "",
                "last_login": "",
                "invited_by_email": None,
            }
        ],
    )
    with TestClient(main.app) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "TestPassword123!"},
        )
        assert response.status_code == 200, response.text
        yield client
    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()

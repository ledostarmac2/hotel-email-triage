from __future__ import annotations

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient


def test_dashboard_static_shell_has_core_panels(app_client: TestClient) -> None:
    response = app_client.get("/")
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")
    assert soup.select_one("#emailList") is not None
    assert soup.select_one("#detailPanel") is not None
    assert soup.select_one("#replyModal") is not None
    assert soup.select_one("script[src^='/static/app.js']") is not None


def test_shared_inbox_workflow_with_mocked_import_feedback_and_reply(app_client: TestClient) -> None:
    payload = {
        "mailbox": "NYCWA_Reservations",
        "folder": "Inbox",
        "messages": [
            {
                "graph_message_id": "msg-001",
                "subject": "Payment link request for arrival May 18",
                "sender_name": "Avery Advisor",
                "sender_email": "avery@agency.example",
                "received_datetime": "2026-05-17T10:00:00",
                "body_text": "Please send a secure payment link for confirmation 123456789 before arrival tomorrow.",
                "body_preview": "Please send a secure payment link.",
                "conversation_id": "conv-001",
                "importance": "high",
                "has_attachments": False,
            },
            {
                "graph_message_id": "msg-002",
                "subject": "Re: Payment link request for arrival May 18",
                "sender_name": "Avery Advisor",
                "sender_email": "avery@agency.example",
                "received_datetime": "2026-05-17T11:00:00",
                "body_text": "Thank you for the quick help. Please confirm once applied.",
                "body_preview": "Thank you for the quick help.",
                "conversation_id": "conv-001",
                "importance": "normal",
                "has_attachments": False,
            },
        ],
    }
    import_response = app_client.post("/api/outlook-desktop/import-json", json=payload)
    assert import_response.status_code == 200, import_response.text
    assert import_response.json()["fetched_count"] == 2
    assert import_response.json()["analyzed_count"] == 2

    list_response = app_client.get("/api/emails")
    assert list_response.status_code == 200
    emails = list_response.json()["emails"]
    assert len(emails) == 1
    selected_id = emails[0]["id"]
    assert emails[0]["conversation_email_count"] == 2
    assert 1 <= emails[0]["urgency_score"] <= 5

    detail_response = app_client.get(f"/api/emails/{selected_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()["email"]
    assert detail["ai_summary"]
    assert isinstance(detail["internal_next_steps"], list)
    assert isinstance(detail["missing_information"], list)
    assert detail["recommended_department_owner"] in {
        "Front Desk",
        "Reservations",
        "Concierge",
        "Sales",
        "Housekeeping",
        "Engineering",
        "All Departments",
    }

    analyze_response = app_client.post(f"/api/emails/{selected_id}/analyze")
    assert analyze_response.status_code == 200
    analyzed = analyze_response.json()["email"]
    assert analyzed["suggested_reply_draft"].startswith("Dear")
    assert "Waldorf Astoria" in analyzed["suggested_reply_draft"]

    feedback_response = app_client.post(
        f"/api/emails/{selected_id}/feedback",
        json={
            "feedback_text": "This agency thread is completed and should stay with Reservations.",
            "corrected_owner": "Reservations",
            "corrected_status": "Completed",
            "summary_quality_rating": 5,
            "reply_quality_rating": 4,
        },
    )
    assert feedback_response.status_code == 200, feedback_response.text
    assert feedback_response.json()["corrections"]["corrected_status"] == "Completed"

    admin_response = app_client.get("/api/admin/stats")
    assert admin_response.status_code == 200
    admin = admin_response.json()
    assert "misclassification_drilldowns" in admin
    assert any(row["action"].startswith("triage.feedback") for row in admin["audit_logs"])


def test_export_inbox_returns_clear_503_on_non_windows(app_client: TestClient, monkeypatch) -> None:
    import outlook_dashboard.main as main

    monkeypatch.setattr(main, "IS_WINDOWS", False)
    response = app_client.post("/api/outlook-desktop/export-inbox")

    assert response.status_code == 503
    assert response.json()["detail"] == "Outlook COM integration is Windows-only."


def test_analyze_email_returns_local_draft_when_ai_provider_fails(
    app_client: TestClient,
    monkeypatch,
) -> None:
    import outlook_dashboard.main as main

    payload = {
        "mailbox": "NYCWA_Reservations",
        "folder": "Inbox",
        "messages": [
            {
                "graph_message_id": "msg-ai-fallback-001",
                "subject": "Question about dinner reservation",
                "sender_name": "Jordan Guest",
                "sender_email": "jordan@example.com",
                "received_datetime": "2026-05-28T10:00:00",
                "body_text": "Can you please help confirm my dinner reservation?",
                "body_preview": "Can you please help confirm my dinner reservation?",
                "conversation_id": "conv-ai-fallback-001",
                "importance": "normal",
                "has_attachments": False,
            }
        ],
    }
    import_response = app_client.post("/api/outlook-desktop/import-json", json=payload)
    assert import_response.status_code == 200, import_response.text
    selected_id = app_client.get("/api/emails").json()["emails"][0]["id"]

    monkeypatch.setattr(
        main,
        "analyze_email",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )
    response = app_client.post(f"/api/emails/{selected_id}/analyze")

    assert response.status_code == 200, response.text
    email = response.json()["email"]
    assert email["suggested_reply_draft"].startswith("Dear")
    assert "Waldorf Astoria" in email["suggested_reply_draft"]
    assert email["analysis_error"] == "AI suggestion unavailable; returned local draft."


def test_analyze_email_returns_generated_draft_if_local_save_fails(
    app_client: TestClient,
    monkeypatch,
) -> None:
    import outlook_dashboard.main as main

    payload = {
        "mailbox": "NYCWA_Reservations",
        "folder": "Inbox",
        "messages": [
            {
                "graph_message_id": "msg-save-fallback-001",
                "subject": "Room availability question",
                "sender_name": "Casey Guest",
                "sender_email": "casey@example.com",
                "received_datetime": "2026-05-28T10:05:00",
                "body_text": "Do you have a king room available next Friday?",
                "body_preview": "Do you have a king room available next Friday?",
                "conversation_id": "conv-save-fallback-001",
                "importance": "normal",
                "has_attachments": False,
            }
        ],
    }
    import_response = app_client.post("/api/outlook-desktop/import-json", json=payload)
    assert import_response.status_code == 200, import_response.text
    selected_id = app_client.get("/api/emails").json()["emails"][0]["id"]

    monkeypatch.setattr(main, "save_analysis", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db locked")))
    response = app_client.post(f"/api/emails/{selected_id}/analyze")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["warning"] == "AI suggestion was generated but could not be saved locally."
    assert payload["email"]["suggested_reply_draft"].startswith("Dear")


def test_admin_invite_returns_manual_link_when_smtp_unconfigured(app_client: TestClient) -> None:
    response = app_client.post("/api/auth/invite", json={"email": "agent@example.com"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True
    assert payload["email_sent"] is False
    assert payload["manual_delivery_required"] is True
    assert payload["invite_url"].startswith("http://testserver/reset-password?token=")
    assert "user_id" in payload


def test_admin_deployment_diagnostics_are_safe_and_useful(app_client: TestClient) -> None:
    response = app_client.get("/api/admin/deployment/diagnostics")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["app"]["native_shell"] == "PySide6"
    assert payload["storage"]["database_exists"] is True
    assert payload["services"]["smtp_configured"] is False
    assert payload["services"]["supabase_configured"] is False
    assert payload["outlook"]["mailbox"] == "NYCWA_Reservations"
    assert "password" not in str(payload).lower()
    assert "service_role" not in str(payload).lower()


def test_auth_rate_limit_returns_429(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "rate-limit.sqlite3"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    monkeypatch.setenv("REPLYRIGHT_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("REPLYRIGHT_ADMIN_PASSWORD", "TestPassword123!")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("OPENAI_API_KEY", " ")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", " ")
    monkeypatch.setenv("ANTHROPIC_API_KEY", " ")
    monkeypatch.setenv("SUPABASE_URL", " ")
    monkeypatch.setenv("SUPABASE_KEY", " ")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", " ")

    import outlook_dashboard.main as main
    from outlook_dashboard.config import get_settings

    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()
    monkeypatch.setattr(main, "ensure_admin", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "authenticate_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "download_approved_rules", lambda: [])
    monkeypatch.setattr(main, "download_prompt_versions", lambda: [])
    monkeypatch.setattr(main, "download_known_senders", lambda: [])
    monkeypatch.setattr(main, "flush_feedback_queue", lambda: 0)
    monkeypatch.setattr(main, "start_update_check", lambda: None)
    with TestClient(main.app) as client:
        for _ in range(2):
            response = client.post(
                "/api/auth/login",
                json={"email": "admin@example.com", "password": "wrong"},
            )
            assert response.status_code == 401
        limited = client.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "wrong"},
        )
        assert limited.status_code == 429
    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()


def test_remember_email_survives_app_restart_style_login(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "remember.sqlite3"
    prefs_path = tmp_path / "preferences.json"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    monkeypatch.setenv("REPLYRIGHT_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("REPLYRIGHT_ADMIN_PASSWORD", "TestPassword123!")
    monkeypatch.setenv("OPENAI_API_KEY", " ")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", " ")
    monkeypatch.setenv("ANTHROPIC_API_KEY", " ")
    monkeypatch.setenv("SUPABASE_URL", " ")
    monkeypatch.setenv("SUPABASE_KEY", " ")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", " ")

    import outlook_dashboard.main as main
    import outlook_dashboard.preferences as preferences
    from outlook_dashboard.config import get_settings

    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()
    monkeypatch.setattr(preferences, "PREFERENCES_PATH", prefs_path)
    monkeypatch.setattr(main, "ensure_admin", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "admin_user_exists", lambda: True)
    monkeypatch.setattr(main, "download_approved_rules", lambda: [])
    monkeypatch.setattr(main, "download_prompt_versions", lambda: [])
    monkeypatch.setattr(main, "download_known_senders", lambda: [])
    monkeypatch.setattr(main, "flush_feedback_queue", lambda: 0)
    monkeypatch.setattr(main, "start_update_check", lambda: None)
    monkeypatch.setattr(
        main,
        "authenticate_user",
        lambda email, password, db_path=None: {
            "id": "00000000-0000-4000-8000-000000000001",
            "email": email.lower(),
            "role": "admin",
            "_access_token": "test-access",
            "_refresh_token": "test-refresh",
        },
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/login",
            data={"email": "Admin@Example.com", "password": "TestPassword123!", "remember_email": "1"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert prefs_path.read_text(encoding="utf-8")

        login_page = client.get("/login")
        assert 'value="admin@example.com" data-server-email' in login_page.text
        assert 'id="rememberEmail" name="remember_email" value="1" checked' in login_page.text

    get_settings.cache_clear()
    main._RATE_LIMIT_BUCKETS.clear()

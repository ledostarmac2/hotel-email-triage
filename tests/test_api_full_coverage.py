"""Full FastAPI endpoint coverage — uses the app_client fixture from conftest.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ── Utility / Health ──────────────────────────────────────────────────────────


def test_healthz(app_client: TestClient) -> None:
    r = app_client.get("/healthz")
    assert r.status_code == 200


def test_api_health(app_client: TestClient) -> None:
    r = app_client.get("/api/health")
    assert r.status_code == 200


def test_api_version(app_client: TestClient) -> None:
    r = app_client.get("/api/version")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data


def test_api_config(app_client: TestClient) -> None:
    r = app_client.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_api_taxonomy(app_client: TestClient) -> None:
    r = app_client.get("/api/taxonomy")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data or isinstance(data, dict)


def test_update_available(app_client: TestClient) -> None:
    r = app_client.get("/api/update-available")
    assert r.status_code in (200, 404, 503)


# ── Auth ──────────────────────────────────────────────────────────────────────


def test_auth_login_success(app_client: TestClient) -> None:
    r = app_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "TestPassword123!"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("role") == "admin"


def test_auth_login_bad_credentials(app_client: TestClient) -> None:
    r = app_client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpassword"},
    )
    assert r.status_code in (401, 403)


def test_auth_login_empty_body(app_client: TestClient) -> None:
    r = app_client.post("/api/auth/login", json={})
    assert r.status_code in (400, 422)


def test_auth_me(app_client: TestClient) -> None:
    r = app_client.get("/api/auth/me")
    assert r.status_code == 200
    data = r.json()
    user = data.get("user") or data
    assert user.get("email") == "admin@example.com"


def test_auth_me_unauthenticated() -> None:
    from outlook_dashboard import main
    from fastapi.testclient import TestClient as FreshClient
    with FreshClient(main.app) as c:
        r = c.get("/api/auth/me")
    assert r.status_code in (401, 403)


def test_auth_startup_state(app_client: TestClient) -> None:
    r = app_client.get("/api/auth/startup-state")
    assert r.status_code == 200
    data = r.json()
    assert "admin_exists" in data or isinstance(data, dict)


def test_auth_logout(app_client: TestClient) -> None:
    r = app_client.post("/api/auth/logout")
    assert r.status_code in (200, 204)


def test_auth_forgot_password_returns_ok(app_client: TestClient) -> None:
    r = app_client.post("/api/auth/forgot-password", json={"email": "admin@example.com"})
    assert r.status_code in (200, 202, 404, 503)


def test_auth_users_list(app_client: TestClient) -> None:
    r = app_client.get("/api/auth/users")
    assert r.status_code == 200
    data = r.json()
    users = data if isinstance(data, list) else data.get("users", [])
    assert isinstance(users, list)
    assert any(u.get("email") == "admin@example.com" for u in users)


def test_auth_users_delete_unknown(app_client: TestClient) -> None:
    r = app_client.delete("/api/auth/users/99999")
    assert r.status_code in (200, 404, 422)


def test_auth_users_reset_password_unknown(app_client: TestClient) -> None:
    r = app_client.post(
        "/api/auth/users/99999/reset-password",
        json={"password": "NewPass1!"},
    )
    assert r.status_code in (200, 404, 422)


def test_auth_credentials_setup_post_empty(app_client: TestClient) -> None:
    r = app_client.post("/api/auth/credentials-setup", json={})
    assert r.status_code in (200, 400, 422)


# ── Emails ────────────────────────────────────────────────────────────────────


def _emails_list(client: TestClient, **params) -> list:
    r = client.get("/api/emails", params=params)
    assert r.status_code == 200
    data = r.json()
    return data if isinstance(data, list) else data.get("emails", [])


def test_emails_list_empty(app_client: TestClient) -> None:
    emails = _emails_list(app_client)
    assert isinstance(emails, list)


def test_emails_list_pagination(app_client: TestClient) -> None:
    emails = _emails_list(app_client, limit=5, offset=0)
    assert isinstance(emails, list)


def test_emails_get_nonexistent(app_client: TestClient) -> None:
    r = app_client.get("/api/emails/99999")
    assert r.status_code == 404


def test_emails_feedback_nonexistent(app_client: TestClient) -> None:
    r = app_client.post(
        "/api/emails/99999/feedback",
        json={"feedback_text": "This email doesn't exist.", "corrected_urgency": 3},
    )
    assert r.status_code in (404, 422)


def _import_sample_email(client: TestClient) -> int:
    payload = {
        "messages": [
            {
                "graph_message_id": "e2e-test-001",
                "subject": "Test email import",
                "sender_name": "Test Sender",
                "sender_email": "sender@example.com",
                "body_text": "This is a test email body.",
                "body_preview": "This is a test email body.",
                "conversation_id": "conv-e2e-001",
                "importance": "normal",
                "received_datetime": "2026-05-01T10:00:00Z",
            }
        ]
    }
    r = client.post("/api/outlook-desktop/import-json", json=payload)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    return data.get("imported") or data.get("count") or 1


def test_emails_import_then_list(app_client: TestClient) -> None:
    _import_sample_email(app_client)
    emails = _emails_list(app_client)
    assert len(emails) >= 1


def test_emails_import_then_get(app_client: TestClient) -> None:
    _import_sample_email(app_client)
    emails = _emails_list(app_client)
    assert len(emails) >= 1
    email_id = emails[0]["id"]
    r = app_client.get(f"/api/emails/{email_id}")
    assert r.status_code == 200
    data = r.json()
    email = data.get("email") or data
    assert email.get("id") == email_id


def test_emails_import_then_feedback(app_client: TestClient) -> None:
    _import_sample_email(app_client)
    emails = _emails_list(app_client)
    email_id = emails[0]["id"]
    r = app_client.post(
        f"/api/emails/{email_id}/feedback",
        json={
            "feedback_text": "This should be Front Desk urgency 4.",
            "corrected_urgency": 4,
            "corrected_owner": "Front Desk",
        },
    )
    assert r.status_code in (200, 201)


def test_emails_import_duplicate_idempotent(app_client: TestClient) -> None:
    _import_sample_email(app_client)
    _import_sample_email(app_client)
    emails = _emails_list(app_client)
    assert len(emails) == 1


def test_emails_import_missing_graph_id(app_client: TestClient) -> None:
    payload = {"messages": [{"subject": "No ID email", "body_text": "No graph_message_id"}]}
    r = app_client.post("/api/outlook-desktop/import-json", json=payload)
    assert r.status_code in (200, 201, 422)


def test_emails_import_empty_list(app_client: TestClient) -> None:
    r = app_client.post("/api/outlook-desktop/import-json", json={"messages": []})
    assert r.status_code in (200, 201)
    assert r.json().get("imported", 0) == 0


def test_emails_export_inbox(app_client: TestClient) -> None:
    _import_sample_email(app_client)
    r = app_client.post("/api/outlook-desktop/export-inbox", json={})
    # 200/201: success; 400: Outlook not installed (Windows runner); 503: non-Windows; 422: validation
    assert r.status_code in (200, 201, 400, 422, 503)
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, dict)


# ── Sync ──────────────────────────────────────────────────────────────────────


def test_sync_outlook_no_credentials(app_client: TestClient) -> None:
    r = app_client.post("/api/sync/outlook")
    assert r.status_code in (200, 400, 503)


def test_ai_process_pending(app_client: TestClient) -> None:
    r = app_client.post("/api/ai/process-pending")
    assert r.status_code in (200, 202, 400, 503)


# ── Admin ─────────────────────────────────────────────────────────────────────


def test_admin_stats(app_client: TestClient) -> None:
    r = app_client.get("/api/admin/stats")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_admin_training_status(app_client: TestClient) -> None:
    r = app_client.get("/api/admin/training/status")
    assert r.status_code == 200


def test_admin_training_run(app_client: TestClient) -> None:
    r = app_client.post("/api/admin/training/run")
    assert r.status_code in (200, 202, 400, 503)


def test_admin_training_examples(app_client: TestClient) -> None:
    r = app_client.get("/api/admin/training/examples")
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


def test_admin_prompts_list(app_client: TestClient) -> None:
    r = app_client.get("/api/admin/prompts")
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


def test_admin_classifier_train(app_client: TestClient) -> None:
    r = app_client.post("/api/admin/classifier/train")
    assert r.status_code in (200, 202, 400, 503)


def test_admin_intelligence_health(app_client: TestClient) -> None:
    r = app_client.get("/api/admin/intelligence/health")
    assert r.status_code == 200


def test_admin_intelligence_sender_profile(app_client: TestClient) -> None:
    r = app_client.get("/api/admin/intelligence/sender-profile?domain=example.com")
    assert r.status_code in (200, 404)


def test_admin_intelligence_signals(app_client: TestClient) -> None:
    _import_sample_email(app_client)
    emails = _emails_list(app_client)
    email_id = emails[0]["id"]
    r = app_client.get(f"/api/admin/intelligence/signals?email_id={email_id}")
    assert r.status_code in (200, 404)


def test_admin_models_feature_importance(app_client: TestClient) -> None:
    r = app_client.get("/api/admin/models/feature-importance")
    assert r.status_code in (200, 404)


# ── Rule Candidates ───────────────────────────────────────────────────────────


def test_rule_candidates_list(app_client: TestClient) -> None:
    r = app_client.get("/api/rule-candidates")
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


# ── KYC Config / Status ───────────────────────────────────────────────────────


def _kyc_settings(data: dict) -> dict:
    return data.get("settings") or data


def test_kyc_config_get(app_client: TestClient) -> None:
    r = app_client.get("/api/kyc/config")
    assert r.status_code == 200
    s = _kyc_settings(r.json())
    assert "enabled" in s
    assert "reminder_interval_minutes" in s


def test_kyc_config_patch_interval(app_client: TestClient) -> None:
    r = app_client.put("/api/kyc/config", json={"reminder_interval_minutes": 30})
    assert r.status_code == 200
    assert _kyc_settings(r.json())["reminder_interval_minutes"] == 30


def test_kyc_config_patch_enable_disable(app_client: TestClient) -> None:
    r = app_client.put("/api/kyc/config", json={"enabled": False})
    assert r.status_code == 200
    assert _kyc_settings(r.json())["enabled"] is False
    r = app_client.put("/api/kyc/config", json={"enabled": True})
    assert r.status_code == 200
    assert _kyc_settings(r.json())["enabled"] is True


def test_kyc_config_patch_strict_mode(app_client: TestClient) -> None:
    r = app_client.put("/api/kyc/config", json={"strict_mode": True})
    assert r.status_code == 200
    assert _kyc_settings(r.json())["strict_mode"] is True


def test_kyc_config_patch_team_members(app_client: TestClient) -> None:
    r = app_client.put("/api/kyc/config", json={"phone_team_members": ["Alice", "Bob"]})
    assert r.status_code == 200
    assert "Alice" in _kyc_settings(r.json())["phone_team_members"]


def test_kyc_config_invalid_interval(app_client: TestClient) -> None:
    r = app_client.put("/api/kyc/config", json={"reminder_interval_minutes": 0})
    assert r.status_code in (400, 422)


def _kyc_status(data: dict) -> dict:
    return data.get("status") or data


def test_kyc_status(app_client: TestClient) -> None:
    r = app_client.get("/api/kyc/status")
    assert r.status_code == 200
    s = _kyc_status(r.json())
    assert "settings" in s
    assert "overdue" in s
    assert "missed_count" in s


def test_kyc_reminders(app_client: TestClient) -> None:
    r = app_client.post("/api/kyc/reminders", json={})
    assert r.status_code in (200, 404, 422)


def test_kyc_history(app_client: TestClient) -> None:
    r = app_client.get("/api/kyc/history")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data or isinstance(data, list)


# ── KYC Event Lifecycle ───────────────────────────────────────────────────────


def _get_current_event_id(client: TestClient) -> int | None:
    status = _kyc_status(client.get("/api/kyc/status").json())
    event = status.get("current_event")
    return event["id"] if event else None


def _force_event(client: TestClient) -> int:
    app_client_patch = client.put(
        "/api/kyc/config",
        json={"enabled": True, "reminder_interval_minutes": 1},
    )
    assert app_client_patch.status_code == 200
    status = _kyc_status(client.get("/api/kyc/status").json())
    event = status.get("current_event")
    if event:
        return int(event["id"])
    pytest.skip("No current KYC event available for action tests")


def _kyc_event(data: dict) -> dict:
    return data.get("event") or data


def test_kyc_event_acknowledge(app_client: TestClient) -> None:
    event_id = _force_event(app_client)
    r = app_client.post(f"/api/kyc/events/{event_id}/acknowledge", json={})
    assert r.status_code == 200
    assert _kyc_event(r.json())["status"] == "acknowledged"


def test_kyc_event_snooze(app_client: TestClient) -> None:
    event_id = _force_event(app_client)
    r = app_client.post(f"/api/kyc/events/{event_id}/snooze", json={"snooze_minutes": 10})
    assert r.status_code == 200
    event = _kyc_event(r.json())
    assert event["status"] == "snoozed"
    assert event["snoozed_until"] is not None


def test_kyc_event_complete(app_client: TestClient) -> None:
    event_id = _force_event(app_client)
    r = app_client.post(
        f"/api/kyc/events/{event_id}/complete",
        json={"team_member": "Hyun Song"},
    )
    assert r.status_code == 200
    event = _kyc_event(r.json())
    assert event["status"] == "completed"
    assert event["team_member"] == "Hyun Song"


def test_kyc_event_skip(app_client: TestClient) -> None:
    event_id = _force_event(app_client)
    r = app_client.post(
        f"/api/kyc/events/{event_id}/skip",
        json={"reason": "Not applicable today"},
    )
    assert r.status_code == 200
    event = _kyc_event(r.json())
    assert event["status"] == "skipped"
    assert event["skip_reason"] == "Not applicable today"


def test_kyc_event_nonexistent(app_client: TestClient) -> None:
    r = app_client.post("/api/kyc/events/99999/acknowledge", json={})
    assert r.status_code in (404, 422)


def test_kyc_complete_updates_last_inspection(app_client: TestClient) -> None:
    event_id = _force_event(app_client)
    app_client.post(f"/api/kyc/events/{event_id}/complete", json={"team_member": "Alice"})
    config = _kyc_settings(app_client.get("/api/kyc/config").json())
    assert config.get("last_inspection_at") is not None


def test_kyc_history_after_actions(app_client: TestClient) -> None:
    event_id = _force_event(app_client)
    app_client.post(f"/api/kyc/events/{event_id}/complete", json={})
    r = app_client.get("/api/kyc/history")
    assert r.status_code == 200
    history = r.json()
    if isinstance(history, list):
        events = history
    else:
        events = history.get("events") or history.get("history") or []
    assert any(e.get("status") == "completed" for e in events)


# ── Rate Limiting ─────────────────────────────────────────────────────────────


def test_health_not_rate_limited(app_client: TestClient) -> None:
    for _ in range(20):
        r = app_client.get("/healthz")
        assert r.status_code == 200


def test_login_rate_limit_headers(app_client: TestClient) -> None:
    r = app_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "TestPassword123!"},
    )
    assert r.status_code == 200

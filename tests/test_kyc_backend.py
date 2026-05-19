from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from outlook_dashboard.database import initialize_database
from outlook_dashboard.kyc.models import KycActionRequest, KycEventCreate, KycSettingsUpdate
from outlook_dashboard.kyc.service import KycService


def _past_iso(minutes: int = 30) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def test_kyc_config_and_status_endpoint_create_due_event(app_client: TestClient) -> None:
    config_response = app_client.put(
        "/api/kyc/config",
        json={
            "enabled": True,
            "reminder_interval_minutes": 15,
            "last_inspection_at": _past_iso(20),
            "strict_mode": True,
            "escalation_enabled": True,
            "escalation_after_missed": 1,
            "phone_team_members": ["Brian Tarabocchia", "Hyun Song"],
            "remember_account": True,
            "account_alias": "WANY Reservations KYC",
        },
    )
    assert config_response.status_code == 200, config_response.text
    settings = config_response.json()["settings"]
    assert settings["reminder_interval_minutes"] == 15
    assert settings["account_alias"] == "WANY Reservations KYC"

    status_response = app_client.get("/api/kyc/status")
    assert status_response.status_code == 200, status_response.text
    status = status_response.json()["status"]
    assert status["overdue"] is True
    assert status["requires_acknowledgement"] is True
    assert status["escalation_due"] is True
    assert status["current_event"]["status"] == "pending"


def test_kyc_event_actions_and_history_are_audited(app_client: TestClient) -> None:
    create_response = app_client.post("/api/kyc/reminders", json={"source": "test", "note": "Hourly check"})
    assert create_response.status_code == 200, create_response.text
    event_id = create_response.json()["event"]["id"]

    ack_response = app_client.post(
        f"/api/kyc/events/{event_id}/acknowledge",
        json={"reason": "Inspection seen by reservations."},
    )
    assert ack_response.status_code == 200, ack_response.text
    assert ack_response.json()["event"]["status"] == "acknowledged"

    snooze_response = app_client.post(
        f"/api/kyc/events/{event_id}/snooze",
        json={"snooze_minutes": 10, "reason": "Guest call in progress."},
    )
    assert snooze_response.status_code == 200, snooze_response.text
    assert snooze_response.json()["event"]["status"] == "snoozed"
    assert snooze_response.json()["event"]["snoozed_until"]

    complete_response = app_client.post(
        f"/api/kyc/events/{event_id}/complete",
        json={"team_member": "Brian Tarabocchia", "reason": "Inspection completed."},
    )
    assert complete_response.status_code == 200, complete_response.text
    completed = complete_response.json()["event"]
    assert completed["status"] == "completed"
    assert completed["team_member"] == "Brian Tarabocchia"

    history_response = app_client.get("/api/kyc/history")
    assert history_response.status_code == 200
    assert any(row["id"] == event_id and row["status"] == "completed" for row in history_response.json()["events"])

    admin_response = app_client.get("/api/admin/stats")
    assert admin_response.status_code == 200
    actions = {row["action"] for row in admin_response.json()["audit_logs"]}
    assert "kyc.event.create" in actions
    assert "kyc.event.complete" in actions


def test_kyc_skip_missing_event_returns_404(app_client: TestClient) -> None:
    response = app_client.post("/api/kyc/events/999999/skip", json={"reason": "No event."})
    assert response.status_code == 404
    assert response.json()["detail"] == "KYC reminder event not found."


def test_kyc_local_persistence_survives_service_restart(tmp_path) -> None:
    db_path = tmp_path / "kyc.sqlite3"
    initialize_database(db_path)

    service = KycService(db_path)
    settings = service.update_settings(
        KycSettingsUpdate(reminder_interval_minutes=30, last_inspection_at=_past_iso(5)),
        actor_user_id="tester",
        actor_email="tester@example.com",
    )
    assert settings.reminder_interval_minutes == 30
    event = service.create_event(
        KycEventCreate(source="unit-test", note="Persist this event"),
        actor_user_id="tester",
        actor_email="tester@example.com",
    )
    service.skip(
        event.id,
        KycActionRequest(reason="Manual skip for persistence test."),
        actor_user_id="tester",
        actor_email="tester@example.com",
    )

    restarted = KycService(db_path)
    assert restarted.get_settings().reminder_interval_minutes == 30
    history = restarted.history()
    assert any(row.id == event.id and row.status == "skipped" for row in history)

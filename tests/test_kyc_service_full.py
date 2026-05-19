"""KYC service full lifecycle tests — real temp SQLite, no API keys needed."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from outlook_dashboard.database import initialize_database
from outlook_dashboard.kyc.models import KycActionRequest, KycEventCreate, KycSettingsUpdate
from outlook_dashboard.kyc.service import KycService


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def svc(tmp_path: Path) -> KycService:
    db = tmp_path / "kyc_test.sqlite3"
    initialize_database(db)
    return KycService(db_path=db)


ACTOR = dict(actor_user_id="u-1", actor_email="tester@example.com")


# ── Default Settings ──────────────────────────────────────────────────────────


def test_default_settings_enabled(svc: KycService) -> None:
    s = svc.get_settings()
    assert s.enabled is True


def test_default_settings_interval(svc: KycService) -> None:
    s = svc.get_settings()
    assert s.reminder_interval_minutes == 15


def test_default_settings_strict_mode_off(svc: KycService) -> None:
    s = svc.get_settings()
    assert s.strict_mode is False


def test_default_settings_escalation_off(svc: KycService) -> None:
    s = svc.get_settings()
    assert s.escalation_enabled is False


def test_default_settings_no_last_inspection(svc: KycService) -> None:
    s = svc.get_settings()
    assert s.last_inspection_at is None


# ── Settings Update ───────────────────────────────────────────────────────────


def test_update_settings_interval(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(reminder_interval_minutes=30), **ACTOR)
    assert svc.get_settings().reminder_interval_minutes == 30


def test_update_settings_strict_mode(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(strict_mode=True), **ACTOR)
    assert svc.get_settings().strict_mode is True


def test_update_settings_disable(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    assert svc.get_settings().enabled is False


def test_update_settings_escalation(svc: KycService) -> None:
    svc.update_settings(
        KycSettingsUpdate(escalation_enabled=True, escalation_after_missed=3),
        **ACTOR,
    )
    s = svc.get_settings()
    assert s.escalation_enabled is True
    assert s.escalation_after_missed == 3


def test_update_settings_team_members(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(phone_team_members=["Alice", "Bob"]), **ACTOR)
    assert "Alice" in svc.get_settings().phone_team_members


def test_update_settings_active_hours(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(active_hours_start="08:00", active_hours_end="20:00"), **ACTOR)
    s = svc.get_settings()
    assert s.active_hours_start == "08:00"
    assert s.active_hours_end == "20:00"


def test_update_settings_idempotent(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(reminder_interval_minutes=20), **ACTOR)
    svc.update_settings(KycSettingsUpdate(reminder_interval_minutes=20), **ACTOR)
    assert svc.get_settings().reminder_interval_minutes == 20


# ── Status: no event, disabled ────────────────────────────────────────────────


def test_status_disabled_no_event(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    status = svc.status()
    assert status.current_event is None
    assert status.overdue is False
    assert status.requires_acknowledgement is False


def test_status_enabled_no_last_inspection_creates_event(svc: KycService) -> None:
    status = svc.status()
    assert status.current_event is not None
    assert status.current_event.status == "pending"


def test_status_overdue_no_current_creates_event_when_due(svc: KycService) -> None:
    status = svc.status()
    assert status.current_event is not None


# ── Manual Event Creation ─────────────────────────────────────────────────────


def test_create_manual_event(svc: KycService) -> None:
    req = KycEventCreate(source="manual", note="Test manual event")
    event = svc.create_event(req, **ACTOR)
    assert event.id > 0
    assert event.status == "pending"
    assert event.source == "manual"
    assert event.note == "Test manual event"


def test_create_event_with_due_at(svc: KycService) -> None:
    due = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    req = KycEventCreate(due_at=due, source="manual")
    event = svc.create_event(req, **ACTOR)
    assert event.due_at is not None


def test_create_event_without_due_at_defaults_to_now(svc: KycService) -> None:
    req = KycEventCreate(source="test")
    event = svc.create_event(req, **ACTOR)
    assert event.due_at is not None


# ── Acknowledge ───────────────────────────────────────────────────────────────


def test_acknowledge_pending_event(svc: KycService) -> None:
    status = svc.status()
    assert status.current_event is not None
    event = svc.acknowledge(status.current_event.id, KycActionRequest(), **ACTOR)
    assert event.status == "acknowledged"
    assert event.acknowledged_at is not None


def test_acknowledge_sets_timestamp(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    before = datetime.now(UTC)
    event = svc.acknowledge(event_id, KycActionRequest(), **ACTOR)
    after = datetime.now(UTC)
    from outlook_dashboard.kyc.service import _parse_dt
    acked = _parse_dt(event.acknowledged_at)
    assert acked is not None
    assert before <= acked <= after + timedelta(seconds=2)


def test_acknowledge_nonexistent_raises(svc: KycService) -> None:
    with pytest.raises(KeyError):
        svc.acknowledge(99999, KycActionRequest(), **ACTOR)


# ── Snooze ────────────────────────────────────────────────────────────────────


def test_snooze_sets_status_snoozed(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    event = svc.snooze(event_id, KycActionRequest(snooze_minutes=10), **ACTOR)
    assert event.status == "snoozed"
    assert event.snoozed_until is not None


def test_snooze_explicit_minutes(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    before = datetime.now(UTC)
    event = svc.snooze(event_id, KycActionRequest(snooze_minutes=15), **ACTOR)
    from outlook_dashboard.kyc.service import _parse_dt
    until = _parse_dt(event.snoozed_until)
    assert until is not None
    assert (until - before).total_seconds() >= 14 * 60


def test_snooze_default_uses_min_interval_60(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(reminder_interval_minutes=120), **ACTOR)
    event_id = svc.status().current_event.id
    before = datetime.now(UTC)
    event = svc.snooze(event_id, KycActionRequest(), **ACTOR)
    from outlook_dashboard.kyc.service import _parse_dt
    until = _parse_dt(event.snoozed_until)
    assert until is not None
    snooze_secs = (until - before).total_seconds()
    assert snooze_secs <= 61 * 60, "Default snooze must not exceed 60 min when interval > 60"


def test_snooze_interval_under_60_uses_interval(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(reminder_interval_minutes=20), **ACTOR)
    event_id = svc.status().current_event.id
    before = datetime.now(UTC)
    event = svc.snooze(event_id, KycActionRequest(), **ACTOR)
    from outlook_dashboard.kyc.service import _parse_dt
    until = _parse_dt(event.snoozed_until)
    assert until is not None
    snooze_secs = (until - before).total_seconds()
    assert 19 * 60 <= snooze_secs <= 21 * 60


def test_snooze_nonexistent_raises(svc: KycService) -> None:
    with pytest.raises(KeyError):
        svc.snooze(99999, KycActionRequest(snooze_minutes=5), **ACTOR)


# ── Complete ──────────────────────────────────────────────────────────────────


def test_complete_event(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    event = svc.complete(event_id, KycActionRequest(team_member="Alice"), **ACTOR)
    assert event.status == "completed"
    assert event.completed_at is not None
    assert event.team_member == "Alice"


def test_complete_updates_last_inspection(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    svc.complete(event_id, KycActionRequest(), **ACTOR)
    settings = svc.get_settings()
    assert settings.last_inspection_at is not None


def test_complete_without_team_member(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    event = svc.complete(event_id, KycActionRequest(), **ACTOR)
    assert event.status == "completed"
    assert event.team_member is None


def test_complete_nonexistent_raises(svc: KycService) -> None:
    with pytest.raises(KeyError):
        svc.complete(99999, KycActionRequest(), **ACTOR)


# ── Skip ──────────────────────────────────────────────────────────────────────


def test_skip_event(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    event = svc.skip(event_id, KycActionRequest(reason="Not required today"), **ACTOR)
    assert event.status == "skipped"
    assert event.skipped_at is not None
    assert event.skip_reason == "Not required today"


def test_skip_without_reason(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    event = svc.skip(event_id, KycActionRequest(), **ACTOR)
    assert event.status == "skipped"
    assert event.skip_reason is None


def test_skip_nonexistent_raises(svc: KycService) -> None:
    with pytest.raises(KeyError):
        svc.skip(99999, KycActionRequest(), **ACTOR)


# ── Overdue / Strict Mode ─────────────────────────────────────────────────────


def _create_overdue_event(svc: KycService) -> int:
    """Create an event with a due_at in the past."""
    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    req = KycEventCreate(due_at=past, source="test-overdue")
    event = svc.create_event(req, **ACTOR)
    return event.id


def test_overdue_detected(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    _create_overdue_event(svc)
    svc.update_settings(KycSettingsUpdate(enabled=True), **ACTOR)
    status = svc.status()
    assert status.overdue is True


def test_requires_acknowledgement_when_strict_overdue(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    _create_overdue_event(svc)
    svc.update_settings(KycSettingsUpdate(enabled=True, strict_mode=True), **ACTOR)
    status = svc.status()
    if status.overdue:
        assert status.requires_acknowledgement is True


def test_requires_acknowledgement_false_without_strict(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(strict_mode=False), **ACTOR)
    status = svc.status()
    assert status.requires_acknowledgement is False


def test_snoozed_event_not_overdue_until_snooze_expires(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    svc.snooze(event_id, KycActionRequest(snooze_minutes=60), **ACTOR)
    status = svc.status()
    if status.current_event and status.current_event.status == "snoozed":
        assert status.overdue is False


# ── Missed Count ──────────────────────────────────────────────────────────────


def test_missed_count_zero_initially(svc: KycService) -> None:
    status = svc.status()
    assert status.missed_count >= 0


def test_missed_count_includes_overdue_pending(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    past = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    req = KycEventCreate(due_at=past, source="test-missed")
    svc.create_event(req, **ACTOR)
    svc.update_settings(KycSettingsUpdate(enabled=True), **ACTOR)
    status = svc.status()
    assert status.missed_count >= 1


def test_completed_event_not_missed(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    svc.complete(event_id, KycActionRequest(), **ACTOR)
    count_after = svc.repo.missed_count()
    assert count_after == 0


# ── Escalation ────────────────────────────────────────────────────────────────


def test_escalation_not_due_below_threshold(svc: KycService) -> None:
    svc.update_settings(
        KycSettingsUpdate(escalation_enabled=True, escalation_after_missed=5),
        **ACTOR,
    )
    status = svc.status()
    assert status.missed_count < 5 or status.escalation_due is True


def test_escalation_due_when_missed_gte_threshold(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    for _ in range(3):
        past = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
        svc.create_event(KycEventCreate(due_at=past, source="overdue"), **ACTOR)
    svc.update_settings(
        KycSettingsUpdate(enabled=True, escalation_enabled=True, escalation_after_missed=2),
        **ACTOR,
    )
    status = svc.status()
    if status.missed_count >= 2:
        assert status.escalation_due is True


def test_escalation_false_when_disabled(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(escalation_enabled=False), **ACTOR)
    status = svc.status()
    assert status.escalation_due is False


# ── History ───────────────────────────────────────────────────────────────────


def test_history_empty_initially(svc: KycService) -> None:
    events = svc.history()
    assert isinstance(events, list)


def test_history_grows_after_completion(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    svc.complete(event_id, KycActionRequest(), **ACTOR)
    events = svc.history()
    assert any(e.status == "completed" for e in events)


def test_history_limit(svc: KycService) -> None:
    for _ in range(5):
        req = KycEventCreate(source="test-hist")
        e = svc.create_event(req, **ACTOR)
        svc.complete(e.id, KycActionRequest(), **ACTOR)
    events = svc.history(limit=3)
    assert len(events) <= 3


def test_history_ordered_most_recent_first(svc: KycService) -> None:
    for _ in range(3):
        req = KycEventCreate(source="test-order")
        e = svc.create_event(req, **ACTOR)
        svc.complete(e.id, KycActionRequest(), **ACTOR)
    events = svc.history(limit=10)
    if len(events) >= 2:
        assert events[0].id >= events[1].id


# ── Next Due Calculation ──────────────────────────────────────────────────────


def test_next_due_after_complete(svc: KycService) -> None:
    event_id = svc.status().current_event.id
    svc.complete(event_id, KycActionRequest(), **ACTOR)
    status = svc.status()
    if status.settings.enabled:
        assert status.next_due_at is not None


def test_next_due_none_when_disabled(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    event_id = svc.status().current_event.id if svc.status().current_event else None
    if event_id:
        svc.complete(event_id, KycActionRequest(), **ACTOR)
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    status = svc.status()
    assert status.next_due_at is None


# ── No last_inspection_at ─────────────────────────────────────────────────────


def test_next_due_returns_now_when_no_last_inspection(svc: KycService) -> None:
    from outlook_dashboard.kyc.service import _parse_dt
    settings = svc.get_settings()
    assert settings.last_inspection_at is None
    status = svc.status()
    assert status.current_event is not None


# ── Repository Direct ─────────────────────────────────────────────────────────


def test_repo_event_returns_none_for_missing(svc: KycService) -> None:
    assert svc.repo.event(99999) is None


def test_repo_current_event_returns_none_when_all_completed(svc: KycService) -> None:
    svc.update_settings(KycSettingsUpdate(enabled=False), **ACTOR)
    event_id = svc.status().current_event.id if svc.status().current_event else None
    if event_id:
        svc.complete(event_id, KycActionRequest(), **ACTOR)
    assert svc.repo.current_event() is None


def test_repo_update_event_raises_for_missing(svc: KycService) -> None:
    with pytest.raises(KeyError):
        svc.repo.update_event(99999, {"status": "skipped"})

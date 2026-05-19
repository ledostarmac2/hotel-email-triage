from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..database import record_audit_event
from ..text_utils import utc_now_iso
from .models import KycActionRequest, KycEvent, KycEventCreate, KycSettings, KycSettingsUpdate, KycStatus
from .repository import KycRepository


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


class KycService:
    def __init__(self, db_path: Path | None = None) -> None:
        self.repo = KycRepository(db_path)
        self.db_path = db_path

    def get_settings(self) -> KycSettings:
        return self.repo.settings()

    def update_settings(
        self,
        update: KycSettingsUpdate,
        *,
        actor_user_id: str | int | None,
        actor_email: str | None,
    ) -> KycSettings:
        current = self.repo.settings()
        updates = {key: value for key, value in _dump(update).items() if value is not None}
        merged = _copy_model(current, updates)
        saved = self.repo.save_settings(merged)
        self._audit("kyc.settings.update", None, actor_user_id, actor_email, {"updated_fields": sorted(updates)})
        return saved

    def status(self) -> KycStatus:
        settings = self.repo.settings()
        current = self.repo.current_event()
        now = datetime.now(UTC)
        if settings.enabled and current is None:
            due_at = self._next_due(settings, now)
            if due_at <= now:
                current = self.repo.create_event(due_at=_iso(due_at), source="scheduler")
        next_due = self._next_due(settings, now) if settings.enabled else None
        event_due = _parse_dt(current.due_at) if current else None
        overdue = bool(event_due and event_due <= now and current.status != "snoozed")
        if current and current.status == "snoozed":
            snoozed_until = _parse_dt(current.snoozed_until)
            overdue = bool(snoozed_until and snoozed_until <= now)
            next_due = snoozed_until or next_due
        missed = self.repo.missed_count()
        return KycStatus(
            settings=settings,
            current_event=current,
            next_due_at=_iso(next_due) if next_due else None,
            overdue=overdue,
            requires_acknowledgement=bool(overdue and settings.strict_mode),
            missed_count=missed,
            escalation_due=bool(settings.escalation_enabled and missed >= settings.escalation_after_missed),
        )

    def create_event(
        self,
        request: KycEventCreate,
        *,
        actor_user_id: str | int | None,
        actor_email: str | None,
    ) -> KycEvent:
        due_at = _parse_dt(request.due_at) or datetime.now(UTC)
        event = self.repo.create_event(due_at=_iso(due_at), source=request.source, note=request.note)
        self._audit("kyc.event.create", event.id, actor_user_id, actor_email, {"source": request.source})
        return event

    def history(self, *, limit: int = 100) -> list[KycEvent]:
        return self.repo.list_events(limit=limit)

    def acknowledge(
        self,
        event_id: int,
        request: KycActionRequest,
        *,
        actor_user_id: str | int | None,
        actor_email: str | None,
    ) -> KycEvent:
        return self._action(
            event_id,
            "acknowledge",
            {"status": "acknowledged", "acknowledged_at": utc_now_iso()},
            request,
            actor_user_id,
            actor_email,
        )

    def snooze(
        self,
        event_id: int,
        request: KycActionRequest,
        *,
        actor_user_id: str | int | None,
        actor_email: str | None,
    ) -> KycEvent:
        settings = self.repo.settings()
        minutes = request.snooze_minutes or min(settings.reminder_interval_minutes, 60)
        until = datetime.now(UTC) + timedelta(minutes=minutes)
        return self._action(
            event_id,
            "snooze",
            {"status": "snoozed", "snoozed_until": _iso(until)},
            _copy_model(request, {"snooze_minutes": minutes}),
            actor_user_id,
            actor_email,
        )

    def complete(
        self,
        event_id: int,
        request: KycActionRequest,
        *,
        actor_user_id: str | int | None,
        actor_email: str | None,
    ) -> KycEvent:
        now = utc_now_iso()
        event = self._action(
            event_id,
            "complete",
            {"status": "completed", "completed_at": now, "team_member": request.team_member},
            request,
            actor_user_id,
            actor_email,
        )
        settings = self.repo.settings()
        self.repo.save_settings(_copy_model(settings, {"last_inspection_at": now}))
        return event

    def skip(
        self,
        event_id: int,
        request: KycActionRequest,
        *,
        actor_user_id: str | int | None,
        actor_email: str | None,
    ) -> KycEvent:
        return self._action(
            event_id,
            "skip",
            {"status": "skipped", "skipped_at": utc_now_iso(), "skip_reason": request.reason},
            request,
            actor_user_id,
            actor_email,
        )

    def _action(
        self,
        event_id: int,
        action: str,
        fields: dict[str, Any],
        request: KycActionRequest,
        actor_user_id: str | int | None,
        actor_email: str | None,
    ) -> KycEvent:
        if self.repo.event(event_id) is None:
            raise KeyError(event_id)
        event = self.repo.update_event(event_id, fields)
        self.repo.record_acknowledgement(
            event_id=event_id,
            action=action,
            reason=request.reason,
            snooze_minutes=request.snooze_minutes,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
        )
        self._audit(
            f"kyc.event.{action}",
            event_id,
            actor_user_id,
            actor_email,
            {"reason": request.reason, "snooze_minutes": request.snooze_minutes, "team_member": request.team_member},
        )
        return event

    def _next_due(self, settings: KycSettings, now: datetime) -> datetime:
        last = _parse_dt(settings.last_inspection_at)
        if last is None:
            return now
        return last + timedelta(minutes=settings.reminder_interval_minutes)

    def _audit(
        self,
        action: str,
        event_id: int | None,
        actor_user_id: str | int | None,
        actor_email: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repo.record_audit(
            action=action,
            event_id=event_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            metadata=metadata,
        )
        record_audit_event(
            action=action,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            entity_type="kyc_event" if event_id is not None else "kyc_settings",
            entity_id=event_id,
            metadata=metadata,
            db_path=self.db_path,
        )


def _dump(model: Any) -> dict[str, Any]:
    dump = getattr(model, "model_dump", None)
    if callable(dump):
        return dump()
    return model.dict()


def _copy_model(model: Any, update: dict[str, Any]) -> Any:
    copy_fn = getattr(model, "model_copy", None)
    if callable(copy_fn):
        return copy_fn(update=update)
    return model.copy(update=update)

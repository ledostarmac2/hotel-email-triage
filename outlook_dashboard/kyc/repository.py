from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import UTC, datetime
from typing import Any

from .. import __version__
from ..database import managed_connect, row_to_dict
from ..runtime_log import get_logger
from ..text_utils import utc_now_iso
from .models import KycEvent, KycSettings

_log = get_logger("kyc")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _decode(value: Any, fallback: Any = None) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _model_dump(model: Any) -> dict[str, Any]:
    dump = getattr(model, "model_dump", None)
    if callable(dump):
        return dump()
    return model.dict()


def _model_copy(model: Any, update: dict[str, Any]) -> Any:
    copy_fn = getattr(model, "model_copy", None)
    if callable(copy_fn):
        return copy_fn(update=update)
    return model.copy(update=update)


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


def ensure_kyc_schema(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS kyc_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled INTEGER NOT NULL DEFAULT 1,
            reminder_interval_minutes INTEGER NOT NULL DEFAULT 15,
            active_hours_start TEXT NOT NULL DEFAULT '00:00',
            active_hours_end TEXT NOT NULL DEFAULT '23:59',
            strict_mode INTEGER NOT NULL DEFAULT 0,
            escalation_enabled INTEGER NOT NULL DEFAULT 0,
            escalation_after_missed INTEGER NOT NULL DEFAULT 2,
            escalation_recipients TEXT NOT NULL DEFAULT '[]',
            last_inspection_at TEXT,
            phone_team_members TEXT NOT NULL DEFAULT '[]',
            remember_account INTEGER NOT NULL DEFAULT 0,
            account_alias TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kyc_inspection_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            due_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            source TEXT NOT NULL DEFAULT 'scheduler',
            note TEXT,
            acknowledged_at TEXT,
            snoozed_until TEXT,
            completed_at TEXT,
            skipped_at TEXT,
            skip_reason TEXT,
            team_member TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kyc_acknowledgements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            snooze_minutes INTEGER,
            actor_user_id TEXT,
            actor_email TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES kyc_inspection_events(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS kyc_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            action TEXT NOT NULL,
            actor_user_id TEXT,
            actor_email TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES kyc_inspection_events(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_kyc_events_status_due ON kyc_inspection_events (status, due_at);
        CREATE INDEX IF NOT EXISTS idx_kyc_events_created ON kyc_inspection_events (created_at);
        CREATE INDEX IF NOT EXISTS idx_kyc_ack_event ON kyc_acknowledgements (event_id);
        CREATE INDEX IF NOT EXISTS idx_kyc_audit_event ON kyc_audit_log (event_id);
        """
    )


class KycRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path

    def settings(self) -> KycSettings:
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            row = db.execute("SELECT * FROM kyc_settings WHERE id = 1").fetchone()
            if row is None:
                settings = KycSettings(updated_at=utc_now_iso())
                data = _model_dump(settings)
                db.execute(
                    """
                    INSERT INTO kyc_settings (
                        id, enabled, reminder_interval_minutes, active_hours_start,
                        active_hours_end, strict_mode, escalation_enabled,
                        escalation_after_missed, escalation_recipients,
                        last_inspection_at, phone_team_members, remember_account,
                        account_alias, updated_at
                    )
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._settings_params(data),
                )
                return settings
        return self._settings_from_row(row_to_dict(row) or {})

    def save_settings(self, settings: KycSettings) -> KycSettings:
        updated = _model_copy(settings, {"updated_at": utc_now_iso()})
        data = _model_dump(updated)
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            db.execute(
                """
                INSERT INTO kyc_settings (
                    id, enabled, reminder_interval_minutes, active_hours_start,
                    active_hours_end, strict_mode, escalation_enabled,
                    escalation_after_missed, escalation_recipients,
                    last_inspection_at, phone_team_members, remember_account,
                    account_alias, updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    enabled = excluded.enabled,
                    reminder_interval_minutes = excluded.reminder_interval_minutes,
                    active_hours_start = excluded.active_hours_start,
                    active_hours_end = excluded.active_hours_end,
                    strict_mode = excluded.strict_mode,
                    escalation_enabled = excluded.escalation_enabled,
                    escalation_after_missed = excluded.escalation_after_missed,
                    escalation_recipients = excluded.escalation_recipients,
                    last_inspection_at = excluded.last_inspection_at,
                    phone_team_members = excluded.phone_team_members,
                    remember_account = excluded.remember_account,
                    account_alias = excluded.account_alias,
                    updated_at = excluded.updated_at
                """,
                self._settings_params(data),
            )
        self._mirror("kyc_settings", {**data, "id": 1})
        return updated

    def create_event(self, *, due_at: str, source: str, note: str | None = None) -> KycEvent:
        now = utc_now_iso()
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            cursor = db.execute(
                """
                INSERT INTO kyc_inspection_events (due_at, status, source, note, created_at, updated_at)
                VALUES (?, 'pending', ?, ?, ?, ?)
                """,
                (due_at, source, note, now, now),
            )
            event_id = int(cursor.lastrowid)
        event = self.event(event_id)
        if event is None:
            raise RuntimeError("KYC event was not persisted.")
        self._mirror("kyc_inspection_events", _model_dump(event))
        return event

    def event(self, event_id: int) -> KycEvent | None:
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            row = db.execute("SELECT * FROM kyc_inspection_events WHERE id = ?", (event_id,)).fetchone()
        return self._event_from_row(row_to_dict(row)) if row else None

    def current_event(self) -> KycEvent | None:
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            row = db.execute(
                """
                SELECT * FROM kyc_inspection_events
                WHERE status IN ('pending', 'acknowledged', 'snoozed')
                ORDER BY due_at ASC, id ASC
                LIMIT 1
                """
            ).fetchone()
        return self._event_from_row(row_to_dict(row)) if row else None

    def list_events(self, *, limit: int = 100) -> list[KycEvent]:
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            rows = db.execute(
                """
                SELECT * FROM kyc_inspection_events
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [self._event_from_row(row_to_dict(row) or {}) for row in rows]

    def update_event(self, event_id: int, fields: dict[str, Any]) -> KycEvent:
        if not fields:
            event = self.event(event_id)
            if event is None:
                raise KeyError(event_id)
            return event
        allowed = {
            "status",
            "acknowledged_at",
            "snoozed_until",
            "completed_at",
            "skipped_at",
            "skip_reason",
            "team_member",
            "note",
        }
        update_fields = {key: value for key, value in fields.items() if key in allowed}
        update_fields["updated_at"] = utc_now_iso()
        assignments = ", ".join(f"{key} = ?" for key in update_fields)
        values = list(update_fields.values()) + [event_id]
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            cursor = db.execute(
                f"UPDATE kyc_inspection_events SET {assignments} WHERE id = ?",
                values,
            )
            if cursor.rowcount == 0:
                raise KeyError(event_id)
        event = self.event(event_id)
        if event is None:
            raise KeyError(event_id)
        self._mirror("kyc_inspection_events", _model_dump(event))
        return event

    def record_acknowledgement(
        self,
        *,
        event_id: int,
        action: str,
        reason: str | None,
        snooze_minutes: int | None,
        actor_user_id: str | int | None,
        actor_email: str | None,
    ) -> None:
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            db.execute(
                """
                INSERT INTO kyc_acknowledgements (
                    event_id, action, reason, snooze_minutes,
                    actor_user_id, actor_email, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    action,
                    reason,
                    snooze_minutes,
                    str(actor_user_id) if actor_user_id is not None else None,
                    actor_email,
                    utc_now_iso(),
                ),
            )

    def record_audit(
        self,
        *,
        action: str,
        event_id: int | None,
        actor_user_id: str | int | None,
        actor_email: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = metadata or {}
        with managed_connect(self.db_path) as db:
            ensure_kyc_schema(db)
            db.execute(
                """
                INSERT INTO kyc_audit_log (
                    event_id, action, actor_user_id, actor_email, metadata, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    action,
                    str(actor_user_id) if actor_user_id is not None else None,
                    actor_email,
                    _json(payload),
                    utc_now_iso(),
                ),
            )

    def missed_count(self) -> int:
        now = datetime.now(UTC)
        count = 0
        for event in self.list_events(limit=500):
            if event.status not in {"pending", "acknowledged", "snoozed"}:
                continue
            compare_at = _parse_dt(event.snoozed_until if event.status == "snoozed" else event.due_at)
            if compare_at and compare_at < now:
                count += 1
        return count

    def _settings_params(self, data: dict[str, Any]) -> tuple[Any, ...]:
        return (
            1 if data.get("enabled") else 0,
            int(data.get("reminder_interval_minutes") or 15),
            data.get("active_hours_start") or "00:00",
            data.get("active_hours_end") or "23:59",
            1 if data.get("strict_mode") else 0,
            1 if data.get("escalation_enabled") else 0,
            int(data.get("escalation_after_missed") or 2),
            _json(data.get("escalation_recipients") or []),
            data.get("last_inspection_at"),
            _json(data.get("phone_team_members") or []),
            1 if data.get("remember_account") else 0,
            data.get("account_alias"),
            data.get("updated_at") or utc_now_iso(),
        )

    def _settings_from_row(self, row: dict[str, Any]) -> KycSettings:
        return KycSettings(
            enabled=bool(row.get("enabled")),
            reminder_interval_minutes=int(row.get("reminder_interval_minutes") or 15),
            active_hours_start=row.get("active_hours_start") or "00:00",
            active_hours_end=row.get("active_hours_end") or "23:59",
            strict_mode=bool(row.get("strict_mode")),
            escalation_enabled=bool(row.get("escalation_enabled")),
            escalation_after_missed=int(row.get("escalation_after_missed") or 2),
            escalation_recipients=_decode(row.get("escalation_recipients"), []),
            last_inspection_at=row.get("last_inspection_at"),
            phone_team_members=_decode(row.get("phone_team_members"), []),
            remember_account=bool(row.get("remember_account")),
            account_alias=row.get("account_alias"),
            updated_at=row.get("updated_at"),
        )

    def _event_from_row(self, row: dict[str, Any] | None) -> KycEvent:
        if not row:
            raise KeyError("Missing KYC event row")
        return KycEvent(**row)

    def _mirror(self, table: str, payload: dict[str, Any]) -> None:
        url = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            return
        try:
            import httpx

            headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            }
            mirrored = dict(payload)
            mirrored["app_version"] = __version__
            endpoint = f"{url}/rest/v1/{table}?on_conflict=id"
            with httpx.Client(timeout=5) as client:
                response = client.post(endpoint, json=mirrored, headers=headers)
            if response.status_code not in (200, 201, 204):
                _log.warning("Supabase: KYC mirror failed table=%s status=%s", table, response.status_code)
        except Exception as exc:
            _log.warning("Supabase: KYC mirror skipped after error: %s", exc)

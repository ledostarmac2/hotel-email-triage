from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DEFAULT_TEAM_MEMBERS = ["Hyun Song", "Eleanor Green", "Dakota Weglarz", "Brian Tarabocchia"]

KycEventStatus = Literal["pending", "acknowledged", "snoozed", "completed", "skipped", "expired"]
KycAction = Literal["acknowledge", "snooze", "complete", "skip"]


class KycSettings(BaseModel):
    enabled: bool = True
    reminder_interval_minutes: int = Field(default=15, ge=1, le=240)
    active_hours_start: str = Field(default="00:00", pattern=r"^\d{2}:\d{2}$")
    active_hours_end: str = Field(default="23:59", pattern=r"^\d{2}:\d{2}$")
    strict_mode: bool = False
    escalation_enabled: bool = False
    escalation_after_missed: int = Field(default=2, ge=1, le=20)
    escalation_recipients: list[str] = Field(default_factory=list, max_length=20)
    last_inspection_at: str | None = None
    phone_team_members: list[str] = Field(default_factory=lambda: list(DEFAULT_TEAM_MEMBERS), max_length=20)
    remember_account: bool = False
    account_alias: str | None = Field(default=None, max_length=120)
    updated_at: str | None = None


class KycSettingsUpdate(BaseModel):
    enabled: bool | None = None
    reminder_interval_minutes: int | None = Field(default=None, ge=1, le=240)
    active_hours_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    active_hours_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    strict_mode: bool | None = None
    escalation_enabled: bool | None = None
    escalation_after_missed: int | None = Field(default=None, ge=1, le=20)
    escalation_recipients: list[str] | None = Field(default=None, max_length=20)
    last_inspection_at: str | None = None
    phone_team_members: list[str] | None = Field(default=None, max_length=20)
    remember_account: bool | None = None
    account_alias: str | None = Field(default=None, max_length=120)


class KycEventCreate(BaseModel):
    due_at: str | None = None
    source: str = Field(default="manual", max_length=40)
    note: str | None = Field(default=None, max_length=500)


class KycActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    snooze_minutes: int | None = Field(default=None, ge=1, le=240)
    team_member: str | None = Field(default=None, max_length=120)


class KycEvent(BaseModel):
    id: int
    due_at: str
    status: KycEventStatus
    source: str
    note: str | None = None
    acknowledged_at: str | None = None
    snoozed_until: str | None = None
    completed_at: str | None = None
    skipped_at: str | None = None
    skip_reason: str | None = None
    team_member: str | None = None
    created_at: str
    updated_at: str


class KycStatus(BaseModel):
    settings: KycSettings
    current_event: KycEvent | None = None
    next_due_at: str | None = None
    overdue: bool = False
    requires_acknowledgement: bool = False
    missed_count: int = 0
    escalation_due: bool = False


class KycHistory(BaseModel):
    events: list[KycEvent]

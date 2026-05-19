from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..config import get_settings
from .models import KycActionRequest, KycEventCreate, KycHistory, KycSettingsUpdate
from .service import KycService

router = APIRouter(prefix="/api/kyc", tags=["kyc"])


def _actor(request: Request) -> tuple[str | int | None, str | None]:
    user = getattr(request.state, "user", None) or {}
    return user.get("id"), user.get("email")


def _service() -> KycService:
    return KycService(get_settings().database_path)


@router.get("/config")
def get_kyc_config() -> dict:
    return {"settings": _service().get_settings()}


@router.put("/config")
def update_kyc_config(payload: KycSettingsUpdate, request: Request) -> dict:
    actor_user_id, actor_email = _actor(request)
    settings = _service().update_settings(payload, actor_user_id=actor_user_id, actor_email=actor_email)
    return {"settings": settings}


@router.get("/status")
def get_kyc_status() -> dict:
    return {"status": _service().status()}


@router.post("/reminders")
def create_kyc_reminder(payload: KycEventCreate, request: Request) -> dict:
    actor_user_id, actor_email = _actor(request)
    event = _service().create_event(payload, actor_user_id=actor_user_id, actor_email=actor_email)
    return {"event": event}


@router.get("/history")
def get_kyc_history(limit: int = Query(default=100, ge=1, le=500)) -> KycHistory:
    return KycHistory(events=_service().history(limit=limit))


@router.post("/events/{event_id}/acknowledge")
def acknowledge_kyc_event(event_id: int, payload: KycActionRequest, request: Request) -> dict:
    return _run_action("acknowledge", event_id, payload, request)


@router.post("/events/{event_id}/snooze")
def snooze_kyc_event(event_id: int, payload: KycActionRequest, request: Request) -> dict:
    return _run_action("snooze", event_id, payload, request)


@router.post("/events/{event_id}/complete")
def complete_kyc_event(event_id: int, payload: KycActionRequest, request: Request) -> dict:
    return _run_action("complete", event_id, payload, request)


@router.post("/events/{event_id}/skip")
def skip_kyc_event(event_id: int, payload: KycActionRequest, request: Request) -> dict:
    return _run_action("skip", event_id, payload, request)


def _run_action(action: str, event_id: int, payload: KycActionRequest, request: Request) -> dict:
    actor_user_id, actor_email = _actor(request)
    service = _service()
    try:
        if action == "acknowledge":
            event = service.acknowledge(event_id, payload, actor_user_id=actor_user_id, actor_email=actor_email)
        elif action == "snooze":
            event = service.snooze(event_id, payload, actor_user_id=actor_user_id, actor_email=actor_email)
        elif action == "complete":
            event = service.complete(event_id, payload, actor_user_id=actor_user_id, actor_email=actor_email)
        elif action == "skip":
            event = service.skip(event_id, payload, actor_user_id=actor_user_id, actor_email=actor_email)
        else:
            raise HTTPException(status_code=400, detail="Unsupported KYC action.")
    except KeyError:
        raise HTTPException(status_code=404, detail="KYC reminder event not found.") from None
    return {"event": event}

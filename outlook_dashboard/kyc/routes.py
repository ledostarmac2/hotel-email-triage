from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from ..config import get_settings
from .models import KycActionRequest, KycEventCreate, KycHistory, KycSettingsUpdate
from .service import KycService

_log = logging.getLogger("kyc.routes")

router = APIRouter(prefix="/api/kyc", tags=["kyc"])


def _actor(request: Request) -> tuple[str | int | None, str | None]:
    user = getattr(request.state, "user", None) or {}
    return user.get("id"), user.get("email")


def _service() -> KycService:
    return KycService(get_settings().database_path)


@router.get("/config")
def get_kyc_config() -> dict:
    try:
        return {"settings": _service().get_settings()}
    except Exception as exc:
        _log.error("kyc get_config failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not load KYC configuration.") from exc


@router.put("/config")
def update_kyc_config(payload: KycSettingsUpdate, request: Request) -> dict:
    actor_user_id, actor_email = _actor(request)
    try:
        settings = _service().update_settings(payload, actor_user_id=actor_user_id, actor_email=actor_email)
        return {"settings": settings}
    except Exception as exc:
        _log.error("kyc update_config failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not update KYC configuration.") from exc


@router.get("/status")
def get_kyc_status() -> dict:
    try:
        return {"status": _service().status()}
    except Exception as exc:
        _log.error("kyc get_status failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not retrieve KYC status.") from exc


@router.post("/reminders")
def create_kyc_reminder(payload: KycEventCreate, request: Request) -> dict:
    actor_user_id, actor_email = _actor(request)
    try:
        event = _service().create_event(payload, actor_user_id=actor_user_id, actor_email=actor_email)
        return {"event": event}
    except Exception as exc:
        _log.error("kyc create_reminder failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not create KYC reminder.") from exc


@router.get("/history")
def get_kyc_history(limit: int = Query(default=100, ge=1, le=500)) -> KycHistory:
    try:
        return KycHistory(events=_service().history(limit=limit))
    except Exception as exc:
        _log.error("kyc get_history failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not retrieve KYC history.") from exc


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
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=404, detail="KYC reminder event not found.") from None
    except Exception as exc:
        _log.error("kyc action=%s event_id=%s failed: %s", action, event_id, exc)
        raise HTTPException(status_code=500, detail="KYC action could not be completed. Please try again.") from exc
    return {"event": event}

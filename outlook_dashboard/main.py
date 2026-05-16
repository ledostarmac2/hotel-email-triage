from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .ai import analyze_email
from .config import get_settings
from .database import (
    email_count,
    emails_without_analysis,
    get_email,
    initialize_database,
    list_emails,
    record_sync_run,
    save_analysis,
    update_status,
    upsert_email,
)
from .graph import (
    GRAPH_FIELDS,
    GraphAuthenticationError,
    GraphConfigurationError,
    authorization_url,
    exchange_callback_code,
    fetch_recent_messages,
)
from .mock_data import build_mock_emails
from .taxonomy import CATEGORIES, PRIORITY_LEVELS, RISK_FLAGS, STATUSES


STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    initialize_database(settings.database_path)
    if settings.auto_seed_mock and email_count(settings.database_path) == 0:
        _seed_mock(settings, analyze=True)
    yield


app = FastAPI(
    title="Luxury Hotel Outlook Email Intelligence",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class StatusUpdate(BaseModel):
    status: str


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "ok": True,
        "read_only_outlook": True,
        "graph_configured": settings.graph_configured,
        "openai_configured": settings.openai_configured,
        "database_path": str(settings.database_path),
    }


@app.get("/api/config")
def config() -> dict[str, object]:
    settings = get_settings()
    return {
        "shared_mailbox_email": settings.shared_mailbox_email,
        "graph_configured": settings.graph_configured,
        "openai_configured": settings.openai_configured,
        "required_graph_fields": GRAPH_FIELDS,
        "required_graph_permissions": ["Mail.Read", "Mail.Read.Shared"],
        "read_only_outlook": True,
    }


@app.get("/api/taxonomy")
def taxonomy() -> dict[str, list[str]]:
    return {
        "categories": CATEGORIES,
        "priorities": PRIORITY_LEVELS,
        "risk_flags": RISK_FLAGS,
        "statuses": STATUSES,
    }


@app.get("/auth/login")
def auth_login(mode: Literal["personal", "shared"] = "shared") -> RedirectResponse:
    settings = get_settings()
    try:
        return RedirectResponse(authorization_url(settings, mode))
    except GraphConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/auth/callback")
def auth_callback(code: str | None = None, state: str | None = None, error: str | None = None) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not code or not state:
        raise HTTPException(status_code=400, detail="OAuth callback is missing code or state.")
    settings = get_settings()
    try:
        exchange_callback_code(settings, code, state)
    except (GraphAuthenticationError, GraphConfigurationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse("/")


@app.post("/api/mock/seed")
def seed_mock() -> dict[str, object]:
    settings = get_settings()
    return _seed_mock(settings, analyze=True)


@app.post("/api/sync/outlook")
def sync_outlook(
    mode: Literal["personal", "shared"] = "shared",
    top: int = Query(default=25, ge=1, le=50),
    analyze: bool = True,
) -> dict[str, object]:
    settings = get_settings()
    try:
        messages = fetch_recent_messages(settings, mode, top=top)
        result = _store_and_optionally_analyze(messages, settings, analyze=analyze)
        record_sync_run(
            source="outlook",
            mailbox_mode=mode,
            fetched_count=len(messages),
            inserted_count=result["inserted_count"],
            updated_count=result["updated_count"],
            analyzed_count=result["analyzed_count"],
            db_path=settings.database_path,
        )
        return {
            "source": "outlook",
            "mode": mode,
            "fetched_count": len(messages),
            **result,
            "read_only_outlook": True,
        }
    except (GraphAuthenticationError, GraphConfigurationError) as exc:
        record_sync_run(
            source="outlook",
            mailbox_mode=mode,
            fetched_count=0,
            inserted_count=0,
            updated_count=0,
            analyzed_count=0,
            error=str(exc),
            db_path=settings.database_path,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ai/process-pending")
def process_pending(limit: int = Query(default=25, ge=1, le=100)) -> dict[str, int]:
    settings = get_settings()
    pending = emails_without_analysis(limit=limit, db_path=settings.database_path)
    analyzed = 0
    for email in pending:
        save_analysis(email["id"], analyze_email(email, settings), db_path=settings.database_path)
        analyzed += 1
    return {"analyzed_count": analyzed}


@app.get("/api/emails")
def api_list_emails(
    category: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    risk: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    settings = get_settings()
    emails = list_emails(
        category=category or None,
        priority=priority or None,
        status=status or None,
        risk=risk or None,
        query=q or None,
        limit=limit,
        db_path=settings.database_path,
    )
    return {"emails": emails, "count": len(emails)}


@app.get("/api/emails/{email_id}")
def api_get_email(email_id: int) -> dict[str, object]:
    settings = get_settings()
    email = get_email(email_id, db_path=settings.database_path)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found.")
    return {"email": email}


@app.post("/api/emails/{email_id}/analyze")
def api_analyze_email(email_id: int) -> dict[str, object]:
    settings = get_settings()
    email = get_email(email_id, db_path=settings.database_path)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found.")
    analysis = analyze_email(email, settings)
    save_analysis(email_id, analysis, db_path=settings.database_path)
    return {"email": get_email(email_id, db_path=settings.database_path)}


@app.patch("/api/emails/{email_id}/status")
def api_update_status(email_id: int, update: StatusUpdate) -> dict[str, object]:
    settings = get_settings()
    try:
        update_status(email_id, update.status, db_path=settings.database_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Email not found.") from exc
    return {"email": get_email(email_id, db_path=settings.database_path), "read_only_outlook": True}


def _seed_mock(settings, analyze: bool) -> dict[str, object]:
    messages = build_mock_emails()
    result = _store_and_optionally_analyze(messages, settings, analyze=analyze)
    record_sync_run(
        source="mock",
        mailbox_mode="mock",
        fetched_count=len(messages),
        inserted_count=result["inserted_count"],
        updated_count=result["updated_count"],
        analyzed_count=result["analyzed_count"],
        db_path=settings.database_path,
    )
    return {"source": "mock", "fetched_count": len(messages), **result}


def _store_and_optionally_analyze(messages, settings, analyze: bool) -> dict[str, int]:
    inserted = 0
    updated = 0
    analyzed = 0
    for message in messages:
        if not message.get("graph_message_id"):
            continue
        email_id, was_inserted = upsert_email(message, db_path=settings.database_path)
        inserted += 1 if was_inserted else 0
        updated += 0 if was_inserted else 1
        if analyze:
            email = get_email(email_id, db_path=settings.database_path)
            if email:
                save_analysis(email_id, analyze_email(email, settings), db_path=settings.database_path)
                analyzed += 1
    return {"inserted_count": inserted, "updated_count": updated, "analyzed_count": analyzed}

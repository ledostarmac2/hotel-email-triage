from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import time

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .ai import analyze_email, triage_email, urgency_score
from .config import DATA_DIR, get_settings
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
from .outlook_desktop import OutlookDesktopExportError, export_mailbox_folder_to_msg
from .runtime_log import configure as _configure_runtime_log
from .runtime_log import get_logger
from .taxonomy import CATEGORIES, PRIORITY_LEVELS, RISK_FLAGS, STATUSES


STATIC_DIR = Path(__file__).resolve().parent / "static"


_log = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _configure_runtime_log(DATA_DIR)
    settings = get_settings()
    _log.info(
        "Server starting: host=%s port=%s db=%s openai=%s graph=%s",
        settings.app_host,
        settings.app_port,
        settings.database_path,
        settings.openai_configured,
        settings.graph_configured,
    )
    initialize_database(settings.database_path)
    if settings.auto_seed_mock and email_count(settings.database_path) == 0:
        _seed_mock(settings, analyze=True)
    yield
    _log.info("Server shutdown.")


_http_log = get_logger("http")


class _RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _http_log.error(
                "%s %s — UNHANDLED %s (%.0f ms)",
                request.method, request.url.path, type(exc).__name__, elapsed_ms,
                exc_info=True,
            )
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        level = 30 if response.status_code >= 400 else 20  # WARNING vs INFO
        _http_log.log(
            level,
            "%s %s%s — %s (%.0f ms)",
            request.method,
            request.url.path,
            f"?{request.url.query}" if request.url.query else "",
            response.status_code,
            elapsed_ms,
        )
        return response


app = FastAPI(
    title="Luxury Hotel Outlook Email Intelligence",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(_RequestLogMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class StatusUpdate(BaseModel):
    status: str


class DesktopOutlookMessage(BaseModel):
    graph_message_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    from_name: str | None = None
    from_email: str | None = None
    received_datetime: str | None = None
    body_preview: str | None = None
    body_content_type: str | None = "text"
    body_content: str | None = None
    body_text: str | None = None
    conversation_id: str | None = None
    importance: str | None = "normal"
    has_attachments: bool = False


class DesktopOutlookImport(BaseModel):
    mailbox: str = "NYCWA_Reservations"
    folder: str = "Inbox"
    messages: list[DesktopOutlookMessage] = Field(default_factory=list)


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
        "outlook_desktop_export": {
            "mailbox": settings.outlook_export_mailbox,
            "folder": settings.outlook_export_folder,
            "export_dir": str(settings.outlook_export_dir),
        },
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


@app.post("/api/outlook-desktop/export-inbox")
def export_outlook_desktop_inbox() -> dict[str, object]:
    settings = get_settings()
    _log.info(
        "Outlook export requested: mailbox=%s folder=%s macro=%s",
        settings.outlook_export_mailbox,
        settings.outlook_export_folder,
        settings.outlook_export_macro,
    )
    try:
        result = export_mailbox_folder_to_msg(
            settings.outlook_export_mailbox,
            settings.outlook_export_folder,
            settings.outlook_export_dir,
            settings.outlook_export_macro,
        )
        _log.info("Outlook export launched macro successfully: %s", settings.outlook_export_macro)
        return {"source": "outlook_desktop", **result}
    except OutlookDesktopExportError as exc:
        _log.error("Outlook export failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/outlook-desktop/import-json")
def import_outlook_desktop_json(payload: DesktopOutlookImport) -> dict[str, object]:
    settings = get_settings()
    messages = [_desktop_message_to_email(message, payload.mailbox, payload.folder) for message in payload.messages]
    result = _store_and_optionally_analyze(messages, settings, analyze=True)
    record_sync_run(
        source="outlook_desktop",
        mailbox_mode="shared",
        fetched_count=len(messages),
        inserted_count=result["inserted_count"],
        updated_count=result["updated_count"],
        analyzed_count=result["analyzed_count"],
        db_path=settings.database_path,
    )
    return {
        "source": "outlook_desktop",
        "mailbox": payload.mailbox,
        "folder": payload.folder,
        "fetched_count": len(messages),
        **result,
    }


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
        save_analysis(email["id"], triage_email(email, settings), db_path=settings.database_path)
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
    emails = [_decorate_email(email) for email in emails]
    emails.sort(key=lambda email: (email["urgency_score"], email.get("received_datetime") or ""), reverse=True)
    return {"emails": emails, "count": len(emails)}


@app.get("/api/emails/{email_id}")
def api_get_email(email_id: int) -> dict[str, object]:
    settings = get_settings()
    email = get_email(email_id, db_path=settings.database_path)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found.")
    return {"email": _decorate_email(email)}


@app.post("/api/emails/{email_id}/analyze")
def api_analyze_email(email_id: int) -> dict[str, object]:
    settings = get_settings()
    email = get_email(email_id, db_path=settings.database_path)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found.")
    _log.info(
        "AI analyze requested: email_id=%s engine=%s",
        email_id,
        "openai" if settings.openai_configured else "heuristic",
    )
    try:
        analysis = analyze_email(email, settings)
    except Exception as exc:
        _log.error("AI analyze failed: email_id=%s error=%s", email_id, exc, exc_info=True)
        raise
    if analysis.get("analysis_error"):
        _log.warning("AI analyze completed with error: email_id=%s error=%s", email_id, analysis["analysis_error"])
    else:
        _log.info("AI analyze succeeded: email_id=%s engine=%s", email_id, analysis.get("analysis_engine"))
    save_analysis(email_id, analysis, db_path=settings.database_path)
    refreshed = get_email(email_id, db_path=settings.database_path)
    return {"email": _decorate_email(refreshed or {})}


@app.patch("/api/emails/{email_id}/status")
def api_update_status(email_id: int, update: StatusUpdate) -> dict[str, object]:
    settings = get_settings()
    try:
        update_status(email_id, update.status, db_path=settings.database_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Email not found.") from exc
    email = get_email(email_id, db_path=settings.database_path)
    return {"email": _decorate_email(email or {}), "read_only_outlook": True}


def _desktop_message_to_email(message: DesktopOutlookMessage, mailbox: str, folder: str) -> dict[str, object]:
    data = message.model_dump() if hasattr(message, "model_dump") else message.dict()
    raw_id = data.get("graph_message_id") or f"{mailbox}:{folder}:{data.get('conversation_id')}:{data.get('received_datetime')}:{data.get('subject')}"
    body = data.get("body_text") or data.get("body_content") or data.get("body_preview") or ""
    preview = data.get("body_preview") or body[:240]
    return {
        **data,
        "graph_message_id": f"outlook-desktop:{raw_id}",
        "body_preview": preview,
        "body_content_type": data.get("body_content_type") or "text",
        "body_content": data.get("body_content") or body,
        "body_text": body,
        "source": "outlook_desktop",
        "mailbox_mode": "shared",
    }


def _decorate_email(email: dict[str, object]) -> dict[str, object]:
    decorated = dict(email)
    decorated["urgency_score"] = urgency_score(decorated)
    decorated["priority_rank"] = decorated["urgency_score"]
    return decorated


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
                save_analysis(email_id, triage_email(email, settings), db_path=settings.database_path)
                analyzed += 1
    return {"inserted_count": inserted, "updated_count": updated, "analyzed_count": analyzed}

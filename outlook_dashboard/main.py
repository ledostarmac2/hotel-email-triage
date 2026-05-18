from __future__ import annotations

import html as html_lib
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .ai import analyze_email, infer_feedback_corrections, triage_conversation, triage_email, urgency_score
from .auth import (
    authenticate_user,
    create_reset_token,
    create_user,
    delete_session,
    delete_user,
    encode_session,
    ensure_admin,
    get_session_user,
    list_users,
    reset_password,
    send_invite_email,
    send_reset_email,
)
from .config import DATA_DIR, get_settings
from .database import (
    admin_correction_stats,
    admin_low_confidence_emails,
    admin_misclassification_drilldowns,
    admin_overview_stats,
    admin_recent_audit_logs,
    consume_reset_token,
    delete_emails_not_in_graph_ids,
    detect_rule_candidates,
    emails_without_analysis,
    get_email,
    initialize_database,
    list_conversation_emails,
    list_emails,
    list_feedback_for_conversation,
    list_recent_triage_feedback,
    record_audit_event,
    record_sync_run,
    save_analysis,
    save_triage_feedback,
    set_rule_candidate_status,
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
from .outlook_desktop import OutlookDesktopExportError, export_mailbox_folder_to_msg
from .platform_compat import HAS_OUTLOOK_COM, HAS_WEBVIEW, HAS_WEBVIEW2_RUNTIME, IS_WINDOWS
from .preferences import clear_remembered_email, remembered_email, save_remembered_email
from .runtime_log import configure as _configure_runtime_log
from .runtime_log import get_logger
from .supabase_client import (
    download_approved_rules,
    download_known_senders,
    download_prompt_versions,
    flush_feedback_queue,
    promote_rule_candidates,
    upload_feedback_event,
)
from .taxonomy import CATEGORIES, CONTACT_TYPES, DEPARTMENT_OWNERS, PRIORITY_LEVELS, RISK_FLAGS, STATUSES
from .local_classifier import invalidate_cache as invalidate_classifier_cache
from .local_classifier import train as train_local_classifier
from .training_pipeline import pipeline_status as training_pipeline_status
from .training_pipeline import run_pipeline as run_training_pipeline
from .updater import get_update_status, start_update_check

STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_VER = str(int(time.time()))

_log = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _configure_runtime_log(DATA_DIR)
    settings = get_settings()
    _log.info(
        "Server starting: host=%s port=%s db=%s openai=%s google_ai=%s graph=%s",
        settings.app_host,
        settings.app_port,
        settings.database_path,
        settings.openai_configured,
        settings.google_ai_configured,
        settings.graph_configured,
    )
    initialize_database(settings.database_path)
    if settings.replyright_admin_email and settings.replyright_admin_password:
        ensure_admin(settings.replyright_admin_email, settings.replyright_admin_password, settings.database_path)
    else:
        _log.warning("Admin account seed skipped: REPLYRIGHT_ADMIN_EMAIL/PASSWORD are not configured.")
    rules = download_approved_rules()
    if rules:
        _log.info("Supabase: loaded %s approved classification rules", len(rules))
    prompts = download_prompt_versions()
    if prompts:
        _log.info("Supabase: loaded %s prompt versions", len(prompts))
    senders = download_known_senders()
    if senders:
        _log.info("Supabase: loaded %s known sender mappings", len(senders))
    flushed = flush_feedback_queue()
    if flushed:
        _log.info("Supabase: flushed %s queued feedback events", flushed)
    start_update_check()
    yield
    _log.info("Server shutdown.")


_http_log = get_logger("http")


_AUTH_SKIP = {
    "/login",
    "/api/health",
    "/reset-password",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
}
_AUTH_SKIP_PREFIX = ("/static/",)
_RATE_LIMIT_PATHS = {
    "/login",
    "/api/auth/login",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
}
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_BUCKETS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


class _RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path not in _RATE_LIMIT_PATHS:
            return await call_next(request)
        settings = get_settings()
        limit = max(0, int(settings.rate_limit_per_minute))
        if limit <= 0:
            return await call_next(request)
        client_host = request.client.host if request.client else "unknown"
        key = (client_host, path)
        now = time.monotonic()
        bucket = _RATE_LIMIT_BUCKETS[key]
        while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        # Prune keys whose window has fully expired to prevent unbounded dict growth.
        stale = [k for k, b in _RATE_LIMIT_BUCKETS.items() if b and now - b[-1] > _RATE_LIMIT_WINDOW_SECONDS]
        for k in stale:
            del _RATE_LIMIT_BUCKETS[k]
        if len(bucket) >= limit:
            return JSONResponse(
                {"detail": "Too many attempts. Please wait before trying again."},
                status_code=429,
            )
        bucket.append(now)
        return await call_next(request)


class _AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _AUTH_SKIP or any(path.startswith(p) for p in _AUTH_SKIP_PREFIX):
            return await call_next(request)
        session_cookie = request.cookies.get("rr_session", "")
        settings = get_settings()
        user = get_session_user(session_cookie, settings.database_path) if session_cookie else None
        if not user:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Authentication required."}, status_code=401)
            return RedirectResponse("/login")
        request.state.user = user
        response = await call_next(request)
        new_access = user.pop("_new_access_token", None)
        new_refresh = user.pop("_new_refresh_token", None)
        if new_access and new_refresh:
            response.set_cookie(
                "rr_session",
                encode_session(new_access, new_refresh),
                httponly=True,
                samesite="lax",
                max_age=60 * 60 * 24 * 30,
                path="/",
            )
        return response


class _RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            _http_log.error(
                "%s %s — UNHANDLED %s (%.0f ms)",
                request.method,
                request.url.path,
                type(exc).__name__,
                elapsed_ms,
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
app.add_middleware(_RateLimitMiddleware)
app.add_middleware(_AuthMiddleware)
app.add_middleware(_RequestLogMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class StatusUpdate(BaseModel):
    status: str


class TriageFeedbackRequest(BaseModel):
    feedback_text: str = Field(min_length=2, max_length=4000)
    corrected_urgency: int | None = Field(default=None, ge=1, le=5)
    corrected_category: str | None = None
    corrected_owner: str | None = None
    corrected_contact_type: str | None = None
    corrected_sentiment: str | None = None
    corrected_status: str | None = None
    summary_quality_rating: int | None = Field(default=None, ge=1, le=5)
    reply_quality_rating: int | None = Field(default=None, ge=1, le=5)


class RuleCandidateStatusRequest(BaseModel):
    key: str = Field(min_length=1, max_length=240)
    status: str = Field(min_length=1, max_length=40)
    type: str | None = Field(default=None, max_length=80)
    pattern: str | None = Field(default=None, max_length=500)
    suggestion: str | None = Field(default=None, max_length=500)


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


@app.get("/login")
def login_page() -> HTMLResponse:
    return _login_response()


@app.post("/login")
def login_form(email: str = Form(...), password: str = Form(...), remember_email: str | None = Form(None)):
    settings = get_settings()
    user = authenticate_user(email, password, settings.database_path)
    if not user:
        response = _login_response(
            "Invalid email or password.", email, status_code=401, remember_checked=bool(remember_email)
        )
        _apply_remembered_email(response, email, bool(remember_email))
        return response
    access_token = user.pop("_access_token", "")
    refresh_token = user.pop("_refresh_token", "")
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "rr_session",
        encode_session(access_token, refresh_token),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    _apply_remembered_email(response, email, bool(remember_email))
    return response


def _login_response(
    error_message: str = "",
    email: str = "",
    status_code: int = 200,
    *,
    remember_checked: bool | None = None,
) -> HTMLResponse:
    html = (STATIC_DIR / "login.html").read_text(encoding="utf-8")
    stored_email = remembered_email()
    display_email = email.strip() or stored_email
    checked = bool(display_email) if remember_checked is None else remember_checked
    html = html.replace(
        'data-server-error=""',
        f'data-server-error="{html_lib.escape(error_message, quote=True)}"',
    )
    html = html.replace(
        'value="" data-server-email',
        f'value="{html_lib.escape(display_email, quote=True)}" data-server-email',
    )
    html = html.replace(
        '<input type="checkbox" id="rememberEmail" name="remember_email" value="1" />',
        (
            '<input type="checkbox" id="rememberEmail" name="remember_email" value="1" checked />'
            if checked
            else '<input type="checkbox" id="rememberEmail" name="remember_email" value="1" />'
        ),
    )
    return HTMLResponse(content=html, status_code=status_code, headers={"Cache-Control": "no-store"})


def _apply_remembered_email(response, email: str, should_remember: bool) -> None:
    normalized = email.lower().strip()
    if should_remember and normalized:
        save_remembered_email(normalized)
        response.set_cookie("rr_remembered_email", normalized, max_age=60 * 60 * 24 * 365, samesite="lax", path="/")
    else:
        clear_remembered_email()
        response.delete_cookie("rr_remembered_email", path="/")


@app.get("/reset-password")
def reset_password_page() -> HTMLResponse:
    html = (STATIC_DIR / "reset_password.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


@app.get("/")
def dashboard() -> HTMLResponse:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace("/static/app.js?v=2", f"/static/app.js?v={_STATIC_VER}")
    html = html.replace("/static/styles.css?v=2", f"/static/styles.css?v={_STATIC_VER}")
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


# ── Auth endpoints ────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


class InviteRequest(BaseModel):
    email: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


@app.post("/api/auth/login")
def api_login(payload: LoginRequest, request: Request):
    settings = get_settings()
    user = authenticate_user(payload.email, payload.password, settings.database_path)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    access_token = user.pop("_access_token", "")
    refresh_token = user.pop("_refresh_token", "")
    record_audit_event(
        action="auth.login",
        actor_user_id=None,
        actor_email=str(user["email"]),
        entity_type="user",
        entity_id=str(user["id"]),
        metadata={"role": user["role"]},
        db_path=settings.database_path,
    )
    response = JSONResponse({"ok": True, "role": user["role"], "email": user["email"]})
    response.set_cookie(
        "rr_session",
        encode_session(access_token, refresh_token),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.post("/api/auth/logout")
def api_logout(request: Request):
    session_cookie = request.cookies.get("rr_session", "")
    if session_cookie:
        delete_session(session_cookie, get_settings().database_path)
    response = JSONResponse({"ok": True})
    response.delete_cookie("rr_session")
    return response


@app.get("/api/auth/me")
def api_me(request: Request):
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return {"user": request.state.user}


@app.post("/api/auth/forgot-password")
def api_forgot_password(payload: ForgotPasswordRequest):
    settings = get_settings()
    if not settings.smtp_configured:
        raise HTTPException(status_code=503, detail="Email service not configured. Contact your admin.")
    token = create_reset_token(payload.email.lower().strip(), settings.database_path)
    if token:
        base_url = f"http://{settings.app_host}:{settings.app_port}"
        try:
            send_reset_email(payload.email.lower().strip(), token, base_url, settings)
        except Exception as exc:
            _log.error("Reset email failed for %s: %s", payload.email, exc)
            raise HTTPException(status_code=503, detail="Failed to send email. Contact your admin.") from exc
    return {"ok": True}


@app.post("/api/auth/reset-password")
def api_reset_password_confirm(payload: ResetPasswordConfirmRequest):
    settings = get_settings()
    user_id = consume_reset_token(payload.token, settings.database_path)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    reset_password(user_id, payload.new_password, settings.database_path)
    return {"ok": True}


@app.post("/api/auth/invite")
def api_invite(payload: InviteRequest, request: Request):
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    if not settings.smtp_configured:
        raise HTTPException(status_code=503, detail="Email service not configured. Add SMTP settings to .env.")
    try:
        user_id = create_user(
            payload.email,
            secrets.token_hex(32),  # placeholder — user sets their own password via invite link
            role="user",
            invited_by_id=request.state.user["id"],
            db_path=settings.database_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = create_reset_token(payload.email, settings.database_path, hours=24)
    if not token:
        raise HTTPException(status_code=500, detail="Could not generate invite token.")
    base_url = f"http://{settings.app_host}:{settings.app_port}"
    try:
        send_invite_email(payload.email, token, base_url, settings)
    except Exception as exc:
        _log.error("Invite email failed for %s: %s", payload.email, exc)
        raise HTTPException(
            status_code=503, detail="User created but invite email failed. Check SMTP settings."
        ) from exc
    return {"ok": True, "user_id": user_id}


@app.get("/api/auth/users")
def api_list_users(request: Request):
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    return {"users": list_users(get_settings().database_path)}


@app.delete("/api/auth/users/{user_id}")
def api_delete_user(user_id: str, request: Request):
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    if user_id == request.state.user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")
    delete_user(user_id, get_settings().database_path)
    return {"ok": True}


@app.post("/api/auth/users/{user_id}/reset-password")
def api_reset_password(user_id: str, payload: ResetPasswordRequest, request: Request):
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    reset_password(user_id, payload.new_password, get_settings().database_path)
    return {"ok": True}


# ── Admin analytics ───────────────────────────────────────────────────────────


@app.get("/api/admin/stats")
def api_admin_stats(request: Request):
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    return {
        "overview": admin_overview_stats(settings.database_path),
        "corrections": admin_correction_stats(settings.database_path),
        "misclassification_drilldowns": admin_misclassification_drilldowns(settings.database_path),
        "low_confidence": admin_low_confidence_emails(db_path=settings.database_path),
        "rule_candidates": detect_rule_candidates(settings.database_path),
        "audit_logs": admin_recent_audit_logs(db_path=settings.database_path),
    }


@app.get("/api/admin/training/status")
def api_training_status(request: Request) -> dict[str, object]:
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    return training_pipeline_status(db_path=get_settings().database_path)


@app.post("/api/admin/training/run")
def api_training_run(request: Request, batch_size: int = 10, refine: bool = False) -> dict[str, object]:
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    result = run_training_pipeline(batch_size=batch_size, refine=refine, db_path=settings.database_path)
    record_audit_event(
        action="training.pipeline.run",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="training_pipeline",
        entity_id=None,
        metadata=result,
        db_path=settings.database_path,
    )
    return result


@app.post("/api/admin/classifier/train")
def api_classifier_train(request: Request) -> dict[str, object]:
    """Train local scikit-learn classifiers from Supabase training_examples."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    result = train_local_classifier(db_path=get_settings().database_path)
    invalidate_classifier_cache()
    record_audit_event(
        action="classifier.train",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="local_classifier",
        entity_id=None,
        metadata=result,
        db_path=get_settings().database_path,
    )
    return result


@app.get("/api/admin/training/examples")
def api_training_examples(request: Request, limit: int = 20) -> dict[str, object]:
    """Return unreviewed training examples from Supabase for the human-review queue."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        return {"examples": [], "error": "Supabase not configured"}
    try:
        import httpx
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }
        r = httpx.get(
            f"{url}/rest/v1/training_examples",
            params={"human_reviewed": "eq.false", "select": "*", "order": "created_at.desc", "limit": str(limit)},
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            return {"examples": r.json()}
        return {"examples": [], "error": f"Supabase error {r.status_code}"}
    except Exception as exc:
        return {"examples": [], "error": str(exc)[:200]}


@app.patch("/api/admin/training/examples/{example_id}/review")
def api_mark_training_reviewed(example_id: str, request: Request) -> dict[str, object]:
    """Mark a training example as human-reviewed in Supabase."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        import httpx
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        r = httpx.patch(
            f"{url}/rest/v1/training_examples",
            params={"id": f"eq.{example_id}"},
            json={"human_reviewed": True},
            headers=headers,
            timeout=10,
        )
        if r.status_code not in (200, 204):
            raise HTTPException(status_code=502, detail=f"Supabase error {r.status_code}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:200]) from exc
    record_audit_event(
        action="training.example.reviewed",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="training_example",
        entity_id=example_id,
        metadata={"human_reviewed": True},
        db_path=get_settings().database_path,
    )
    return {"ok": True, "id": example_id}


@app.post("/api/rule-candidates/status")
def api_set_rule_candidate_status(payload: RuleCandidateStatusRequest, request: Request) -> dict[str, object]:
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    try:
        set_rule_candidate_status(
            payload.key,
            payload.status,
            candidate_type=payload.type or "manual",
            pattern=payload.pattern or "",
            suggestion=payload.suggestion or "",
            db_path=settings.database_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        action="rule_candidate.status",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="rule_candidate",
        entity_id=payload.key,
        metadata={"status": payload.status, "type": payload.type or "manual"},
        db_path=settings.database_path,
    )
    candidates = detect_rule_candidates(settings.database_path)
    return {"ok": True, "rule_candidates": candidates, "count": len(candidates)}


@app.get("/api/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "ok": True,
        "read_only_outlook": True,
        "graph_configured": settings.graph_configured,
        "openai_configured": settings.openai_configured,
        "openai_model": settings.openai_model if settings.openai_configured else "",
        "google_ai_configured": settings.google_ai_configured,
        "google_ai_model": settings.google_ai_model if settings.google_ai_configured else "",
        "anthropic_configured": settings.anthropic_configured,
        "anthropic_model": settings.anthropic_model if settings.anthropic_configured else "",
        "database_path": str(settings.database_path),
        "platform": {
            "is_windows": IS_WINDOWS,
            "has_outlook_com": HAS_OUTLOOK_COM,
            "has_webview": HAS_WEBVIEW,
            "has_webview2_runtime": HAS_WEBVIEW2_RUNTIME,
        },
        "config_warnings": settings.runtime_warnings,
    }


@app.get("/api/config")
def config() -> dict[str, object]:
    settings = get_settings()
    return {
        "shared_mailbox_email": settings.shared_mailbox_email,
        "graph_configured": settings.graph_configured,
        "openai_configured": settings.openai_configured,
        "openai_model": settings.openai_model if settings.openai_configured else "",
        "google_ai_configured": settings.google_ai_configured,
        "google_ai_model": settings.google_ai_model if settings.google_ai_configured else "",
        "anthropic_configured": settings.anthropic_configured,
        "anthropic_model": settings.anthropic_model if settings.anthropic_configured else "",
        "required_graph_fields": GRAPH_FIELDS,
        "required_graph_permissions": ["Mail.Read", "Mail.Read.Shared"],
        "read_only_outlook": True,
        "platform": {
            "is_windows": IS_WINDOWS,
            "has_outlook_com": HAS_OUTLOOK_COM,
            "has_webview": HAS_WEBVIEW,
            "has_webview2_runtime": HAS_WEBVIEW2_RUNTIME,
        },
        "outlook_desktop_export": {
            "mailbox": settings.outlook_export_mailbox,
            "folder": settings.outlook_export_folder,
            "export_dir": str(settings.outlook_export_dir),
        },
        "config_warnings": settings.runtime_warnings,
    }


@app.get("/api/update-available")
def update_available() -> dict[str, object]:
    status = get_update_status()
    return {
        "available": bool(status.get("available")),
        "version": status.get("version") or "",
        "url": status.get("url") or "",
        "checked": bool(status.get("checked")),
    }


@app.get("/api/taxonomy")
def taxonomy() -> dict[str, list[str]]:
    return {
        "categories": CATEGORIES,
        "priorities": PRIORITY_LEVELS,
        "risk_flags": RISK_FLAGS,
        "statuses": STATUSES,
        "contact_types": CONTACT_TYPES,
        "department_owners": DEPARTMENT_OWNERS,
    }


@app.get("/api/rule-candidates")
def rule_candidates() -> dict[str, object]:
    candidates = detect_rule_candidates(get_settings().database_path)
    return {"rule_candidates": candidates, "count": len(candidates)}


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


@app.post("/api/outlook-desktop/export-inbox")
def export_outlook_desktop_inbox() -> dict[str, object]:
    if not IS_WINDOWS:
        raise HTTPException(status_code=503, detail="Outlook COM integration is Windows-only.")
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
        messages = result.pop("messages", None)
        if messages is not None:
            stored = _store_and_optionally_analyze(messages, settings, analyze=True)
            imported_ids = [str(message["graph_message_id"]) for message in messages if message.get("graph_message_id")]
            deleted_count = delete_emails_not_in_graph_ids(imported_ids, db_path=settings.database_path)
            record_sync_run(
                source="outlook_desktop",
                mailbox_mode="shared",
                fetched_count=len(messages),
                inserted_count=stored["inserted_count"],
                updated_count=stored["updated_count"],
                analyzed_count=stored["analyzed_count"],
                db_path=settings.database_path,
            )
            _log.info(
                "Outlook direct import completed: fetched=%s inserted=%s updated=%s analyzed=%s deleted=%s",
                len(messages),
                stored["inserted_count"],
                stored["updated_count"],
                stored["analyzed_count"],
                deleted_count,
            )
            return {
                "source": "outlook_desktop",
                "fetched_count": len(messages),
                "deleted_count": deleted_count,
                "read_only_outlook": True,
                **result,
                **stored,
            }

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
    feedback_entries = list_recent_triage_feedback(limit=200, db_path=settings.database_path)
    analyzed = 0
    for email in pending:
        save_analysis(
            email["id"],
            triage_email(email, settings, feedback_entries=feedback_entries),
            db_path=settings.database_path,
        )
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
    feedback_entries = list_recent_triage_feedback(limit=150, db_path=settings.database_path)
    emails = _group_conversation_rows(
        [_decorate_email(email) for email in emails],
        settings=settings,
        feedback_entries=feedback_entries,
    )
    emails.sort(key=lambda email: (email["urgency_score"], email.get("received_datetime") or ""), reverse=True)
    return {"emails": emails, "count": len(emails)}


@app.get("/api/emails/{email_id}")
def api_get_email(email_id: int) -> dict[str, object]:
    settings = get_settings()
    email = get_email(email_id, db_path=settings.database_path)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found.")
    decorated = _decorate_email(email)
    conversation_id = decorated.get("conversation_id")
    if conversation_id:
        raw_messages = list_conversation_emails(str(conversation_id), db_path=settings.database_path)
        feedback_entries = list_recent_triage_feedback(limit=150, db_path=settings.database_path)
        messages = [_decorate_email(row) for row in raw_messages]
        decorated = _apply_conversation_triage(decorated, raw_messages, settings, feedback_entries)
        decorated["feedback_count"] = len(
            list_feedback_for_conversation(str(conversation_id), db_path=settings.database_path)
        )
    else:
        messages = [decorated]
    decorated["conversation_messages"] = messages
    decorated["conversation_email_count"] = len(messages)
    return {"email": decorated}


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


@app.post("/api/emails/{email_id}/feedback")
def api_triage_feedback(email_id: int, payload: TriageFeedbackRequest, request: Request) -> dict[str, object]:
    settings = get_settings()
    email = get_email(email_id, db_path=settings.database_path)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found.")

    corrections = infer_feedback_corrections(payload.feedback_text, email)
    explicit = {
        "corrected_urgency": payload.corrected_urgency,
        "corrected_category": payload.corrected_category,
        "corrected_owner": payload.corrected_owner,
        "corrected_contact_type": payload.corrected_contact_type,
        "corrected_sentiment": payload.corrected_sentiment,
        "corrected_status": payload.corrected_status,
    }
    for key, value in explicit.items():
        if value not in (None, ""):
            corrections[key] = value

    _validate_feedback_corrections(corrections)
    feedback_id = save_triage_feedback(
        email_id=email_id,
        conversation_id=str(email.get("conversation_id") or ""),
        feedback_text=payload.feedback_text,
        corrected_urgency=corrections.get("corrected_urgency"),
        corrected_category=corrections.get("corrected_category"),
        corrected_owner=corrections.get("corrected_owner"),
        corrected_contact_type=corrections.get("corrected_contact_type"),
        corrected_sentiment=corrections.get("corrected_sentiment"),
        corrected_status=corrections.get("corrected_status"),
        summary_quality_rating=payload.summary_quality_rating,
        reply_quality_rating=payload.reply_quality_rating,
        db_path=settings.database_path,
    )
    upload_feedback_event(
        _decorate_email(email),
        corrections,
        payload.feedback_text,
        summary_quality_rating=payload.summary_quality_rating,
        reply_quality_rating=payload.reply_quality_rating,
    )
    promote_rule_candidates(detect_rule_candidates(settings.database_path))
    if corrections.get("corrected_status"):
        update_status(email_id, str(corrections["corrected_status"]), db_path=settings.database_path)
    record_audit_event(
        action="triage.feedback",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="email",
        entity_id=email_id,
        metadata={
            "correction_keys": sorted(k for k, v in corrections.items() if v not in (None, "")),
            "summary_quality_rating": payload.summary_quality_rating,
            "reply_quality_rating": payload.reply_quality_rating,
        },
        db_path=settings.database_path,
    )

    conversation_id = str(email.get("conversation_id") or "")
    raw_messages = (
        list_conversation_emails(conversation_id, db_path=settings.database_path) if conversation_id else [email]
    )
    feedback_entries = list_recent_triage_feedback(limit=150, db_path=settings.database_path)
    decorated = _apply_conversation_triage(_decorate_email(email), raw_messages, settings, feedback_entries)
    decorated["conversation_messages"] = [_decorate_email(row) for row in raw_messages]
    decorated["conversation_email_count"] = len(raw_messages)
    decorated["feedback_count"] = len(list_feedback_for_conversation(conversation_id, db_path=settings.database_path))
    return {"email": decorated, "feedback_id": feedback_id, "corrections": corrections}


@app.patch("/api/emails/{email_id}/status")
def api_update_status(email_id: int, update: StatusUpdate, request: Request) -> dict[str, object]:
    settings = get_settings()
    try:
        update_status(email_id, update.status, db_path=settings.database_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Email not found.") from exc
    email = get_email(email_id, db_path=settings.database_path)
    record_audit_event(
        action="email.status",
        actor_user_id=str(request.state.user["id"]),
        actor_email=str(request.state.user["email"]),
        entity_type="email",
        entity_id=email_id,
        metadata={"status": update.status},
        db_path=settings.database_path,
    )
    return {"email": _decorate_email(email or {}), "read_only_outlook": True}


def _desktop_message_to_email(message: DesktopOutlookMessage, mailbox: str, folder: str) -> dict[str, object]:
    data = message.model_dump() if hasattr(message, "model_dump") else message.dict()
    raw_id = (
        data.get("graph_message_id")
        or f"{mailbox}:{folder}:{data.get('conversation_id')}:{data.get('received_datetime')}:{data.get('subject')}"
    )
    body = str(data.get("body_text") or data.get("body_content") or data.get("body_preview") or "")
    preview = str(data.get("body_preview") or body[:240])
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


def _validate_feedback_corrections(corrections: dict[str, object]) -> None:
    if corrections.get("corrected_category") and corrections["corrected_category"] not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Unsupported category correction.")
    if corrections.get("corrected_owner") and corrections["corrected_owner"] not in DEPARTMENT_OWNERS:
        raise HTTPException(status_code=400, detail="Unsupported owner correction.")
    if corrections.get("corrected_contact_type") and corrections["corrected_contact_type"] not in CONTACT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported contact correction.")
    if corrections.get("corrected_sentiment") and corrections["corrected_sentiment"] not in {
        "Positive",
        "Neutral",
        "Concerned",
        "Upset",
    }:
        raise HTTPException(status_code=400, detail="Unsupported sentiment correction.")
    if corrections.get("corrected_status") and corrections["corrected_status"] not in STATUSES:
        raise HTTPException(status_code=400, detail="Unsupported status correction.")
    if corrections.get("corrected_urgency") not in (None, ""):
        try:
            score = int(str(corrections["corrected_urgency"]))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Unsupported urgency correction.") from exc
        if score < 1 or score > 5:
            raise HTTPException(status_code=400, detail="Unsupported urgency correction.")


def _decorate_email(email: dict[str, object]) -> dict[str, object]:
    decorated = dict(email)
    decorated["urgency_score"] = urgency_score(decorated)
    decorated["priority_rank"] = decorated["urgency_score"]
    return decorated


def _apply_conversation_triage(
    row: dict[str, object],
    conversation: list[dict[str, object]],
    settings,
    feedback_entries: list[dict[str, object]],
) -> dict[str, object]:
    analysis = triage_conversation(conversation, settings=settings, feedback_entries=feedback_entries)
    merged = dict(row)
    for key in (
        "ai_summary",
        "category",
        "priority_level",
        "guest_sentiment",
        "internal_next_steps",
        "missing_information",
        "risk_flags",
        "recommended_department_owner",
        "contact_type",
        "analysis_engine",
        "model",
        "feedback_applied",
        "adaptive_explanation",
    ):
        if key in analysis:
            merged[key] = analysis[key]
    if analysis.get("urgency_score") not in (None, ""):
        merged["urgency_override"] = analysis["urgency_score"]
    return _decorate_email(merged)


def _group_conversation_rows(
    emails: list[dict[str, object]],
    *,
    settings,
    feedback_entries: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for email in emails:
        key = str(email.get("conversation_id") or email.get("graph_message_id") or email.get("id"))
        grouped.setdefault(key, []).append(email)

    rows: list[dict[str, object]] = []
    for key, conversation in grouped.items():
        conversation.sort(
            key=lambda email: (str(email.get("received_datetime") or ""), int(str(email.get("id") or "0"))),
            reverse=True,
        )
        row = dict(conversation[0])
        row["conversation_id"] = row.get("conversation_id") or key
        row["conversation_email_count"] = len(conversation)
        row = _apply_conversation_triage(row, conversation, settings, feedback_entries)
        row["conversation_email_count"] = len(conversation)
        rows.append(row)
    return rows


def _store_and_optionally_analyze(messages, settings, analyze: bool) -> dict[str, int]:
    inserted = 0
    updated = 0
    analyzed = 0
    feedback_entries = list_recent_triage_feedback(limit=200, db_path=settings.database_path) if analyze else []
    for message in messages:
        if not message.get("graph_message_id"):
            continue
        email_id, was_inserted = upsert_email(message, db_path=settings.database_path)
        inserted += 1 if was_inserted else 0
        updated += 0 if was_inserted else 1
        if analyze:
            email = get_email(email_id, db_path=settings.database_path)
            if email:
                save_analysis(
                    email_id,
                    triage_email(email, settings, feedback_entries=feedback_entries),
                    db_path=settings.database_path,
                )
                analyzed += 1
    return {"inserted_count": inserted, "updated_count": updated, "analyzed_count": analyzed}

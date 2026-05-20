from __future__ import annotations

import html as html_lib
import os
import platform
import secrets
import sys
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
    admin_setup_available,
    admin_user_exists,
    authenticate_user,
    create_first_admin,
    create_reset_token,
    create_session,
    create_user,
    delete_session,
    delete_user,
    encode_session,
    ensure_admin,
    get_session_user,
    list_users,
    needs_credentials_setup,
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
    get_purgeable_email_ids,
    initialize_database,
    list_conversation_emails,
    list_emails,
    list_feedback_for_conversation,
    list_recent_triage_feedback,
    purge_email_bodies,
    record_audit_event,
    record_sync_run,
    save_analysis,
    save_triage_feedback,
    set_rule_candidate_status,
    update_feedback_quality_state,
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
from .platform_compat import HAS_OUTLOOK_COM, IS_WINDOWS
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
from .kyc import router as kyc_router
from .local_classifier import feature_importance as classifier_feature_importance
from .local_classifier import get_model_meta
from .local_classifier import invalidate_cache as invalidate_classifier_cache
from .local_classifier import train as train_local_classifier
from .training_pipeline import pipeline_status as training_pipeline_status
from .training_pipeline import run_pipeline as run_training_pipeline
from .completed_training_pipeline import (
    completed_pipeline_status,
    run_completed_pipeline,
)
from .database import list_property_knowledge
from .updater import get_build_info, get_update_status, start_download, start_update_check

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
        if not admin_user_exists():
            _log.info("No admin found; first-run setup is available.")
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
    "/setup",
    "/credentials-setup",
    "/healthz",
    "/api/health",
    "/reset-password",
    "/api/auth/login",
    "/api/auth/setup",
    "/api/auth/logout",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
}
_AUTH_SKIP_PREFIX = ("/static/",)
_RATE_LIMIT_PATHS = {
    "/login",
    "/setup",
    "/credentials-setup",
    "/api/auth/login",
    "/api/auth/setup",
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
    version="0.1.1",
    lifespan=lifespan,
)
app.add_middleware(_RateLimitMiddleware)
app.add_middleware(_AuthMiddleware)
app.add_middleware(_RequestLogMiddleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(kyc_router)


class StatusUpdate(BaseModel):
    status: str


_FEEDBACK_REASON_CODES = {
    "wrong_category", "wrong_urgency", "wrong_owner", "wrong_contact_type",
    "missing_risk_flag", "false_risk_flag", "poor_summary", "poor_reply_draft",
    "confidence_too_low", "context_mismatch", "other",
}


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
    correction_reason: str | None = Field(default=None, max_length=80)


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


@app.get("/credentials-setup", response_model=None)
def credentials_setup_page() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


@app.post("/credentials-setup", response_model=None)
def credentials_setup_form() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_model=None)
def login_page() -> HTMLResponse | RedirectResponse:
    if not admin_user_exists():
        return RedirectResponse("/setup", status_code=303)
    return _login_response()


@app.post("/login", response_model=None)
def login_form(
    email: str = Form(...), password: str = Form(...), remember_email: str | None = Form(None)
) -> HTMLResponse | RedirectResponse:
    if not admin_user_exists():
        return RedirectResponse("/setup", status_code=303)
    settings = get_settings()
    user = authenticate_user(email, password, settings.database_path)
    if not user:
        response = _login_response(
            "Invalid email or password.", email, status_code=401, remember_checked=bool(remember_email)
        )
        _apply_remembered_email(response, email, bool(remember_email))
        return response
    response = RedirectResponse("/", status_code=303)
    _set_auth_cookie(response, user, settings.database_path)
    _apply_remembered_email(response, email, bool(remember_email))
    return response


@app.get("/setup", response_model=None)
def setup_page() -> HTMLResponse | RedirectResponse:
    if admin_user_exists():
        return RedirectResponse("/login", status_code=303)
    return _setup_response()


@app.post("/setup", response_model=None)
def setup_form(email: str = Form(...), password: str = Form(...)) -> HTMLResponse | RedirectResponse:
    settings = get_settings()
    if len(password) < 8:
        return _setup_response(error_message="Password must be at least 8 characters.", email=email, status_code=400)
    if admin_user_exists():
        return RedirectResponse("/login", status_code=303)
    try:
        if admin_setup_available():
            user_id = create_first_admin(email, password, settings.database_path)
        else:
            user_id = create_user(email, password, role="admin", db_path=settings.database_path)
    except Exception as exc:
        return _setup_response(error_message=str(exc), email=email, status_code=400)
    record_audit_event(
        action="auth.first_admin_setup",
        actor_user_id=None,
        actor_email=email.lower().strip(),
        entity_type="user",
        entity_id=user_id,
        metadata={"role": "admin"},
        db_path=settings.database_path,
    )
    user = authenticate_user(email, password, settings.database_path)
    if not user:
        return RedirectResponse("/login", status_code=303)
    response = RedirectResponse("/", status_code=303)
    _set_auth_cookie(response, user, settings.database_path)
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


def _setup_response(error_message: str = "", email: str = "", status_code: int = 200) -> HTMLResponse:
    html = (STATIC_DIR / "setup.html").read_text(encoding="utf-8")
    html = html.replace(
        'data-server-error=""',
        f'data-server-error="{html_lib.escape(error_message, quote=True)}"',
    )
    html = html.replace(
        'value="" data-server-email',
        f'value="{html_lib.escape(email.strip(), quote=True)}" data-server-email',
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


def _set_auth_cookie(response, user: dict, db_path: Path | None = None) -> None:
    access_token = user.pop("_access_token", "")
    refresh_token = user.pop("_refresh_token", "")
    if access_token and refresh_token:
        cookie_value = encode_session(access_token, refresh_token)
    else:
        cookie_value = create_session(str(user["id"]), db_path)
    response.set_cookie(
        "rr_session",
        cookie_value,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )


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


class SetupAdminRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


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
    _set_auth_cookie(response, user, settings.database_path)
    return response


@app.get("/api/auth/startup-state")
def api_startup_state():
    """Return the first-run state so the Qt desktop shell can route to the correct window."""
    if needs_credentials_setup():
        return JSONResponse({"state": "credentials_setup"})
    if admin_setup_available() and not admin_user_exists():
        return JSONResponse({"state": "admin_setup"})
    return JSONResponse({"state": "login"})


@app.post("/api/auth/credentials-setup")
def api_credentials_setup(payload: CredentialsSetupRequest):
    url = payload.supabase_url.strip()
    key = payload.supabase_key.strip()
    svc = payload.supabase_service_role_key.strip()
    ai_key = payload.anthropic_api_key.strip()

    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="SUPABASE_URL must start with https://")
    if len(key) < 20:
        raise HTTPException(status_code=400, detail="SUPABASE_KEY appears too short.")
    if len(svc) < 20:
        raise HTTPException(status_code=400, detail="SUPABASE_SERVICE_ROLE_KEY appears too short.")

    values: dict[str, str] = {
        "SUPABASE_URL": url,
        "SUPABASE_KEY": key,
        "SUPABASE_SERVICE_ROLE_KEY": svc,
    }
    if ai_key:
        values["ANTHROPIC_API_KEY"] = ai_key

    try:
        write_local_env(values)
    except Exception as exc:
        _log.error("api credentials-setup: failed to write .env: %s", exc)
        raise HTTPException(status_code=500, detail="Could not save credentials to local .env.") from exc

    get_settings.cache_clear()
    _log.info("api credentials-setup: Supabase config written for %d keys", len(values))
    return JSONResponse({"ok": True, "keys_written": list(values.keys())})


@app.post("/api/auth/setup")
def api_setup_admin(payload: SetupAdminRequest, request: Request):
    settings = get_settings()
    if admin_user_exists():
        raise HTTPException(status_code=409, detail="An admin account already exists.")
    try:
        if admin_setup_available():
            user_id = create_first_admin(payload.email, payload.password, settings.database_path)
        else:
            user_id = create_user(payload.email, payload.password, role="admin", db_path=settings.database_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        action="auth.first_admin_setup",
        actor_user_id=None,
        actor_email=payload.email.lower().strip(),
        entity_type="user",
        entity_id=user_id,
        metadata={"role": "admin"},
        db_path=settings.database_path,
    )
    user = authenticate_user(payload.email, payload.password, settings.database_path)
    response = JSONResponse({"ok": True, "email": payload.email.lower().strip(), "role": "admin"})
    if user:
        _set_auth_cookie(response, user, settings.database_path)
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


def _local_base_url(request: Request) -> str:
    """Return the current app origin without a trailing slash."""
    return str(request.base_url).rstrip("/")


@app.post("/api/auth/invite")
def api_invite(payload: InviteRequest, request: Request):
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    try:
        user_id = create_user(
            payload.email,
            secrets.token_hex(32),  # placeholder — user sets their own password via invite link
            role="user",
            invited_by_id=(
                request.state.user["id"]
                if admin_setup_available() or str(request.state.user["id"]).isdigit()
                else None
            ),
            db_path=settings.database_path,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = create_reset_token(payload.email, settings.database_path, hours=24)
    if not token:
        raise HTTPException(status_code=500, detail="Could not generate invite token.")
    base_url = _local_base_url(request)
    invite_url = f"{base_url}/reset-password?token={token}"
    result = {
        "ok": True,
        "user_id": user_id,
        "email_sent": False,
        "invite_url": invite_url,
        "manual_delivery_required": True,
        "detail": "Invite created. Copy invite_url to the user or configure SMTP for email delivery.",
    }
    if not settings.smtp_configured:
        record_audit_event(
            action="auth.invite.created_manual_delivery",
            actor_user_id=None,
            actor_email=str(request.state.user["email"]),
            entity_type="user",
            entity_id=user_id,
            metadata={"email_sent": False, "smtp_configured": False},
            db_path=settings.database_path,
        )
        return result
    try:
        send_invite_email(payload.email, token, base_url, settings)
    except Exception as exc:
        _log.error("Invite email failed for %s: %s", payload.email, exc)
        result["detail"] = "User created but invite email failed. Copy invite_url manually."
        result["email_error"] = "smtp_send_failed"
        record_audit_event(
            action="auth.invite.email_failed",
            actor_user_id=None,
            actor_email=str(request.state.user["email"]),
            entity_type="user",
            entity_id=user_id,
            metadata={"email_sent": False, "smtp_configured": True},
            db_path=settings.database_path,
        )
        return result
    result["email_sent"] = True
    result["manual_delivery_required"] = False
    result["detail"] = "Invite email sent."
    record_audit_event(
        action="auth.invite.sent",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="user",
        entity_id=user_id,
        metadata={"email_sent": True},
        db_path=settings.database_path,
    )
    return result


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


@app.get("/api/admin/deployment/diagnostics")
def api_deployment_diagnostics(request: Request) -> dict[str, object]:
    """Return a safe deployment readiness snapshot for support and beta rollout."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    build = get_build_info()
    classifier_meta = get_model_meta(settings.database_path) or {}
    checks = {
        "runtime": {
            "frozen": bool(getattr(sys, "frozen", False)),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "executable": Path(sys.executable).name,
        },
        "app": {
            "version": build.get("version", ""),
            "commit": build.get("commit", ""),
            "build_date": build.get("build_date", ""),
            "host": settings.app_host,
            "port": settings.app_port,
            "native_shell": "PySide6",
        },
        "storage": {
            "database_path": str(settings.database_path),
            "database_exists": settings.database_path.exists(),
            "data_dir": str(DATA_DIR),
        },
        "services": {
            "supabase_configured": bool(settings.supabase_url and settings.supabase_key),
            "supabase_admin_configured": admin_setup_available(),
            "smtp_configured": settings.smtp_configured,
            "graph_configured": settings.graph_configured,
            "openai_configured": settings.openai_configured,
            "google_ai_configured": settings.google_ai_configured,
            "anthropic_configured": settings.anthropic_configured,
        },
        "outlook": {
            "windows": IS_WINDOWS,
            "outlook_com_available": HAS_OUTLOOK_COM,
            "mailbox": settings.outlook_export_mailbox,
            "folder": settings.outlook_export_folder,
        },
        "classifier": {
            "has_model": bool(classifier_meta.get("version_id")),
            "version_id": classifier_meta.get("version_id", ""),
            "trained_at": classifier_meta.get("trained_at", ""),
            "targets": sorted((classifier_meta.get("targets") or {}).keys()),
        },
        "warnings": settings.runtime_warnings,
    }
    return checks


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


@app.post("/api/admin/training/purge-bodies")
def api_purge_bodies(
    request: Request,
    min_age_days: int = Query(default=0, ge=0, description="Only purge emails received this many days ago or earlier"),
    require_analyzed: bool = Query(default=True, description="Only purge emails with a completed analysis"),
    dry_run: bool = Query(default=False, description="Report what would be purged without making changes"),
) -> dict[str, object]:
    """Null out email body_text and body_content for analyzed emails to free storage.

    Part of the import→train→delete workflow. Safe to run repeatedly.
    Returns the IDs purged and the total count.
    """
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    ids = get_purgeable_email_ids(
        min_age_days=min_age_days,
        require_analyzed=require_analyzed,
        db_path=settings.database_path,
    )
    if dry_run:
        return {"dry_run": True, "purgeable_count": len(ids), "purgeable_ids": ids}
    purged = purge_email_bodies(ids, db_path=settings.database_path)
    record_audit_event(
        action="training.bodies.purged",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="email_bodies",
        entity_id=None,
        metadata={"purged_count": purged, "min_age_days": min_age_days, "require_analyzed": require_analyzed},
        db_path=settings.database_path,
    )
    return {"purged_count": purged, "purged_ids": ids, "dry_run": False}


class CompletedRequestsImportBody(BaseModel):
    mailbox_name: str = Field(..., min_length=1, description="Outlook mailbox display name")
    folder_name: str = Field("Completed Requests", min_length=1)
    batch_size: int = Field(50, ge=1, le=200)


@app.post("/api/admin/training/import-completed-requests")
def api_import_completed_requests(
    payload: CompletedRequestsImportBody,
    request: Request,
) -> dict[str, object]:
    """Import up to batch_size emails from the Completed Requests Outlook folder,
    label them with local heuristics, and store compact sanitized training examples.
    Requires admin role and Outlook running on the same Windows machine.
    """
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    result = run_completed_pipeline(
        mailbox_name=payload.mailbox_name,
        folder_name=payload.folder_name,
        batch_size=payload.batch_size,
        db_path=settings.database_path,
    )
    record_audit_event(
        action="training.completed_requests.import",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="completed_training_pipeline",
        entity_id=None,
        metadata={k: v for k, v in result.items() if k != "messages"},
        db_path=settings.database_path,
    )
    return result


@app.get("/api/admin/training/completed-requests/status")
def api_completed_requests_status(request: Request) -> dict[str, object]:
    """Return processing counts and property knowledge summary."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    return completed_pipeline_status(db_path=get_settings().database_path)


@app.get("/api/admin/training/property-knowledge")
def api_property_knowledge(
    request: Request,
    item_type: str = Query(""),
) -> dict[str, object]:
    """Return the property knowledge base extracted from completed email requests."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    items = list_property_knowledge(db_path=get_settings().database_path)
    if item_type:
        items = [i for i in items if i.get("item_type") == item_type]
    grouped: dict[str, list[dict]] = {}
    for item in items:
        t = str(item.get("item_type", "other"))
        grouped.setdefault(t, []).append(item)
    return {"total": len(items), "by_type": grouped}


@app.get("/api/admin/prompts")
def api_list_prompts(request: Request) -> dict[str, object]:
    """List all prompt versions from Supabase."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        return {"prompts": [], "error": "Supabase not configured"}
    try:
        import httpx
        r = httpx.get(
            f"{url}/rest/v1/prompt_versions",
            params={"select": "*", "order": "updated_at.desc"},
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
            timeout=10,
        )
        if r.status_code == 200:
            return {"prompts": r.json()}
        return {"prompts": [], "error": f"status={r.status_code}"}
    except Exception as exc:
        return {"prompts": [], "error": str(exc)[:200]}


class PromptUpdateRequest(BaseModel):
    prompt_id: str
    prompt_text: str
    version: str | None = None


@app.patch("/api/admin/prompts/{prompt_id}")
def api_update_prompt(prompt_id: str, payload: PromptUpdateRequest, request: Request) -> dict[str, object]:
    """Update prompt text in Supabase and refresh the local cache."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    update = {"prompt_text": payload.prompt_text}
    if payload.version:
        update["version"] = payload.version
    try:
        import httpx
        r = httpx.patch(
            f"{url}/rest/v1/prompt_versions",
            params={"id": f"eq.{prompt_id}"},
            json=update,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            timeout=10,
        )
        if r.status_code not in (200, 204):
            raise HTTPException(status_code=502, detail=f"Supabase error {r.status_code}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)[:200]) from exc
    # Refresh local cache so next Analyze call uses the new prompt immediately
    from .supabase_client import download_prompt_versions
    download_prompt_versions()
    record_audit_event(
        action="prompt.updated",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="prompt_version",
        entity_id=prompt_id,
        metadata={"version": payload.version},
        db_path=get_settings().database_path,
    )
    return {"ok": True, "id": prompt_id}


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


@app.get("/api/admin/training/dual-labeled-stats")
def api_dual_labeled_stats(request: Request) -> dict[str, object]:
    """Return dual-labeled counts: this week + last 4 weekly buckets for sparkline."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        return {"this_week": 0, "weeks": [0, 0, 0, 0], "error": "Supabase not configured"}
    from datetime import datetime, timedelta, timezone as _tz

    now = datetime.now(tz=_tz.utc)
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    weeks: list[int] = []
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=10) as client:
            for w in range(3, -1, -1):  # week 3 (oldest) → week 0 (current)
                week_end = now - timedelta(weeks=w)
                week_start = week_end - timedelta(weeks=1)
                r = client.get(
                    f"{url}/rest/v1/training_examples",
                    params={
                        "select": "id",
                        "labeling_engine": "eq.dual_labeled",
                        "created_at": f"gte.{week_start.isoformat()}&created_at=lte.{week_end.isoformat()}",
                        "limit": "1000",
                    },
                    headers={**headers, "Prefer": "count=exact"},
                )
                count = int(r.headers.get("content-range", "*/0").split("/")[-1])
                weeks.append(count)
    except Exception as exc:
        return {"this_week": 0, "weeks": [0, 0, 0, 0], "error": str(exc)[:200]}
    return {"this_week": weeks[-1] if weeks else 0, "weeks": weeks}


@app.get("/api/admin/intelligence/health")
def api_intelligence_health(request: Request) -> dict[str, object]:
    """Model health: version, training timestamp, per-target accuracy + label distribution."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    meta = get_model_meta(db_path=settings.database_path)
    if not meta:
        return {"status": "no_model", "message": "No local classifier has been trained yet."}
    targets = meta.get("targets") or {}
    summary: dict[str, object] = {
        "status": "ok",
        "version_id": meta.get("version_id"),
        "trained_at": meta.get("trained_at"),
        "total_examples": meta.get("total_examples_downloaded"),
        "targets": {},
    }
    for target, tmeta in targets.items():
        cv = tmeta.get("cv_accuracy", -1)
        dist = tmeta.get("label_distribution") or {}
        summary["targets"][target] = {  # type: ignore[index]
            "examples": tmeta.get("examples"),
            "classes": tmeta.get("classes"),
            "cv_accuracy": cv if cv >= 0 else None,
            "label_distribution": dist,
            "most_common_label": max(dist, key=dist.get) if dist else None,  # type: ignore[arg-type]
            "least_common_label": min(dist, key=dist.get) if dist else None,  # type: ignore[arg-type]
        }
    return summary


@app.get("/api/admin/models/feature-importance")
def api_feature_importance(request: Request) -> dict[str, object]:
    """Top TF-IDF terms per class for each trained target (urgency, owner, category)."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    fi = classifier_feature_importance(db_path=settings.database_path)
    if not fi:
        return {"status": "no_model", "feature_importance": {}}
    return {"status": "ok", "feature_importance": fi}


@app.get("/api/admin/intelligence/sender-profile")
def api_sender_profile(request: Request, domain: str = Query("")) -> dict[str, object]:
    """Return the learned sender reputation profile for a domain."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    if not domain:
        raise HTTPException(status_code=400, detail="domain query parameter required")
    from .sender_intelligence import get_sender_profile
    profile = get_sender_profile(domain.lower().strip())
    return {"status": "ok", "profile": profile}


@app.get("/api/admin/intelligence/signals")
def api_email_signals(request: Request, email_id: int = Query(0)) -> dict[str, object]:
    """Extract and return the full signal set for a stored email."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    if not email_id:
        raise HTTPException(status_code=400, detail="email_id query parameter required")
    settings = get_settings()
    row = get_email(email_id, db_path=settings.database_path)
    if not row:
        raise HTTPException(status_code=404, detail="Email not found")
    from .signal_extractor import describe_signals, extract_signals
    signals = extract_signals(
        subject=str(row.get("subject") or ""),
        body=str(row.get("body_text") or row.get("body_preview") or ""),
        sender_email=str(row.get("sender_email") or ""),
        sender_name=str(row.get("sender_name") or ""),
        received_at=row.get("received_datetime"),
    )
    return {
        "status": "ok",
        "email_id": email_id,
        "signals": signals,
        "description": describe_signals(signals),
    }


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
        "service": "ReplyRight",
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
        },
        "config_warnings": settings.runtime_warnings,
    }


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "ReplyRight", "version": app.version}


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
        "asset_url": status.get("asset_url") or "",
        "checked": bool(status.get("checked")),
        "downloading": bool(status.get("downloading")),
        "download_error": status.get("download_error") or "",
    }


@app.get("/api/version")
def api_version() -> dict[str, object]:
    build = get_build_info()
    status = get_update_status()
    return {
        "version": build.get("version") or "",
        "commit": build.get("commit") or "",
        "build_date": build.get("build_date") or "",
        "update_available": bool(status.get("available")),
        "latest_version": status.get("version") or "",
    }


@app.post("/api/update/download")
def trigger_update_download() -> dict[str, object]:
    status = get_update_status()
    if not status.get("available"):
        raise HTTPException(status_code=409, detail="No update available.")
    if status.get("downloading"):
        return {"status": "already_downloading"}
    asset_url = status.get("asset_url") or ""
    if not asset_url:
        raise HTTPException(status_code=409, detail="No download URL — update from GitHub manually.")
    start_download(asset_url)
    return {"status": "started"}


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
def import_outlook_desktop_json(
    payload: DesktopOutlookImport,
    purge_after_analyze: bool = Query(
        default=False,
        description="Null out body_text/body_content after analysis (import→train→delete workflow)",
    ),
) -> dict[str, object]:
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
    purged_count = 0
    if purge_after_analyze:
        ids = get_purgeable_email_ids(require_analyzed=True, db_path=settings.database_path)
        purged_count = purge_email_bodies(ids, db_path=settings.database_path)
    return {
        "source": "outlook_desktop",
        "mailbox": payload.mailbox,
        "folder": payload.folder,
        "fetched_count": len(messages),
        "bodies_purged": purged_count,
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
    needs_review: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    settings = get_settings()
    emails = list_emails(
        category=category or None,
        priority=priority or None,
        status=status or None,
        risk=risk or None,
        query=q or None,
        needs_review=needs_review,
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
    reason = payload.correction_reason
    if reason and reason not in _FEEDBACK_REASON_CODES:
        reason = "other"
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
        correction_reason=reason,
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
        action="triage.feedback.submitted",
        actor_user_id=None,
        actor_email=str(request.state.user["email"]),
        entity_type="email",
        entity_id=email_id,
        metadata={
            "feedback_id": feedback_id,
            "correction_keys": sorted(k for k, v in corrections.items() if v not in (None, "")),
            "correction_reason": reason,
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


class FeedbackQualityRequest(BaseModel):
    quality_state: str = Field(description="One of: raw, reviewed, training_ready, excluded")


@app.patch("/api/feedback/{feedback_id}/quality")
def api_update_feedback_quality(feedback_id: int, payload: FeedbackQualityRequest, request: Request) -> dict[str, object]:
    """Advance a feedback row's quality state for training pipeline control."""
    if request.state.user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    settings = get_settings()
    try:
        update_feedback_quality_state(feedback_id, payload.quality_state, db_path=settings.database_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit_event(
        action="feedback.quality_state",
        actor_email=str(request.state.user["email"]),
        entity_type="triage_feedback",
        entity_id=feedback_id,
        metadata={"quality_state": payload.quality_state},
        db_path=settings.database_path,
    )
    return {"ok": True, "feedback_id": feedback_id, "quality_state": payload.quality_state}


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

from __future__ import annotations

import json
import logging
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

from .text_utils import utc_now_iso

_SESSION_SEP = "|||"
_log = logging.getLogger(__name__)


# ── Supabase connection helpers ───────────────────────────────────────────────


def _supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "").strip().rstrip("/")


def _anon_key() -> str:
    return os.getenv("SUPABASE_KEY", "").strip()


def _service_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def _auth_url(path: str = "") -> str:
    return f"{_supabase_url()}/auth/v1{path}"


def _anon_headers() -> dict:
    return {"apikey": _anon_key(), "Content-Type": "application/json"}


def _admin_headers() -> dict:
    key = _service_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _req(url: str, headers: dict, body: dict | None = None, method: str = "GET") -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            err_body = json.loads(raw)
        except Exception:
            err_body = {"error": raw[:200]}
        raise RuntimeError(f"Supabase {exc.code}: {err_body}") from exc


def _normalize_user(data: dict) -> dict:
    user = data.get("user") or data
    meta = user.get("app_metadata") or {}
    return {
        "id": user.get("id", ""),
        "email": (user.get("email") or "").lower().strip(),
        "role": meta.get("role") or "user",
    }


# ── Session encoding ──────────────────────────────────────────────────────────


def encode_session(access_token: str, refresh_token: str) -> str:
    return f"{access_token}{_SESSION_SEP}{refresh_token}"


def _decode_session(cookie: str) -> tuple[str, str] | None:
    if not cookie or _SESSION_SEP not in cookie:
        return None
    parts = cookie.split(_SESSION_SEP, 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


# ── Auth functions ────────────────────────────────────────────────────────────


def authenticate_user(email: str, password: str, db_path: Path | None = None) -> dict | None:
    """Sign in with email/password. Returns user dict with _access_token/_refresh_token."""
    try:
        resp = _req(
            _auth_url("/token?grant_type=password"),
            _anon_headers(),
            {"email": email.lower().strip(), "password": password},
            method="POST",
        )
    except Exception as exc:
        _log.warning("Supabase sign-in failed: %s", exc)
        return None
    access_token = resp.get("access_token", "")
    refresh_token = resp.get("refresh_token", "")
    if not access_token:
        return None
    user = _normalize_user(resp)
    user["_access_token"] = access_token
    user["_refresh_token"] = refresh_token
    return user


def get_session_user(session_cookie: str, db_path: Path | None = None) -> dict | None:
    """Validate session cookie; returns user dict or None.
    May add _new_access_token/_new_refresh_token if token was refreshed."""
    decoded = _decode_session(session_cookie)
    if not decoded:
        return None
    access_token, refresh_token = decoded

    try:
        resp = _req(
            _auth_url("/user"),
            {**_anon_headers(), "Authorization": f"Bearer {access_token}"},
        )
        return _normalize_user(resp)
    except Exception:
        pass

    if not refresh_token:
        return None
    try:
        resp = _req(
            _auth_url("/token?grant_type=refresh_token"),
            _anon_headers(),
            {"refresh_token": refresh_token},
            method="POST",
        )
        new_access = resp.get("access_token", "")
        new_refresh = resp.get("refresh_token", refresh_token)
        if not new_access:
            return None
        user = _normalize_user(resp)
        user["_new_access_token"] = new_access
        user["_new_refresh_token"] = new_refresh
        return user
    except Exception as exc:
        _log.warning("Supabase token refresh failed: %s", exc)
        return None


def create_session(user_id: str, db_path: Path | None = None) -> str:
    """No-op — sessions are encoded in cookies by encode_session()."""
    return ""


def delete_session(session_cookie: str, db_path: Path | None = None) -> None:
    """Sign the access token out from Supabase."""
    decoded = _decode_session(session_cookie)
    if not decoded:
        return
    access_token, _ = decoded
    try:
        _req(
            _auth_url("/logout"),
            {**_anon_headers(), "Authorization": f"Bearer {access_token}"},
            {},
            method="POST",
        )
    except Exception as exc:
        _log.debug("Supabase sign-out warning: %s", exc)


def ensure_admin(email: str, password: str, db_path: Path | None = None) -> None:
    """Create or repair the admin account in Supabase Auth."""
    normalized = email.lower().strip()
    existing = _find_user_by_email(normalized)
    if existing:
        _update_user(existing["id"], password=password, role="admin")
        _log.info("Supabase: admin account verified/updated for %s", normalized)
    else:
        _create_user(normalized, password, role="admin")
        _log.info("Supabase: admin account created for %s", normalized)


def admin_setup_available() -> bool:
    """Return whether ReplyRight can create the first Supabase admin user."""
    return bool(_supabase_url() and _service_key())


def admin_user_exists() -> bool:
    """Return True when at least one Supabase user has the ReplyRight admin role."""
    if not admin_setup_available():
        return False
    try:
        resp = _req(_auth_url("/admin/users?per_page=1000"), _admin_headers())
        for user in resp.get("users") or []:
            meta = user.get("app_metadata") or {}
            if (meta.get("role") or "").lower() == "admin":
                return True
        return False
    except Exception as exc:
        _log.warning("admin_user_exists failed: %s", exc)
        return False


def create_first_admin(email: str, password: str, db_path: Path | None = None) -> str:
    """Create the first ReplyRight admin user, refusing to run once an admin exists."""
    if not admin_setup_available():
        raise RuntimeError("Supabase service-role configuration is required for first-run setup.")
    if admin_user_exists():
        raise RuntimeError("An admin account already exists.")
    return _create_user(email.lower().strip(), password, role="admin")


def create_user(
    email: str,
    password: str,
    role: str = "user",
    invited_by_id=None,
    db_path: Path | None = None,
) -> str:
    return _create_user(email.lower().strip(), password, role=role)


def reset_password(user_id: str, new_password: str, db_path: Path | None = None) -> None:
    _update_user(str(user_id), password=new_password)


def delete_user(user_id: str, db_path: Path | None = None) -> None:
    try:
        req = urllib.request.Request(
            _auth_url(f"/admin/users/{user_id}"),
            headers=_admin_headers(),
            method="DELETE",
        )
        urllib.request.urlopen(req, timeout=15).close()
    except Exception as exc:
        _log.warning("delete_user failed: %s", exc)


def create_reset_token(email: str, db_path: Path | None = None, hours: int = 1) -> str | None:
    """Generate a password-reset token stored locally pointing to Supabase UUID."""
    from .database import managed_connect

    normalized = email.lower().strip()
    user = _find_user_by_email(normalized)
    if not user:
        return None
    supabase_uid = user.get("id", "")
    if not supabase_uid:
        return None
    token = secrets.token_urlsafe(32)
    from datetime import datetime, timedelta

    expires_at = (datetime.utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    with managed_connect(db_path) as db:
        db.execute(
            "INSERT INTO password_reset_tokens (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token, supabase_uid, expires_at, utc_now_iso()),
        )
    return token


def list_users(db_path: Path | None = None) -> list[dict]:
    try:
        resp = _req(_auth_url("/admin/users?per_page=1000"), _admin_headers())
        users = resp.get("users") or []
        result = []
        for u in users:
            meta = u.get("app_metadata") or {}
            result.append(
                {
                    "id": u.get("id", ""),
                    "email": u.get("email", ""),
                    "role": meta.get("role") or "user",
                    "created_at": u.get("created_at", ""),
                    "last_login": u.get("last_sign_in_at", ""),
                    "invited_by_email": None,
                }
            )
        return result
    except Exception as exc:
        _log.warning("list_users failed: %s", exc)
        return []


# ── Email helpers (SMTP remains local) ───────────────────────────────────────


def send_invite_email(to_email: str, token: str, base_url: str, settings) -> None:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if not settings.smtp_configured:
        _log.warning("send_invite_email: SMTP not configured, skipping email to %s", to_email)
        return
    set_pw_url = f"{base_url}/reset-password?token={token}"
    from_addr = settings.smtp_from or settings.smtp_user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "You've been invited to ReplyRight"
    msg["From"] = from_addr
    msg["To"] = to_email
    text_body = (
        f"Hi,\n\nYou've been invited to ReplyRight — the Waldorf Astoria New York reservations triage tool.\n\n"
        f"Click the link below to set your password and get started (link expires in 24 hours):\n{set_pw_url}\n\n"
        f"Your login email will be: {to_email}\n\n— ReplyRight"
    )
    html_body = f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e8e8e8;padding:40px 24px;max-width:480px;margin:0 auto">
<h2 style="color:#fff;margin-bottom:8px">Welcome to ReplyRight</h2>
<p style="color:rgba(255,255,255,0.55);margin-bottom:6px">Invited to <strong style="color:#e8e8e8">ReplyRight</strong> — Waldorf Astoria New York reservations triage.</p>
<p style="color:rgba(255,255,255,0.55);margin-bottom:6px">Your login email: <strong style="color:#e8e8e8">{to_email}</strong></p>
<p style="color:rgba(255,255,255,0.55);margin-bottom:28px">Click below to set your password. Link expires in <strong style="color:#e8e8e8">24 hours</strong>.</p>
<a href="{set_pw_url}" style="display:inline-block;background:#5b6af0;color:#fff;padding:13px 28px;border-radius:7px;text-decoration:none;font-weight:600;letter-spacing:.02em">Set My Password</a>
<p style="margin-top:36px;color:rgba(255,255,255,0.25);font-size:.8em">If you weren't expecting this, ignore this email.<br>Waldorf Astoria New York · Reservations</p>
</body></html>"""
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(from_addr, [to_email], msg.as_string())


def send_reset_email(to_email: str, token: str, base_url: str, settings) -> None:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if not settings.smtp_configured:
        _log.warning("send_reset_email: SMTP not configured")
        return
    reset_url = f"{base_url}/reset-password?token={token}"
    from_addr = settings.smtp_from or settings.smtp_user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "ReplyRight — Password Reset Request"
    msg["From"] = from_addr
    msg["To"] = to_email
    text_body = (
        f"Hi,\n\nA password reset was requested for your ReplyRight account ({to_email}).\n\n"
        f"Reset link (expires in 1 hour):\n{reset_url}\n\n"
        f"If you didn't request this, ignore this email — your password won't change.\n\n— ReplyRight"
    )
    html_body = f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e8e8e8;padding:40px 24px;max-width:480px;margin:0 auto">
<h2 style="color:#fff;margin-bottom:8px">ReplyRight — Password Reset</h2>
<p style="color:rgba(255,255,255,0.55);margin-bottom:6px">A reset was requested for <strong style="color:#e8e8e8">{to_email}</strong>.</p>
<p style="color:rgba(255,255,255,0.55);margin-bottom:28px">This link expires in <strong style="color:#e8e8e8">1 hour</strong>.</p>
<a href="{reset_url}" style="display:inline-block;background:#5b6af0;color:#fff;padding:13px 28px;border-radius:7px;text-decoration:none;font-weight:600;letter-spacing:.02em">Reset My Password</a>
<p style="margin-top:36px;color:rgba(255,255,255,0.25);font-size:.8em">If you didn't request this, ignore this email.<br>Waldorf Astoria New York · Reservations</p>
</body></html>"""
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(from_addr, [to_email], msg.as_string())


# ── Private Supabase Admin helpers ────────────────────────────────────────────


def _find_user_by_email(email: str) -> dict | None:
    try:
        resp = _req(_auth_url("/admin/users?per_page=1000"), _admin_headers())
        for u in resp.get("users") or []:
            if (u.get("email") or "").lower() == email.lower():
                return u
        return None
    except Exception as exc:
        _log.warning("_find_user_by_email failed: %s", exc)
        return None


def _create_user(email: str, password: str, role: str = "user") -> str:
    try:
        resp = _req(
            _auth_url("/admin/users"),
            _admin_headers(),
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "app_metadata": {"role": role},
            },
            method="POST",
        )
        return resp.get("id", "")
    except Exception as exc:
        _log.error("_create_user failed: %s", exc)
        raise


def _update_user(user_id: str, *, password: str | None = None, role: str | None = None) -> None:
    body: dict = {}
    if password:
        body["password"] = password
    if role:
        body["app_metadata"] = {"role": role}
    if not body:
        return
    url = _auth_url(f"/admin/users/{user_id}")
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=_admin_headers(), method="PUT")
    try:
        urllib.request.urlopen(req, timeout=15).close()
    except Exception as exc:
        _log.warning("_update_user failed: %s", exc)

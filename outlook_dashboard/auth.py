from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path

from .text_utils import utc_now_iso


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode(), 260_000)
    return f"pbkdf2:sha256:260000:{salt}:{key.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, alg, iters, salt, stored_key = stored.split(":")
        key = hashlib.pbkdf2_hmac(alg, password.encode("utf-8"), salt.encode(), int(iters))
        return hmac.compare_digest(key.hex(), stored_key)
    except Exception:
        return False


# ── user CRUD ────────────────────────────────────────────────────────────────

def ensure_admin(email: str, password: str, db_path: Path | None = None) -> None:
    """Create or repair the configured admin account."""
    from .database import managed_connect
    normalized_email = email.lower().strip()
    with managed_connect(db_path) as db:
        existing = db.execute(
            "SELECT id, password_hash, role FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO users (email, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                (normalized_email, _hash_password(password), utc_now_iso()),
            )
            return
        if existing["role"] != "admin" or not _verify_password(password, existing["password_hash"]):
            db.execute(
                "UPDATE users SET password_hash = ?, role = 'admin' WHERE id = ?",
                (_hash_password(password), existing["id"]),
            )


def create_user(
    email: str,
    password: str,
    role: str = "user",
    invited_by_id: int | None = None,
    db_path: Path | None = None,
) -> int:
    from .database import managed_connect
    with managed_connect(db_path) as db:
        cursor = db.execute(
            "INSERT INTO users (email, password_hash, role, invited_by_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (email.lower().strip(), _hash_password(password), role, invited_by_id, utc_now_iso()),
        )
        return int(cursor.lastrowid)


def authenticate_user(email: str, password: str, db_path: Path | None = None) -> dict | None:
    from .database import managed_connect
    with managed_connect(db_path) as db:
        row = db.execute(
            "SELECT id, email, password_hash, role FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
    if not row or not _verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"], "role": row["role"]}


def create_session(user_id: int, db_path: Path | None = None) -> str:
    from .database import managed_connect
    session_id = secrets.token_urlsafe(40)
    # expires in 30 days
    from datetime import datetime, timedelta
    expires_at = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    with managed_connect(db_path) as db:
        db.execute(
            "INSERT INTO sessions (session_id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, expires_at, utc_now_iso()),
        )
        db.execute("UPDATE users SET last_login = ? WHERE id = ?", (utc_now_iso(), user_id))
    return session_id


def get_session_user(session_id: str, db_path: Path | None = None) -> dict | None:
    if not session_id:
        return None
    from .database import managed_connect
    with managed_connect(db_path) as db:
        row = db.execute(
            """
            SELECT u.id, u.email, u.role
            FROM sessions s JOIN users u ON s.user_id = u.id
            WHERE s.session_id = ? AND s.expires_at > datetime('now')
            """,
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_session(session_id: str, db_path: Path | None = None) -> None:
    from .database import managed_connect
    with managed_connect(db_path) as db:
        db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def reset_password(user_id: int, new_password: str, db_path: Path | None = None) -> None:
    from .database import managed_connect
    with managed_connect(db_path) as db:
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (_hash_password(new_password), user_id),
        )


def delete_user(user_id: int, db_path: Path | None = None) -> None:
    from .database import managed_connect
    with managed_connect(db_path) as db:
        db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))


def create_reset_token(email: str, db_path: Path | None = None, hours: int = 1) -> str | None:
    """Generate a password-reset token. Returns token or None if email unknown."""
    from datetime import datetime, timedelta
    from .database import managed_connect
    with managed_connect(db_path) as db:
        row = db.execute("SELECT id FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        if not row:
            return None
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
        db.execute(
            "INSERT INTO password_reset_tokens (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token, row["id"], expires_at, utc_now_iso()),
        )
    return token


def send_invite_email(to_email: str, token: str, base_url: str, settings) -> None:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    set_pw_url = f"{base_url}/reset-password?token={token}"
    from_addr = settings.smtp_from or settings.smtp_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "You've been invited to ReplyRight"
    msg["From"] = from_addr
    msg["To"] = to_email

    text_body = (
        f"Hi,\n\nYou've been invited to ReplyRight — the Waldorf Astoria New York reservations triage tool.\n\n"
        f"Click the link below to set your password and get started (link expires in 24 hours):\n{set_pw_url}\n\n"
        f"Your login email will be: {to_email}\n\n"
        f"— ReplyRight"
    )
    html_body = f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e8e8e8;padding:40px 24px;max-width:480px;margin:0 auto">
<h2 style="color:#fff;margin-bottom:8px">Welcome to ReplyRight</h2>
<p style="color:rgba(255,255,255,0.55);margin-bottom:6px">You've been invited to <strong style="color:#e8e8e8">ReplyRight</strong> — the Waldorf Astoria New York reservations triage tool.</p>
<p style="color:rgba(255,255,255,0.55);margin-bottom:6px">Your login email: <strong style="color:#e8e8e8">{to_email}</strong></p>
<p style="color:rgba(255,255,255,0.55);margin-bottom:28px">Click below to set your password and get started. This link expires in <strong style="color:#e8e8e8">24 hours</strong>.</p>
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

    reset_url = f"{base_url}/reset-password?token={token}"
    from_addr = settings.smtp_from or settings.smtp_user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "ReplyRight — Password Reset Request"
    msg["From"] = from_addr
    msg["To"] = to_email

    text_body = (
        f"Hi,\n\nA password reset was requested for your ReplyRight account ({to_email}).\n\n"
        f"Reset link (expires in 1 hour):\n{reset_url}\n\n"
        f"If you didn't request this, ignore this email — your password won't change.\n\n"
        f"— ReplyRight"
    )
    html_body = f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e8e8e8;padding:40px 24px;max-width:480px;margin:0 auto">
<h2 style="color:#fff;margin-bottom:8px">ReplyRight — Password Reset</h2>
<p style="color:rgba(255,255,255,0.55);margin-bottom:6px">A reset was requested for <strong style="color:#e8e8e8">{to_email}</strong>.</p>
<p style="color:rgba(255,255,255,0.55);margin-bottom:28px">This link expires in <strong style="color:#e8e8e8">1 hour</strong>.</p>
<a href="{reset_url}" style="display:inline-block;background:#5b6af0;color:#fff;padding:13px 28px;border-radius:7px;text-decoration:none;font-weight:600;letter-spacing:.02em">Reset My Password</a>
<p style="margin-top:36px;color:rgba(255,255,255,0.25);font-size:.8em">If you didn't request this, ignore this email — your password won't change.<br>Waldorf Astoria New York · Reservations</p>
</body></html>"""

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(from_addr, [to_email], msg.as_string())


def list_users(db_path: Path | None = None) -> list[dict]:
    from .database import managed_connect
    with managed_connect(db_path) as db:
        rows = db.execute(
            """
            SELECT u.id, u.email, u.role, u.created_at, u.last_login,
                   inv.email AS invited_by_email
            FROM users u LEFT JOIN users inv ON u.invited_by_id = inv.id
            ORDER BY u.role DESC, u.created_at
            """,
        ).fetchall()
    return [dict(r) for r in rows]

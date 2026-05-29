"""
ReplyRight runtime diagnostics log.

Captures API requests, errors, Outlook export attempts, and AI call outcomes
for post-hoc debugging without logging email body content, credentials, or tokens.

Log location: data/replyright-runtime.log  (rotates at 5 MB, keeps 3 backups)
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

_CONFIGURED = False
_HANDLER: logging.handlers.RotatingFileHandler | None = None

SAFE_EVENTS = {
    "outlook.import",
    "api.error",
    "classifier.train",
    "redaction.presidio_unavailable",
    "redaction.presidio_failed",
    "redaction.completed",
    "supabase.sync",
    "ui.startup",
    "health.smoke",
    "training.import",
    "training.upload",
    "training.purge",
}

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]?\d{4}(?!\d)")
_PAYMENT_LINK_RE = re.compile(
    r"\bhttps?://[^\s<>]*(?:sertifi|payment|pay|checkout|invoice|folio)[^\s<>]*",
    re.IGNORECASE,
)
_CONFIRMATION_RE = re.compile(
    r"\b((?:confirmation|conf\.?|reservation|res\.?|booking|folio|case)"
    r"\s*(?:number|no\.?|#|id)?\s*[:#-]?\s*)[A-Z0-9-]{6,18}\b",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{12,}", re.IGNORECASE)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{8,}\b")
_API_KEY_RE = re.compile(
    r"\b(?:sk-(?:proj-)?[A-Za-z0-9_\-]{10,}|sk-ant-[A-Za-z0-9_\-]{10,}|AIza[A-Za-z0-9_\-]{30,})\b"
)
_SESSION_TOKEN_RE = re.compile(r"\b(?:session|cookie|token|api[_-]?key|service[_-]?role)[=:]\s*[^,\s;]{6,}", re.IGNORECASE)
_CARDISH_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

_SENSITIVE_FIELD_HINTS = (
    "body",
    "content",
    "cookie",
    "secret",
    "token",
    "api_key",
    "apikey",
    "service_role",
    "authorization",
    "password",
)


def configure(data_dir: Path) -> None:
    """Wire a rotating file handler into the 'replyright' logger hierarchy.

    Safe to call multiple times — only configures once.
    """
    global _CONFIGURED, _HANDLER
    if _CONFIGURED:
        return
    _CONFIGURED = True

    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "replyright-runtime.log"

    _HANDLER = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _HANDLER.setFormatter(fmt)
    _HANDLER.setLevel(logging.DEBUG)

    root = logging.getLogger("replyright")
    root.setLevel(logging.DEBUG)
    root.addHandler(_HANDLER)
    root.propagate = False

    # Capture uvicorn errors in the same file so crashes appear alongside
    # the API call that preceded them.
    for name in ("uvicorn.error",):
        lg = logging.getLogger(name)
        lg.addHandler(_HANDLER)

    root.info("Runtime log started: %s", log_path)


def get_logger(subsystem: str = "") -> logging.Logger:
    name = f"replyright.{subsystem}" if subsystem else "replyright"
    return logging.getLogger(name)


def scrub_log_value(value: Any) -> Any:
    """Return a log-safe representation of value without guest data or secrets."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(hint in key_text.lower() for hint in _SENSITIVE_FIELD_HINTS):
                safe[key_text] = "[REDACTED]"
            else:
                safe[key_text] = scrub_log_value(item)
        return safe
    if isinstance(value, (list, tuple, set)):
        return [scrub_log_value(item) for item in list(value)[:20]]

    text = str(value)
    text = _BEARER_RE.sub("Bearer [REDACTED_TOKEN]", text)
    text = _JWT_RE.sub("[REDACTED_TOKEN]", text)
    text = _API_KEY_RE.sub("[REDACTED_API_KEY]", text)
    text = _SESSION_TOKEN_RE.sub(lambda m: m.group(0).split("=", 1)[0].split(":", 1)[0] + "=[REDACTED]", text)
    text = _PAYMENT_LINK_RE.sub("[REDACTED_PAYMENT_LINK]", text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _CONFIRMATION_RE.sub(lambda m: f"{m.group(1)}[REDACTED_CONFIRMATION]", text)
    text = _CARDISH_RE.sub("[REDACTED_NUMBER]", text)
    if len(text) > 500:
        text = text[:500] + "...[TRUNCATED]"
    return text


def safe_log(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Log a structured event after scrubbing sensitive field values."""
    safe_fields = {}
    for key, value in fields.items():
        key_text = str(key)
        if any(hint in key_text.lower() for hint in _SENSITIVE_FIELD_HINTS):
            safe_fields[key_text] = "[REDACTED]"
        else:
            safe_fields[key_text] = scrub_log_value(value)
    parts = [f"event={scrub_log_value(event)}"]
    parts.extend(f"{key}={safe_fields[key]!r}" for key in sorted(safe_fields))
    logger.log(level, " ".join(parts))


def make_request_logging_middleware(app_callable: Callable) -> Callable:
    """ASGI middleware that logs every HTTP request — method, path, status, timing.

    Never reads or logs request/response body content.
    """
    logger = get_logger("http")

    async def middleware(scope, receive, send):
        if scope["type"] != "http":
            await app_callable(scope, receive, send)
            return

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        qs = scope.get("query_string", b"").decode("utf-8", errors="replace")
        start = time.perf_counter()
        status_code = 0

        async def send_with_logging(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        try:
            await app_callable(scope, receive, send_with_logging)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "%s %s%s — UNHANDLED %s (%.0f ms)",
                method,
                path,
                f"?{qs}" if qs else "",
                type(exc).__name__,
                elapsed_ms,
                exc_info=True,
            )
            raise
        else:
            elapsed_ms = (time.perf_counter() - start) * 1000
            level = logging.WARNING if status_code >= 400 else logging.INFO
            logger.log(
                level,
                "%s %s%s — %s (%.0f ms)",
                method,
                path,
                f"?{qs}" if qs else "",
                status_code,
                elapsed_ms,
            )

    return middleware

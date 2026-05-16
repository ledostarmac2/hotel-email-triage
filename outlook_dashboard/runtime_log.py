"""
ReplyRight runtime diagnostics log.

Captures API requests, errors, Outlook export attempts, and AI call outcomes
for post-hoc debugging without logging email body content, credentials, or tokens.

Log location: data/replyright-runtime.log  (rotates at 5 MB, keeps 3 backups)
"""
from __future__ import annotations

import logging
import logging.handlers
import time
from pathlib import Path
from typing import Callable

_CONFIGURED = False
_HANDLER: logging.handlers.RotatingFileHandler | None = None


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

from __future__ import annotations

import html
import re
from datetime import UTC
from typing import Any

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    lines = [WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def graph_email_address(value: dict[str, Any] | None) -> tuple[str, str]:
    address = (value or {}).get("emailAddress") or {}
    return (address.get("name") or "", (address.get("address") or "").lower())


def utc_now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()

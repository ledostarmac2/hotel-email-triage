"""
ExecutiveSummaryPlugin — token-optimized email thread cleaner.

Strips HTML, removes quoted threads, signatures, legal disclaimers,
confidentiality footers, and tracking noise before content reaches the LLM.
Reduces token cost without losing the signal the LLM actually needs.
"""
from __future__ import annotations

import re

from semantic_kernel.functions import kernel_function

# Conservative token budget: ~2 000 tokens ≈ 8 000 chars of English prose
DEFAULT_MAX_CHARS = 8_000

# ── HTML ─────────────────────────────────────────────────────────────────────
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)
_HTML_ENTITY_RE = re.compile(r"&(?:[a-zA-Z]+|#\d+);")

# ── Quoted Outlook threads ───────────────────────────────────────────────────
# Matches the "-----Original Message-----" / "-----Forwarded Message-----" block
# and the inline "From: … Sent: … To: … Subject: …" header pattern.
_QUOTED_HEADER_RE = re.compile(
    r"(-{3,}|_{3,})\s*(Original Message|Forwarded Message).*",
    re.IGNORECASE | re.DOTALL,
)
_INLINE_FROM_BLOCK_RE = re.compile(
    r"\n(From:.*?Sent:.*?To:.*?Subject:.*?\n)",
    re.IGNORECASE | re.DOTALL,
)
# Lines that start with ">" (inline quote markers)
_INLINE_QUOTE_LINE_RE = re.compile(r"^>+\s?.*$", re.MULTILINE)

# ── Signatures ───────────────────────────────────────────────────────────────
# Signature separator: a line of dashes/underscores alone on a line
_SIGNATURE_SEPARATOR_RE = re.compile(r"\n[-–—_]{2,}\s*\n.*", re.DOTALL)
_SENT_FROM_RE = re.compile(
    r"\n(Sent from (my |the )?(iPhone|Android|BlackBerry|iPad|Samsung|mobile|phone))\b.*",
    re.IGNORECASE | re.DOTALL,
)

# ── Legal disclaimers / confidentiality footers ──────────────────────────────
_LEGAL_DISCLAIMER_RE = re.compile(
    r"(This\s+(?:e[- ]?mail|message|communication)[\s\S]{0,80}"
    r"(?:confidential|intended only|privileged))[\s\S]*",
    re.IGNORECASE,
)
_CONFIDENTIALITY_HEADER_RE = re.compile(
    r"(CONFIDENTIALITY NOTICE|DISCLAIMER|LEGAL NOTICE|PRIVILEGED AND CONFIDENTIAL)[\s\S]*",
    re.IGNORECASE,
)

# ── Tracking / marketing footer noise ────────────────────────────────────────
_TRACKING_FOOTER_RE = re.compile(
    r"(Unsubscribe|View in browser|Update (?:your )?preferences"
    r"|©\s*\d{4}|All rights reserved)[\s\S]*",
    re.IGNORECASE,
)

# ── Whitespace normalisation ─────────────────────────────────────────────────
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


class ExecutiveSummaryPlugin:
    """
    Strips and compresses raw Outlook email/thread content into a lean,
    token-optimised payload before it reaches the LLM.
    """

    def __init__(self, max_chars: int = DEFAULT_MAX_CHARS) -> None:
        self._max_chars = max_chars

    @kernel_function(
        name="clean",
        description=(
            "Strip HTML, remove quoted threads, signatures, legal disclaimers, "
            "and tracking footers. Returns a clean, token-optimised text payload. "
            "Pass max_chars > 0 to override the instance default."
        ),
    )
    def clean(self, raw_content: str = "", max_chars: int = 0) -> str:
        limit = max_chars if max_chars > 0 else self._max_chars
        text = _strip_html(raw_content)
        text = _remove_quoted_threads(text)
        text = _remove_signatures(text)
        text = _remove_legal_footers(text)
        text = _remove_tracking_noise(text)
        text = _collapse_whitespace(text)
        return _truncate(text, limit).strip()


# ── Private helpers ───────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HTML_ENTITY_RE.sub(" ", text)
    return text


def _remove_quoted_threads(text: str) -> str:
    text = _QUOTED_HEADER_RE.sub("\n[prior thread removed]", text)
    text = _INLINE_FROM_BLOCK_RE.sub("\n[message header removed]\n", text)
    text = _INLINE_QUOTE_LINE_RE.sub("", text)
    return text


def _remove_signatures(text: str) -> str:
    text = _SIGNATURE_SEPARATOR_RE.sub("", text)
    text = _SENT_FROM_RE.sub("", text)
    return text


def _remove_legal_footers(text: str) -> str:
    text = _LEGAL_DISCLAIMER_RE.sub("[legal footer removed]", text)
    text = _CONFIDENTIALITY_HEADER_RE.sub("[confidentiality notice removed]", text)
    return text


def _remove_tracking_noise(text: str) -> str:
    return _TRACKING_FOOTER_RE.sub("", text)


def _collapse_whitespace(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)
    return _MULTI_BLANK_RE.sub("\n\n", text)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated at {limit} chars]"

"""Local, privacy-safe helpers for follow-up and duplicate-thread scoring."""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

try:  # pragma: no cover - exercised through monkeypatch fallback tests
    from rapidfuzz import fuzz as _rapidfuzz_fuzz
except Exception:  # pragma: no cover
    _rapidfuzz_fuzz = None

_PREFIX_RE = re.compile(r"^\s*(?:(?:re|fw|fwd)\s*:\s*)+", re.IGNORECASE)
_CONFIRMATION_TOKEN_RE = re.compile(r"\b[A-Z0-9][A-Z0-9-]{5,18}\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z0-9]+")
_FOLLOW_UP_PHRASES = (
    "following up",
    "follow up",
    "follow-up",
    "any update",
    "checking in",
    "checking back",
    "circling back",
    "touching base",
    "second request",
    "please proceed",
    "sent again",
    "still waiting",
)
_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "please",
    "reservation",
    "booking",
    "confirmation",
}


def normalize_subject(subject: object) -> str:
    """Normalize a subject for local comparison without preserving IDs."""
    text = _PREFIX_RE.sub("", str(subject or "")).lower()
    text = _CONFIRMATION_TOKEN_RE.sub(lambda match: " " if _looks_identifier_like(match.group(0)) else match.group(0), text)
    tokens = [token for token in _WORD_RE.findall(text) if token not in _STOP_WORDS]
    return " ".join(tokens)


def subject_similarity(left: object, right: object) -> float:
    """Return 0..1 subject similarity using rapidfuzz when available."""
    a = normalize_subject(left)
    b = normalize_subject(right)
    if not a or not b:
        return 0.0
    if _rapidfuzz_fuzz is not None:
        return round(float(_rapidfuzz_fuzz.token_set_ratio(a, b)) / 100.0, 4)
    return round(_token_overlap(a, b), 4)


def thread_match_score(
    current: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Score whether two sanitized message summaries likely belong together."""
    subject_score = subject_similarity(current.get("subject_tokens") or current.get("subject"), candidate.get("subject_tokens") or candidate.get("subject"))
    score = subject_score
    reasons: list[str] = []
    if subject_score >= 0.72:
        reasons.append("similar subject")

    current_domain = _domain(current)
    candidate_domain = _domain(candidate)
    if current_domain and candidate_domain and current_domain == candidate_domain:
        score = min(1.0, score + 0.12)
        reasons.append("same sender domain")

    combined_text = " ".join(
        str(part or "")
        for part in (
            current.get("subject_tokens"),
            current.get("body_redacted"),
            candidate.get("subject_tokens"),
            candidate.get("body_redacted"),
        )
    )
    if is_likely_followup_text(combined_text):
        score = min(1.0, score + 0.10)
        reasons.append("follow-up wording")

    if not reasons:
        reasons.append("weak local match")
    return {"score": round(score, 4), "reasons": reasons}


def is_likely_followup_text(text: object) -> bool:
    lower = str(text or "").lower()
    return any(phrase in lower for phrase in _FOLLOW_UP_PHRASES)


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _tokens(text: str) -> Iterable[str]:
    return (token for token in _WORD_RE.findall(text.lower()) if token not in _STOP_WORDS)


def _domain(row: Mapping[str, Any]) -> str:
    if row.get("sender_domain"):
        return str(row.get("sender_domain") or "").lower()
    email = str(row.get("sender_email") or "")
    return email.split("@", 1)[-1].lower() if "@" in email else ""


def _looks_identifier_like(token: str) -> bool:
    return any(ch.isdigit() for ch in token) or "-" in token

"""Arrival-window urgency scoring for hotel email intelligence.

The engine consumes already-extracted entities and travel-program metadata. It
is pure and deterministic, with no database, network, or Outlook side effects.
"""

from __future__ import annotations

import re
from typing import Any

VIP_PROGRAMS = {"STARS", "Virtuoso", "FHR", "FS_Preferred"}

RISK_KEYWORDS: tuple[str, ...] = (
    "chargeback",
    "legal",
    "lawyer",
    "attorney",
    "medical",
    "accessibility",
    "ada",
    "allergy",
    "allergic",
)
BILLING_KEYWORDS: tuple[str, ...] = (
    "billing dispute",
    "dispute",
    "refund",
    "overcharged",
    "incorrect charge",
    "charge issue",
    "folio error",
)
COMPLAINT_KEYWORDS: tuple[str, ...] = (
    "complaint",
    "upset",
    "unacceptable",
    "disappointed",
    "angry",
)
CANCELLATION_KEYWORDS: tuple[str, ...] = (
    "cancel",
    "cancellation",
    "cancelled",
)
THANK_YOU_KEYWORDS: tuple[str, ...] = (
    "thank you",
    "thanks",
    "appreciate it",
    "confirmed",
    "all set",
    "acknowledged",
)
ACTIONABLE_KEYWORDS: tuple[str, ...] = (
    "please",
    "can you",
    "could you",
    "would you",
    "need",
    "request",
    "confirm",
    "advise",
    "update",
    "book",
    "reserve",
    "cancel",
    "modify",
    "change",
    "send",
    "arrange",
    "assist",
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _hint_contains(category_hint: str | None, keywords: tuple[str, ...]) -> bool:
    lowered = (category_hint or "").lower()
    return any(keyword in lowered for keyword in keywords)


def _arrival_window(entities: dict[str, Any]) -> int | None:
    value = entities.get("arrival_window_hours")
    return value if isinstance(value, int) else None


def _is_actionable(text: str) -> bool:
    if _contains_any(text, ACTIONABLE_KEYWORDS):
        return True
    return bool(re.search(r"\?\s*$|\?\s", text))


def compute_urgency(
    subject: str,
    body: str,
    entities: dict[str, Any],
    program: dict[str, Any],
    category_hint: str | None = None,
    has_risk_flags: bool = False,
) -> tuple[int, str]:
    """Compute a 1-5 urgency level and concise plain-English reason."""
    text = f"{subject or ''}\n{body or ''}"
    window = _arrival_window(entities)
    reasons: list[str] = []
    level = 1
    forced_higher = False

    if has_risk_flags or _contains_any(text, RISK_KEYWORDS):
        level = 4
        forced_higher = True
        reasons.append("risk flags")
    elif window is not None and window <= 12:
        level = 5
        forced_higher = True
        reasons.append(f"arrival in {window} hours")
    elif window is not None and window <= 48:
        level = 4
        forced_higher = True
        reasons.append(f"arrival in {window} hours")
    elif window is not None and window <= 24 * 7:
        level = 3
        forced_higher = True
        reasons.append("arrival within 7 days")
    elif (
        _hint_contains(category_hint, ("billing", "complaint", "accessibility"))
        or _contains_any(text, BILLING_KEYWORDS)
        or _contains_any(text, COMPLAINT_KEYWORDS)
    ):
        level = 4
        forced_higher = True
        if _hint_contains(category_hint, ("accessibility",)) or "accessibility" in text.lower():
            reasons.append("accessibility issue")
        elif _hint_contains(category_hint, ("complaint",)) or _contains_any(text, COMPLAINT_KEYWORDS):
            reasons.append("complaint")
        else:
            reasons.append("billing dispute")
    else:
        if _is_actionable(text):
            level = 2
            reasons.append("actionable request")
        else:
            level = 1
            reasons.append("no action needed")

    cancellation_future = (
        _contains_any(text, CANCELLATION_KEYWORDS)
        and window is not None
        and window > 24 * 7
        and not forced_higher
    )
    if cancellation_future:
        level = max(level, 2)
        reasons = ["cancellation more than 7 days out"]

    program_name = program.get("program")
    if program_name in VIP_PROGRAMS:
        previous = level
        level = min(5, level + 1)
        if level > previous:
            reasons.append("VIP boost")

    if cancellation_future and level > 3:
        level = 3

    thank_you = _contains_any(text, THANK_YOU_KEYWORDS)
    if thank_you and not forced_higher:
        level = min(level, 2)
        if reasons == ["no action needed"]:
            reasons = ["thank-you or acknowledgment"]
        elif "thank-you or acknowledgment" not in reasons:
            reasons.append("thank-you cap")

    reason = " + ".join(reasons[:3]) if reasons else "default"
    return level, f"L{level} - {reason}"

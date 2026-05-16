from __future__ import annotations

import re


CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
CVV_RE = re.compile(
    r"\b(cvv|cvc|security code|card code)\s*[:#-]?\s*\d{3,4}\b",
    re.IGNORECASE,
)
EXPIRY_RE = re.compile(
    r"\b(exp(?:iration)?(?: date)?|expires)\s*[:#-]?\s*(0?[1-9]|1[0-2])\s*/\s*\d{2,4}\b",
    re.IGNORECASE,
)


def _luhn_valid(number: str) -> bool:
    digits = [int(ch) for ch in number if ch.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def redact_sensitive_text(text: str) -> tuple[str, dict[str, int]]:
    counts = {"cards": 0, "cvv": 0, "expiry": 0}

    def replace_card(match: re.Match[str]) -> str:
        candidate = match.group(0)
        digits = re.sub(r"\D", "", candidate)
        if _luhn_valid(digits):
            counts["cards"] += 1
            return "[REDACTED_CARD]"
        return candidate

    redacted = CARD_CANDIDATE_RE.sub(replace_card, text)
    redacted, cvv_count = CVV_RE.subn("[REDACTED_CVV]", redacted)
    redacted, expiry_count = EXPIRY_RE.subn("[REDACTED_EXPIRY]", redacted)
    counts["cvv"] = cvv_count
    counts["expiry"] = expiry_count
    return redacted, counts

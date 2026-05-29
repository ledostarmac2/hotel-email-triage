from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

from .config import get_settings
from .runtime_log import get_logger, safe_log

CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
CVV_RE = re.compile(
    r"\b(cvv|cvc|security code|card code)\s*[:#-]?\s*\d{3,4}\b",
    re.IGNORECASE,
)
EXPIRY_RE = re.compile(
    r"\b(exp(?:iration)?(?: date)?|expires)\s*[:#-]?\s*(0?[1-9]|1[0-2])\s*/\s*\d{2,4}\b",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]?\d{4}(?!\d)")
PAYMENT_LINK_RE = re.compile(
    r"\bhttps?://[^\s<>]*(?:sertifi|payment|pay|checkout|invoice|folio)[^\s<>]*",
    re.IGNORECASE,
)
CONFIRMATION_RE = re.compile(
    r"\b((?:confirmation|conf\.?|reservation|res\.?|booking|folio|case|"
    r"confirmaci[oó]n|confirma[cç][aã]o|conferma|best[aä]tigung|"
    r"r[eé]servation|reserva|prenotazione|reservierung|buchung)"
    r"\s*(?:number|no\.?|#|id)?\s*[:#-]?\s*)[A-Z0-9-]{6,18}\b",
    re.IGNORECASE,
)

_log = get_logger("redaction")


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
    counts = {
        "cards": 0,
        "cvv": 0,
        "expiry": 0,
        "emails": 0,
        "phones": 0,
        "payment_links": 0,
        "confirmation_numbers": 0,
    }

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
    redacted, payment_link_count = PAYMENT_LINK_RE.subn("[REDACTED_PAYMENT_LINK]", redacted)
    redacted, email_count = EMAIL_RE.subn("[REDACTED_EMAIL]", redacted)
    redacted, phone_count = PHONE_RE.subn("[REDACTED_PHONE]", redacted)
    redacted, confirmation_count = CONFIRMATION_RE.subn(
        lambda match: f"{match.group(1)}[REDACTED_CONFIRMATION]",
        redacted,
    )
    counts["cvv"] = cvv_count
    counts["expiry"] = expiry_count
    counts["emails"] = email_count
    counts["phones"] = phone_count
    counts["payment_links"] = payment_link_count
    counts["confirmation_numbers"] = confirmation_count
    redacted, presidio_counts = _apply_presidio_second_pass(redacted)
    counts.update(presidio_counts)
    return redacted, counts


def _presidio_enabled() -> bool:
    try:
        return bool(get_settings().enable_presidio_redaction)
    except Exception:
        return False


@lru_cache(maxsize=1)
def _get_presidio_engines() -> tuple[Any, Any]:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine

    return AnalyzerEngine(), AnonymizerEngine()


def _apply_presidio_second_pass(text: str) -> tuple[str, dict[str, int]]:
    if not text or not _presidio_enabled():
        return text, {}

    try:
        analyzer, anonymizer = _get_presidio_engines()
    except Exception as exc:
        safe_log(
            _log,
            logging.WARNING,
            "redaction.presidio_unavailable",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return text, {}

    try:
        results = analyzer.analyze(text=text, language="en")
        if not results:
            return text, {"presidio_entities": 0}
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        counts: dict[str, int] = {"presidio_entities": len(results)}
        for result in results:
            entity = str(getattr(result, "entity_type", "entity") or "entity").lower()
            key = "presidio_" + re.sub(r"[^a-z0-9]+", "_", entity).strip("_")
            counts[key] = counts.get(key, 0) + 1
        return str(getattr(anonymized, "text", text)), counts
    except Exception as exc:
        safe_log(
            _log,
            logging.WARNING,
            "redaction.presidio_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return text, {}

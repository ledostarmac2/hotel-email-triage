"""Luxury travel-program detection for ReplyRight.

The detector combines sender-domain hints with conservative body/signature
keywords. It is pure Python and intentionally performs no I/O or network calls.
"""

from __future__ import annotations

import re
from email.utils import parseaddr
from typing import Any

DOMAIN_REGISTRY: dict[str, str] = {
    "virtuoso.com": "Virtuoso",
    "*.virtuoso.com": "Virtuoso",
    "amexgbt.com": "FHR",
    "americanexpress.com": "FHR",
    "signaturetravelnetwork.com": "Signature",
    "mrandmrssmith.com": "Mr_and_Mrs_Smith",
    "fourseasons.com": "FS_Preferred",
    "hilton.com": "Internal_Hilton",
    "hiltonhonors.com": "Internal_Hilton",
}

VIP_PROGRAMS = {"STARS", "Virtuoso", "FHR", "FS_Preferred"}

_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("FHR", re.compile(r"\b(?:fine hotels\s*&\s*resorts|fhr|amex platinum cardholder)\b", re.I)),
    ("Virtuoso", re.compile(r"\bvirtuoso\s+(?:member|advisor|booking|amenities|rate)\b", re.I)),
    ("STARS", re.compile(r"\b(?:stars\s+booking|starwood\s+luxury)\b", re.I)),
    ("Signature", re.compile(r"\bsignature\s+travel\s+network\b", re.I)),
    ("Mr_and_Mrs_Smith", re.compile(r"\bmr\s*&\s*mrs\s+smith\b|\bmrandmrssmith\b", re.I)),
    ("Impresario", re.compile(r"\bimpresario\b", re.I)),
    ("Hyatt_Prive", re.compile(r"\bhyatt\s+priv(?:e|e?)\b", re.I)),
    ("FS_Preferred", re.compile(r"\bfour\s+seasons\s+preferred\b|\bfs\s+preferred\b", re.I)),
)

_FROM_AT_RE = re.compile(
    r"\bfrom\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+at\s+([A-Z][A-Za-z&.' -]{2,80})",
)
_NAME_LINE_RE = re.compile(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})$", re.M)
_AGENCY_LINE_RE = re.compile(r"^([A-Z][A-Za-z&.' -]{2,80}(?:Travel|Agency|Advisors|Concierge|Tours))$", re.M)


def _domain_from_email(sender_email: str) -> str | None:
    _, address = parseaddr(sender_email or "")
    if "@" not in address:
        return None
    return address.rsplit("@", 1)[1].lower()


def _program_from_domain(domain: str | None) -> tuple[str | None, float]:
    if not domain:
        return None, 0.0
    if domain.endswith(".virtuoso.com") or domain == "virtuoso.com":
        return "Virtuoso", 0.92
    if domain in {"hilton.com", "hiltonhonors.com"} or domain.endswith(".hilton.com"):
        return "Internal_Hilton", 0.95
    if domain == "fourseasons.com" or domain.endswith(".fourseasons.com"):
        return "FS_Preferred", 0.86
    direct = DOMAIN_REGISTRY.get(domain)
    if direct in {"Signature", "Mr_and_Mrs_Smith"}:
        return direct, 0.9
    if direct == "FHR":
        return None, 0.45
    return None, 0.0


def _program_from_keywords(text: str) -> tuple[str | None, float]:
    matches: list[str] = []
    for program, pattern in _KEYWORDS:
        if pattern.search(text):
            matches.append(program)
    if not matches:
        return None, 0.0
    if "FHR" in matches:
        return "FHR", 0.86
    if "Virtuoso" in matches:
        return "Virtuoso", 0.84
    return matches[0], 0.82


def _extract_advisor_and_agency(text: str) -> tuple[str | None, str | None]:
    match = _FROM_AT_RE.search(text)
    if match:
        return match.group(1).strip(), match.group(2).strip(" .")

    name_match = _NAME_LINE_RE.search(text)
    agency_match = _AGENCY_LINE_RE.search(text)
    if name_match and agency_match:
        return name_match.group(1).strip(), agency_match.group(1).strip()
    return None, None


def detect_program(sender_email: str, body: str, signature: str | None = None) -> dict[str, Any]:
    """Detect luxury travel-program metadata from sender and message text."""
    domain = _domain_from_email(sender_email)
    text = "\n".join(part for part in (body or "", signature or "") if part)
    domain_program, domain_confidence = _program_from_domain(domain)
    keyword_program, keyword_confidence = _program_from_keywords(text)

    program: str | None = None
    confidence = 0.0
    if domain_program and keyword_program and domain_program == keyword_program:
        program = domain_program
        confidence = min(1.0, max(domain_confidence, keyword_confidence) + 0.08)
    elif domain_program:
        program = domain_program
        confidence = domain_confidence
    elif keyword_program:
        program = keyword_program
        confidence = keyword_confidence
        if domain in {"amexgbt.com", "americanexpress.com"}:
            confidence = max(confidence, 0.78)
    elif domain in {"amexgbt.com", "americanexpress.com"}:
        program = None
        confidence = domain_confidence

    advisor_name, agency_name = _extract_advisor_and_agency(text)
    return {
        "program": program,
        "advisor_name": advisor_name,
        "agency_name": agency_name,
        "agency_domain": domain,
        "confidence": round(confidence, 2),
    }

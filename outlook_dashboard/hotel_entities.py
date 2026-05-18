"""Hotel entity extractor for Waldorf Astoria New York email triage.

Pure-Python regex + dateparser extractor.  Returns a typed dict:

    {
        "confirmation_numbers": [...],
        "arrival_date":         "2025-12-24" | None,
        "departure_date":       "2025-12-26" | None,
        "nights":               2 | None,
        "room_category":        "Junior Suite" | None,
        "rate_code":            "AAAAA" | None,
        "guest_count":          {"adults": 2, "children": 1} | None,
        "arrival_window_hours": 36 | None,
    }

All fields are always present; unknown / unparseable values are None / [].
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import dateparser

# ── Room category registry (order matters — most-specific first) ──────────────
_ROOM_CATEGORIES: list[tuple[str, re.Pattern[str]]] = [
    ("Presidential Suite", re.compile(r"\bpresidential\s+suite\b", re.I)),
    ("Royal Suite",        re.compile(r"\broyal\s+suite\b", re.I)),
    ("Astoria Suite",      re.compile(r"\bastoria\s+suite\b", re.I)),
    ("Tower Suite",        re.compile(r"\btower\s+suite\b", re.I)),
    ("Junior Suite",       re.compile(r"\bjunior\s+suite\b", re.I)),
    ("Towers",             re.compile(r"\btowers?\s+(?:room|king|queen|double|floor|residence|studio)\b|\btowers\s+access\b|\bwaldorf\s+towers\b|\bon\s+the\s+towers\b", re.I)),
    ("Premier",            re.compile(r"\bpremier\s+(?:room|king|queen|double|view|park|city|suite)?\b", re.I)),
    ("Deluxe",             re.compile(r"\bdeluxe\s+(?:room|king|queen|double|view|park|city)?\b", re.I)),
]

# ── Confirmation number patterns ──────────────────────────────────────────────
# Hilton/OnQ: 8-digit numeric or alphanumeric starting with a letter.
# Strategy: require a keyword prefix THEN a separator ([\s:#]+) THEN the value.
# The separator group prevents the value capture from accidentally consuming keyword text.
_CONF_KW = r"(?:conf(?:irmation)?|res(?:ervation)?|booking\s+ref(?:erence)?|ref(?:erence)?|hilton\s+honors)"
_CONF_SEP = r"[\s.#:]*(?:number|num|no|ref)?[\s.#:]*"
_CONF_PATTERNS = [
    # keyword + separator + 8-10 pure digit run
    re.compile(rf"\b{_CONF_KW}{_CONF_SEP}([0-9]{{8,10}})\b", re.I),
    # keyword + separator + letter-led alphanumeric (e.g. ABC12345)
    re.compile(rf"\b{_CONF_KW}{_CONF_SEP}([A-Z][0-9A-Z]{{5,9}})\b", re.I),
    # Inline: "Conf# ABC12345" or "Res#: 12345678"
    re.compile(r"\bconf(?:irmation)?(?:\s+no\.?|#|:)\s*([A-Z0-9]{6,10})\b", re.I),
    # Mixed alphanumeric standalone (2-4 letters + 4-6 digits or vice-versa)
    # Only match when preceded by conf/res/booking keywords to reduce false positives
    re.compile(r"\b(?:conf|res|booking)\b[^a-z0-9]{0,10}\b([A-Z]{2,4}[0-9]{4,6}|[0-9]{6,10}[A-Z]{0,4})\b", re.I),
]

# ── Rate code patterns ────────────────────────────────────────────────────────
_RATE_CODE_RE = re.compile(
    r"(?:rate\s+code|rate\s+plan|promo\s+code|package\s+code|corporate\s+code|group\s+code|code)[\s:]+([A-Z0-9]{3,12})\b",
    re.I,
)

# ── Guest count patterns ──────────────────────────────────────────────────────
_ADULTS_RE  = re.compile(r"(\d+)\s+adult(?:s)?", re.I)
_CHILDREN_RE = re.compile(r"(\d+)\s+(?:child(?:ren)?|kid(?:s)?)", re.I)
_PAXCOUNT_RE = re.compile(r"(\d+)\s+(?:guest(?:s)?|person|people|pax|occupant(?:s)?)", re.I)

# ── Date parsing settings ─────────────────────────────────────────────────────
_DP_SETTINGS: dict[str, Any] = {
    "PREFER_DATES_FROM": "future",
    "RETURN_AS_TIMEZONE_AWARE": False,
    "PARSERS": ["custom-formats", "absolute-time", "relative-time", "timestamp"],
}

# Patterns that signal a CHECK-IN date is being described
_ARRIVAL_KEYWORDS = (
    "check.?in", "arrival", "arriving", "arrive", "checkin",
    "check in", "stay begins", "first night"
)
_DEPARTURE_KEYWORDS = (
    r"check(?:ing)?\s*out", "departure", "departing", "depart",
    "stay ends", "last night", "leaving on", "leave on"
)


_RELATIVE_DATE_MAP: dict[str, int] = {
    "tonight": 0,
    "today": 0,
    "tomorrow": 1,
    "day after tomorrow": 2,
    "monday": None, "tuesday": None, "wednesday": None, "thursday": None,
    "friday": None, "saturday": None, "sunday": None,
}

_WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _try_parse_date(text: str) -> datetime | None:
    """Attempt to parse a date string. Returns None on failure."""
    if not text or not text.strip():
        return None
    lower = text.strip().lower()

    # Handle relative terms manually (dateparser doesn't cover "tonight")
    if lower in ("tonight", "today"):
        return datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
    if lower == "tomorrow":
        return (datetime.now() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    if lower == "day after tomorrow":
        return (datetime.now() + timedelta(days=2)).replace(hour=15, minute=0, second=0, microsecond=0)

    # Handle bare weekday names ("next Thursday", "Friday the 24th" parsed below by dateparser)
    # For bare weekday like "Friday" we let dateparser handle it
    try:
        result = dateparser.parse(text.strip(), settings=_DP_SETTINGS)  # type: ignore[attr-defined]
        return result
    except Exception:
        return None


def _extract_confirmation_numbers(text: str) -> list[str]:
    found: set[str] = set()
    for pattern in _CONF_PATTERNS:
        for m in pattern.finditer(text):
            val = m.group(1).upper().strip()
            if len(val) >= 6:
                found.add(val)
    return sorted(found)


def _extract_room_category(text: str) -> str | None:
    for name, pattern in _ROOM_CATEGORIES:
        if pattern.search(text):
            return name
    # Generic "suite" fallback
    if re.search(r"\bsuite\b", text, re.I):
        return "Junior Suite"
    return None


def _extract_rate_code(text: str) -> str | None:
    m = _RATE_CODE_RE.search(text)
    if m:
        return m.group(1).upper()
    return None


def _extract_guest_count(text: str) -> dict[str, int] | None:
    adults = None
    children = None
    m = _ADULTS_RE.search(text)
    if m:
        adults = int(m.group(1))
    m2 = _CHILDREN_RE.search(text)
    if m2:
        children = int(m2.group(1))
    # If no explicit adults/children, look for generic guest count
    if adults is None and children is None:
        m3 = _PAXCOUNT_RE.search(text)
        if m3:
            adults = int(m3.group(1))
    if adults is not None or children is not None:
        result: dict[str, int] = {}
        if adults is not None:
            result["adults"] = adults
        if children is not None:
            result["children"] = children
        return result
    return None


# Sentence-level date extraction: find date expressions near arrival/departure keywords
_SENTENCE_SEP = re.compile(r"[.;!\n]")

# Simple date pattern fragments (for sentence extraction)
_DATE_FRAG = re.compile(
    r"""
    \b(
        (?:tonight|tomorrow|yesterday)
        |(?:next|this|last)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)
        |(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+the\s+\d{1,2}(?:st|nd|rd|th)?
        |(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)
        |(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?
        |\d{1,2}/\d{1,2}(?:/\d{2,4})?
        |\d{4}-\d{2}-\d{2}
        |\d{1,2}-\d{1,2}-\d{2,4}
        |\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{4})?
    )\b
    """,
    re.I | re.X,
)

_NIGHTS_RE = re.compile(r"(\d+)\s+night(?:s)?", re.I)


def _extract_dates(text: str) -> tuple[datetime | None, datetime | None, int | None]:
    """Return (arrival_dt, departure_dt, nights)."""
    arrival_dt: datetime | None = None
    departure_dt: datetime | None = None
    nights: int | None = None

    # Extract explicit nights count
    m_nights = _NIGHTS_RE.search(text)
    if m_nights:
        nights = int(m_nights.group(1))

    # Look for keyword-anchored dates
    lower = text.lower()

    arrival_candidates: list[datetime] = []
    departure_candidates: list[datetime] = []

    for kw in _ARRIVAL_KEYWORDS:
        for kw_match in re.finditer(kw, lower):
            # Search a 120-char window after the keyword
            window = text[kw_match.end():kw_match.end() + 120]
            for dm in _DATE_FRAG.finditer(window):
                parsed = _try_parse_date(dm.group(0))
                if parsed:
                    arrival_candidates.append(parsed)

    for kw in _DEPARTURE_KEYWORDS:
        for kw_match in re.finditer(kw, lower):
            window = text[kw_match.end():kw_match.end() + 120]
            for dm in _DATE_FRAG.finditer(window):
                parsed = _try_parse_date(dm.group(0))
                if parsed:
                    departure_candidates.append(parsed)

    # If no keyword-anchored dates, scan all date fragments and pick earliest as arrival
    if not arrival_candidates and not departure_candidates:
        all_dates = []
        for dm in _DATE_FRAG.finditer(text):
            parsed = _try_parse_date(dm.group(0))
            if parsed:
                all_dates.append(parsed)
        if all_dates:
            all_dates.sort()
            arrival_dt = all_dates[0]
            if len(all_dates) >= 2:
                departure_dt = all_dates[1]

    if arrival_candidates:
        arrival_dt = min(arrival_candidates)
    if departure_candidates:
        departure_dt = min(departure_candidates)

    # If we have arrival and nights but no departure, compute it
    if arrival_dt and nights and not departure_dt:
        from datetime import timedelta
        departure_dt = arrival_dt + timedelta(days=nights)

    # If we have both dates, compute nights if not already set
    if arrival_dt and departure_dt and nights is None:
        delta = (departure_dt.date() - arrival_dt.date()).days
        if delta > 0:
            nights = delta

    return arrival_dt, departure_dt, nights


def _arrival_window_hours(arrival_dt: datetime | None) -> int | None:
    if arrival_dt is None:
        return None
    now = datetime.now()
    # Ensure both are naive for comparison
    if arrival_dt.tzinfo is not None:
        now = datetime.now(tz=timezone.utc)
    delta = arrival_dt - now
    hours = delta.total_seconds() / 3600
    if hours < 0:
        return 0  # already past; treat as now
    return int(hours)


def extract(text: str) -> dict[str, Any]:
    """Extract hotel entities from email text.

    Parameters
    ----------
    text:
        Raw or pre-processed email body / subject concatenated.

    Returns
    -------
    dict with keys:
        confirmation_numbers, arrival_date, departure_date, nights,
        room_category, rate_code, guest_count, arrival_window_hours
    """
    arrival_dt, departure_dt, nights = _extract_dates(text)
    window = _arrival_window_hours(arrival_dt)

    return {
        "confirmation_numbers": _extract_confirmation_numbers(text),
        "arrival_date":         arrival_dt.date().isoformat() if arrival_dt else None,
        "departure_date":       departure_dt.date().isoformat() if departure_dt else None,
        "nights":               nights,
        "room_category":        _extract_room_category(text),
        "rate_code":            _extract_rate_code(text),
        "guest_count":          _extract_guest_count(text),
        "arrival_window_hours": window,
    }

"""Pure hotel-domain entity extraction for ReplyRight triage.

This module extracts deterministic reservation signals from subject/body text.
It performs no I/O, does not call AI services, and is intentionally not wired
into the main triage flow yet.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import dateparser
from dateparser.search import search_dates

ROOM_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Presidential Suite", ("presidential suite", "presidential", "suite presidencial", "suite presidentielle", "suite présidentielle", "suite presidenziale", "präsidentensuite")),
    ("Towers Residence", ("towers residence", "tower residence")),
    ("Royal Suite", ("royal suite", "royal", "suite royale", "suite real", "suite reale")),
    ("Astoria Suite", ("astoria suite", "astoria")),
    ("Tower Suite", ("tower suite", "suite torre", "suite tour", "turm suite")),
    ("Junior Suite", ("junior suite", "jr suite")),
    ("Premier King", ("premier king", "premier room")),
    ("Deluxe Queen", ("deluxe queen", "deluxe double queen")),
    ("Deluxe King", ("deluxe king", "deluxe room")),
)

_CONFIRMATION_RE = re.compile(
    r"\b(?:confirmation(?:\s*(?:number|no\.?|#))?|confirm(?:ation)?\s*(?:no\.?|number|#)?|"
    r"reservation(?:\s*(?:number|no\.?|#))?|res(?:ervation)?\s*(?:no\.?|number|#)?|"
    r"booking\s*(?:#|number|ref(?:erence)?)?|"
    r"confirmaci[oó]n|confirma[cç][aã]o|conferma|best[aä]tigung|"
    r"r[eé]servation|reserva|prenotazione|reservierung|buchung)"
    r"[\s:.;#-]+([A-Z0-9]{6,12})\b",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\$\s?\d+(?:\.\d{2})?")
_RATE_CODE_RE = re.compile(
    r"\b(?:rate\s+code|rate\s+plan|promo\s+code|package\s+code|"
    r"corporate\s+code|group\s+code|rate|promo)\s*[:#-]?\s+([A-Z0-9]{3,12})\b",
    re.IGNORECASE,
)
_ADULTS_RE = re.compile(r"\b(\d{1,2})\s+(?:adult(?:s)?|adultos|adultes|adulti|erwachsene)\b", re.IGNORECASE)
_CHILDREN_RE = re.compile(
    r"\b(\d{1,2})\s+(?:child(?:ren)?|kid(?:s)?|ni[nñ][oa]s?|enfants?|crian[cç]as?|bambini|kinder)\b",
    re.IGNORECASE,
)
_GUESTS_RE = re.compile(
    r"\b(\d{1,2})\s+(?:guest(?:s)?|people|pax|persons?|personnes?|ospiti|h[uó]spedes?|g[aä]ste)\b",
    re.IGNORECASE,
)
_NIGHTS_RE = re.compile(
    r"\b(\d{1,3})\s+(?:night(?:s)?|noches|nuits?|noites?|notti|n[aä]chte)\b",
    re.IGNORECASE,
)

_DATE_TOKEN_RE = re.compile(
    r"\b("
    r"day\s+after\s+tomorrow|tonight|today|tomorrow|"
    r"next\s+(?:mon|tues|wednes|thurs|fri|satur|sun)day|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day(?:\s+the)?\s+\d{1,2}(?:st|nd|rd|th)?|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day|"
    r"\d{1,2}/\d{1,2}(?:/\d{2,4})?|"
    r"\d{4}-\d{1,2}-\d{1,2}|"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?|"
    r"(?:the\s+)?\d{1,2}(?:st|nd|rd|th)?"
    r")\b",
    re.IGNORECASE,
)
_ARRIVAL_RE = re.compile(
    r"\b(?:arriv(?:e|es|ing|al)?|check[\s-]?in|stay begins|first night|"
    r"llegada|arriv[ée]e|chegada|arrivo|ankunft)\b",
    re.I,
)
_DEPARTURE_RE = re.compile(
    r"\b(?:depart(?:s|ing|ure)?|check(?:ing)?[\s-]?out|stay ends|leav(?:e|ing)|"
    r"salida|d[ée]part|sa[ií]da|partenza|abreise)\b",
    re.I,
)
_CONFIRMATION_TRIGGER_VALUES = {
    "BOOKING",
    "BUCHUNG",
    "CONFIRMATION",
    "CONFIRMACION",
    "CONFIRMACIÓN",
    "CONFIRMACAO",
    "CONFIRMAÇÃO",
    "CONFERMA",
    "RESERVA",
    "RESERVATION",
    "RESERVIERUNG",
    "RÉSERVATION",
}


def _search_dateparser_dates(text: str, base: datetime) -> list[datetime]:
    settings: dict[str, Any] = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": base,
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    try:
        matches = search_dates(text, settings=settings)
    except Exception:
        return []
    if not matches:
        return []
    dates: list[datetime] = []
    for _raw, parsed in matches:
        if parsed:
            normalized = parsed.replace(tzinfo=None)
            if normalized not in dates:
                dates.append(normalized)
    return dates


def _base_datetime(received_at: datetime | None) -> datetime:
    return received_at.replace(tzinfo=None) if received_at else datetime.now()


def _parse_date_token(token: str, base: datetime) -> datetime | None:
    cleaned = re.sub(r"\b(the)\b", "", token.strip(), flags=re.I)
    cleaned = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", r"\1", cleaned, flags=re.I)
    if not cleaned:
        return None
    lower = cleaned.lower()

    if lower in {"tonight", "today"}:
        return base.replace(hour=0, minute=0, second=0, microsecond=0)
    if lower == "tomorrow":
        return (base + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if lower == "day after tomorrow":
        return (base + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

    weekday_match = re.fullmatch(r"next\s+((?:mon|tues|wednes|thurs|fri|satur|sun)day)", lower)
    if weekday_match:
        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        target = weekdays[weekday_match.group(1)]
        days_ahead = (target - base.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (base + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)

    day_only = re.fullmatch(r"\d{1,2}", cleaned)
    weekday_day = re.fullmatch(r"(?:mon|tues|wednes|thurs|fri|satur|sun)day\s+(\d{1,2})", cleaned, re.I)
    if day_only or weekday_day:
        day = int(weekday_day.group(1) if weekday_day else cleaned)
        for offset in range(0, 18):
            year = base.year + ((base.month - 1 + offset) // 12)
            month = ((base.month - 1 + offset) % 12) + 1
            try:
                candidate = base.replace(year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                continue
            if candidate.date() >= base.date():
                return candidate
        return None

    settings: dict[str, Any] = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": base,
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    try:
        parsed = dateparser.parse(cleaned, settings=settings)
    except Exception:
        return None
    return parsed.replace(tzinfo=None) if parsed else None


def _collect_dates_near(pattern: re.Pattern[str], text: str, base: datetime) -> list[datetime]:
    dates: list[datetime] = []
    for match in pattern.finditer(text):
        window = text[match.end() : match.end() + 120]
        search_window = re.split(r"(?<=\d{4})\.\s+|[;!\n]", window, maxsplit=1)[0]
        if not re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", search_window):
            searched = _search_dateparser_dates(search_window, base)
            if searched:
                dates.append(searched[0])
                continue
        for date_match in _DATE_TOKEN_RE.finditer(window):
            parsed = _parse_date_token(date_match.group(1), base)
            if parsed:
                dates.append(parsed)
                break
    return dates


def _extract_dates(text: str, received_at: datetime | None = None) -> tuple[datetime | None, datetime | None, int | None]:
    base = _base_datetime(received_at)
    nights_match = _NIGHTS_RE.search(text)
    nights = int(nights_match.group(1)) if nights_match else None

    arrivals = _collect_dates_near(_ARRIVAL_RE, text, base)
    departures = _collect_dates_near(_DEPARTURE_RE, text, base)

    all_dates: list[datetime] = []
    if not re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", text):
        all_dates = _search_dateparser_dates(text, base)
    if not all_dates:
        for date_match in _DATE_TOKEN_RE.finditer(text):
            parsed = _parse_date_token(date_match.group(1), base)
            if parsed and parsed not in all_dates:
                all_dates.append(parsed)

    arrival = min(arrivals) if arrivals else (min(all_dates) if all_dates else None)
    departure = min(departures) if departures else None
    if arrival and not departure:
        later_dates = sorted(dt for dt in all_dates if dt.date() > arrival.date())
        if later_dates:
            departure = later_dates[0]
    if arrival and nights and not departure:
        departure = arrival + timedelta(days=nights)
    if arrival and departure and nights is None:
        delta_days = (departure.date() - arrival.date()).days
        nights = delta_days if delta_days > 0 else None
    return arrival, departure, nights


def _extract_confirmation_numbers(text: str) -> list[str]:
    seen: list[str] = []
    for line in text.splitlines() or [text]:
        for match in _CONFIRMATION_RE.finditer(line):
            value = match.group(1).upper()
            if (
                value not in _CONFIRMATION_TRIGGER_VALUES
                and value not in seen
                and (not value.isdigit() or 6 <= len(value) <= 12)
            ):
                seen.append(value)
    return seen


def _extract_room_category(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text.lower())
    for category, phrases in ROOM_CATEGORIES:
        if any(re.search(rf"\b{re.escape(phrase)}\b", normalized) for phrase in phrases):
            return category
    return None


def _extract_rate_code(text: str) -> str | None:
    match = _RATE_CODE_RE.search(text)
    return match.group(1).upper() if match else None


def _extract_guest_counts(text: str) -> tuple[int | None, int | None]:
    adults_match = _ADULTS_RE.search(text)
    children_match = _CHILDREN_RE.search(text)
    guests_match = _GUESTS_RE.search(text)
    adults = int(adults_match.group(1)) if adults_match else None
    children = int(children_match.group(1)) if children_match else None
    if adults is None and children is None and guests_match:
        adults = int(guests_match.group(1))
    return adults, children


def _arrival_window_hours(arrival: datetime | None, received_at: datetime | None) -> int | None:
    if arrival is None or received_at is None:
        return None
    delta = arrival.replace(tzinfo=None) - received_at.replace(tzinfo=None)
    return max(0, int(delta.total_seconds() // 3600))


def extract_entities(subject: str, body: str, received_at: datetime | None = None) -> dict[str, Any]:
    """Extract hotel-specific reservation signals from an email."""
    text = f"{subject or ''}\n{body or ''}"
    arrival, departure, nights = _extract_dates(text, received_at)
    adults, children = _extract_guest_counts(text)
    return {
        "confirmation_numbers": _extract_confirmation_numbers(text),
        "arrival_date": arrival.date().isoformat() if arrival else None,
        "departure_date": departure.date().isoformat() if departure else None,
        "nights": nights,
        "room_category": _extract_room_category(text),
        "rate_code": _extract_rate_code(text),
        "guest_count_adults": adults,
        "guest_count_children": children,
        "arrival_window_hours": _arrival_window_hours(arrival, received_at),
        "mentioned_amounts": [match.group(0).replace(" ", "") for match in _AMOUNT_RE.finditer(text)],
    }


def extract(text: str) -> dict[str, Any]:
    """Backward-compatible wrapper for older tests and exploratory callers."""
    entities = extract_entities("", text)
    return {
        **entities,
        "guest_count": (
            {
                key: value
                for key, value in {
                    "adults": entities["guest_count_adults"],
                    "children": entities["guest_count_children"],
                }.items()
                if value is not None
            }
            or None
        ),
    }

"""Centralized zero-API signal extraction for hotel email intelligence.

One extraction pass per email. Results are consumed by heuristic_analysis(),
urgency_engine.compute_urgency(), local_classifier, and the admin signal inspector.
Pure Python — no network, no disk, no AI calls.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# ── Language detection ─────────────────────────────────────────────────────────
# Simple trigram/keyword approach — fast, no dependencies.

_LANG_MARKERS: dict[str, tuple[str, ...]] = {
    "ru": ("пожалуйста", "здравствуйте", "спасибо", "резервирование", "прибытие", "номер",
           "дата", "гость", "отель", "бронирование"),
    "es": ("por favor", "gracias", "llegada", "habitación", "reserva", "tarifa",
           "cancelar", "confirmar", "salida", "factura"),
    "fr": ("s'il vous plaît", "merci", "arrivée", "chambre", "réservation",
           "annuler", "confirmer", "départ", "facture", "veuillez"),
    "de": ("bitte", "danke", "ankunft", "zimmer", "reservierung",
           "stornieren", "bestätigen", "abfahrt", "rechnung"),
    "it": ("per favore", "grazie", "arrivo", "camera", "prenotazione",
           "cancellare", "confermare", "partenza", "fattura"),
    "zh": ("你好", "请", "谢谢", "预订", "到达", "房间", "退房"),
    "ja": ("ありがとう", "よろしく", "予約", "到着", "チェック"),
    "ar": ("مرحبا", "شكرا", "حجز", "وصول", "غرفة"),
    "pt": ("por favor", "obrigado", "obrigada", "chegada", "quarto",
           "reserva", "cancelar", "confirmar", "saída", "fatura"),
}


def detect_language(text: str) -> tuple[str, float]:
    """Return (language_code, confidence) for the dominant language in text."""
    lower = text.lower()
    scores: dict[str, int] = {"en": 0}
    for lang, markers in _LANG_MARKERS.items():
        for m in markers:
            if m in lower:
                scores[lang] = scores.get(lang, 0) + 1
    # English gets a baseline score proportional to common ASCII words
    en_words = ("the", "and", "for", "with", "your", "please", "have", "will",
                "this", "that", "from", "would", "could", "thank")
    scores["en"] = sum(1 for w in en_words if f" {w} " in lower)
    if not scores:
        return "en", 0.5
    best = max(scores, key=lambda k: scores[k])
    total = sum(scores.values()) or 1
    confidence = min(0.99, scores[best] / total) if scores[best] > 0 else 0.5
    return best, round(confidence, 2)


# ── Structural patterns ────────────────────────────────────────────────────────

_REPLY_INDICATORS = (
    r"\n\s*On .{0,240}?wrote:\s*",
    r"\n\s*-{2,}\s*(?:Original Message|Forwarded Message)\s*-{2,}",
    r"\n\s*From:\s.+\n\s*(?:Sent|Date):\s.+\n\s*To:\s",
    r"\n\s*De:\s.+\n\s*(?:Enviado|Fecha):\s.+\n\s*Para:\s",
    r"\n\s*Von:\s.+\n\s*Gesendet:\s.+\n\s*An:\s",
)
_ATTACHMENT_HINTS = (
    "attached", "attachment", "attaching", "please find", "see attached",
    "find enclosed", "per attached", "as attached", "enclosed please",
    "attached herewith",
)
_GROUP_PATTERNS = (
    r"\b(\d{1,3})\s+rooms?\b",
    r"\broom\s+block\b",
    r"\bgroup\s+block\b",
    r"\brooming\s+list\b",
    r"\bpickup\s+report\b",
    r"\btotal\s+room\s+count\b",
    r"\bgroup\s+booking\b",
    r"\bsingle-use\s+link\b",
)
_AMOUNT_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", re.ASCII)
_ROOM_BLOCK_COUNT_RE = re.compile(r"\b(\d{1,3})\s+rooms?\b", re.IGNORECASE)

# ── Tone / semantic keyword groups ────────────────────────────────────────────

_POSITIVE_WORDS = (
    "thank", "thanks", "appreciate", "wonderful", "excellent", "perfect",
    "great", "fantastic", "love", "pleased", "happy", "delighted", "grateful",
    "impressive", "outstanding",
)
_NEGATIVE_WORDS = (
    "frustrated", "angry", "upset", "furious", "terrible", "awful", "horrible",
    "unacceptable", "disappointed", "disgusted", "outrageous", "ridiculous",
    "worst", "never again", "demand", "lawyer", "lawsuit", "sue",
)
_COMPLETION_WORDS = (
    "confirmed", "completed", "all set", "done", "finished", "submitted",
    "sent it back", "filled out", "applied", "handled", "taken care",
    "has been added", "has been booked", "have been booked",
)
_THANK_YOU_WORDS = (
    "thank you", "thanks", "appreciate", "gracias", "merci", "obrigado",
    "obrigada", "grazie", "danke",
)
_ACTIONABLE_WORDS = (
    "please", "can you", "could you", "would you", "need", "request",
    "confirm", "advise", "update", "book", "reserve", "cancel", "modify",
    "change", "send", "arrange", "assist", "add", "extend", "amend",
)
_FOLLOW_UP_WORDS = (
    "following up", "follow up", "following-up", "any update", "any news",
    "checking in", "checking back", "circling back", "touching base",
    "wanted to follow", "reaching out again", "second request",
)
_NO_RESPONSE_WORDS = (
    "no response", "haven't heard", "havent heard", "no reply", "not heard",
    "still waiting", "still haven't", "several days", "days ago",
    "week ago", "waiting for a response", "unanswered",
)
_VIP_WORDS = (
    "presidential suite", "waldorf suite", "royal suite", "penthouse",
    "ambassador", "senator", "excellency", "his highness", "her highness",
    "vip", "celebrity", "head of state", "diplomat", "virtuoso preferred",
    "hilton honors diamond", "diamond member", "long-stay", "extended stay",
)
_RISK_WORDS = (
    "lawsuit", "legal action", "attorney", "lawyer", "sue", "chargeback",
    "dispute with my bank", "medical", "emergency", "ada", "wheelchair",
    "accessibility", "discrimination", "health department", "fire department",
)
_BILLING_WORDS = (
    "charge", "charged", "bill", "billing", "invoice", "folio", "rate",
    "overcharged", "double charge", "refund", "credit", "dispute",
    "chargeback", "incorrect charge", "wrong amount", "payment",
)
_COMPLAINT_WORDS = (
    "complaint", "complain", "upset", "unacceptable", "disappointed",
    "terrible", "awful", "horrible", "escalate", "negative review",
    "tripadvisor", "google review", "speak to a manager",
)
_URGENCY_WORDS = (
    "urgent", "asap", "as soon as possible", "immediately", "right away",
    "today", "tonight", "this morning", "this afternoon", "emergency",
)
_SAME_DAY_WORDS = (
    "today", "tonight", "this evening", "this morning", "this afternoon",
    "arriving in", "arriving now", "on my way", "en route", "few hours",
)
_CONCIERGE_WORDS = (
    "restaurant", "dinner reservation", "table", "tickets", "theater",
    "broadway", "transportation", "car service", "limo", "helicopter",
    "tour", "spa", "flowers", "champagne", "amenity", "dog", "pet",
)
_NYC_PEAK_WORDS = (
    "fashion week", "nyfw", "un general assembly", "unga", "nyc marathon",
    "new year's eve", "nye", "thanksgiving", "us open", "pride week",
)
_ACCESSIBILITY_WORDS = (
    "wheelchair", "accessible", "accessibility", "mobility", "ada",
    "handicap", "roll-in shower", "grab bars", "visual impairment",
    "hearing impairment", "deaf", "blind", "service animal", "epipen",
    "oxygen", "medical device",
)
_INTERNAL_DOMAINS = (
    "waldorfastoria.com", "waldorfastorianewyork.com",
    "hilton.com", "conradhotels.com", "hiltonhotels.com",
)
_TRAVEL_AGENCY_DOMAINS = (
    "virtuoso.com", "amexgbt.com", "amextgbs.com", "fourseasons.com",
    "htconcierge.co.uk", "altour.com", "protravel.com", "brownell.com",
    "signatures.com", "internova.com", "classicvacations.com",
    "kiwicollection.com", "leadinghotels.com", "preferredhotels.com",
    "sertifi.net",
)
_TRAVEL_AGENCY_KEYWORDS = (
    "travel agency", "travel agent", "travel advisor", "travel adviser",
    "virtuoso", "fhr", "fine hotels", "amex centurion", "platinum concierge",
    "consortia", "signature travel", "ensemble travel", "internova",
    "brownell", "protravel", "altour", "classic vacations",
)


def _count_keywords(text: str, words: tuple[str, ...]) -> int:
    lower = text.lower()
    return sum(1 for w in words if w in lower)


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(w in lower for w in words)


def extract_signals(
    subject: str,
    body: str,
    sender_email: str = "",
    sender_name: str = "",
    received_at: str | None = None,
) -> dict[str, Any]:
    """Extract all zero-API signals from an email.

    Returns a flat dict of named signals that downstream classifiers and the
    urgency engine can consume without re-parsing the raw text.
    """
    full_text = f"{subject}\n{body}"
    lower = full_text.lower()
    body_lower = body.lower()
    sender_lower = sender_email.lower()
    domain = sender_lower.split("@")[-1] if "@" in sender_lower else sender_lower

    # ── Language ────────────────────────────────────────────────────────────
    language, lang_conf = detect_language(full_text)

    # ── Structure ──────────────────────────────────────────────────────────
    words = re.findall(r"\b\w+\b", full_text)
    sentences = re.split(r"[.!?]+", full_text)
    question_count = full_text.count("?")
    exclamation_count = full_text.count("!")
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

    reply_depth = 0
    for pat in _REPLY_INDICATORS:
        matches = re.findall(pat, full_text, re.IGNORECASE | re.DOTALL)
        reply_depth += len(matches)
    is_reply = reply_depth > 0

    has_attachment_hint = _has_any(full_text, _ATTACHMENT_HINTS)

    # ── Tone signals ───────────────────────────────────────────────────────
    pos_count = _count_keywords(full_text, _POSITIVE_WORDS)
    neg_count = _count_keywords(full_text, _NEGATIVE_WORDS)
    total_tone = pos_count + neg_count or 1
    sentiment_polarity = round((pos_count - neg_count) / total_tone, 3)

    is_completion_update = _has_any(full_text, _COMPLETION_WORDS)
    is_thank_you_only = (
        _has_any(full_text, _THANK_YOU_WORDS)
        and len(words) < 80
        and question_count == 0
        and not _has_any(full_text, _ACTIONABLE_WORDS)
    )
    is_actionable = (
        question_count > 0
        or _has_any(full_text, _ACTIONABLE_WORDS)
    )

    # ── Follow-up / no-response ────────────────────────────────────────────
    is_follow_up = _has_any(full_text, _FOLLOW_UP_WORDS)
    no_response_detected = _has_any(full_text, _NO_RESPONSE_WORDS)
    is_duplicate_followup = (
        is_reply
        and (is_follow_up or no_response_detected)
        and len(words) < 120
    )

    # ── Hotel domain signals ───────────────────────────────────────────────
    vip_signal_count = _count_keywords(full_text, _VIP_WORDS)
    risk_signal_count = _count_keywords(full_text, _RISK_WORDS)
    billing_signal_count = _count_keywords(full_text, _BILLING_WORDS)
    complaint_signal_count = _count_keywords(full_text, _COMPLAINT_WORDS)
    urgency_keyword_count = _count_keywords(full_text, _URGENCY_WORDS)
    accessibility_signal_count = _count_keywords(full_text, _ACCESSIBILITY_WORDS)
    same_day_signal_count = _count_keywords(full_text, _SAME_DAY_WORDS)
    concierge_signal_count = _count_keywords(full_text, _CONCIERGE_WORDS)
    peak_season_signal_count = _count_keywords(full_text, _NYC_PEAK_WORDS)

    # ── Amount extraction ──────────────────────────────────────────────────
    amounts = [float(m.replace(",", "")) for m in _AMOUNT_RE.findall(full_text)]
    has_dollar_amount = bool(amounts)
    max_mentioned_amount = max(amounts) if amounts else None

    # ── Group signals ──────────────────────────────────────────────────────
    is_group_inquiry = any(re.search(p, lower) for p in _GROUP_PATTERNS)
    room_block_match = _ROOM_BLOCK_COUNT_RE.search(lower)
    room_block_size_hint: int | None = None
    if room_block_match:
        try:
            room_block_size_hint = int(room_block_match.group(1))
        except (ValueError, IndexError):
            pass

    # ── Contact type signals ───────────────────────────────────────────────
    sender_is_internal = domain in _INTERNAL_DOMAINS or any(d in domain for d in _INTERNAL_DOMAINS)
    sender_is_travel_agency = (
        domain in _TRAVEL_AGENCY_DOMAINS
        or any(d in domain for d in _TRAVEL_AGENCY_DOMAINS)
        or _has_any(full_text, _TRAVEL_AGENCY_KEYWORDS)
    )

    # ── Timing signals ─────────────────────────────────────────────────────
    hour_received: int | None = None
    is_weekend: bool | None = None
    is_after_hours: bool | None = None
    if received_at:
        try:
            dt = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
            hour_received = dt.hour
            is_weekend = dt.weekday() >= 5
            is_after_hours = hour_received < 8 or hour_received >= 18
        except (ValueError, AttributeError):
            pass

    # ── Confidence boost: entity richness ─────────────────────────────────
    # Count how many distinct signal categories fired — used to calibrate
    # classifier confidence upward when the email is unambiguous.
    signal_richness = sum([
        vip_signal_count > 0,
        risk_signal_count > 0,
        billing_signal_count > 0,
        complaint_signal_count > 0,
        is_group_inquiry,
        has_dollar_amount,
        same_day_signal_count > 0,
        accessibility_signal_count > 0,
    ])

    return {
        # Language
        "language": language,
        "language_confidence": lang_conf,
        # Structure
        "word_count": len(words),
        "sentence_count": max(1, len([s for s in sentences if s.strip()])),
        "question_count": question_count,
        "exclamation_count": exclamation_count,
        "paragraph_count": len(paragraphs),
        "is_reply": is_reply,
        "reply_depth": reply_depth,
        "has_attachment_hint": has_attachment_hint,
        # Tone
        "sentiment_polarity": sentiment_polarity,
        "positive_word_count": pos_count,
        "negative_word_count": neg_count,
        "is_thank_you_only": is_thank_you_only,
        "is_completion_update": is_completion_update,
        "is_actionable": is_actionable,
        # Thread/follow-up
        "is_follow_up": is_follow_up,
        "no_response_detected": no_response_detected,
        "is_duplicate_followup": is_duplicate_followup,
        # Hotel domain keyword counts
        "vip_signal_count": vip_signal_count,
        "risk_signal_count": risk_signal_count,
        "billing_signal_count": billing_signal_count,
        "complaint_signal_count": complaint_signal_count,
        "urgency_keyword_count": urgency_keyword_count,
        "accessibility_signal_count": accessibility_signal_count,
        "same_day_signal_count": same_day_signal_count,
        "concierge_signal_count": concierge_signal_count,
        "peak_season_signal_count": peak_season_signal_count,
        # Money
        "has_dollar_amount": has_dollar_amount,
        "max_mentioned_amount": max_mentioned_amount,
        "amount_count": len(amounts),
        # Group
        "is_group_inquiry": is_group_inquiry,
        "room_block_size_hint": room_block_size_hint,
        # Contact type hints
        "sender_is_internal": sender_is_internal,
        "sender_is_travel_agency": sender_is_travel_agency,
        "sender_domain": domain,
        # Timing
        "hour_received": hour_received,
        "is_weekend": is_weekend,
        "is_after_hours": is_after_hours,
        # Summary
        "signal_richness": signal_richness,
    }


def describe_signals(signals: dict[str, Any]) -> list[str]:
    """Return a human-readable list of fired signals for the admin inspector."""
    fired: list[str] = []
    if signals.get("language") not in (None, "en"):
        fired.append(f"Language: {signals['language']} ({int(signals.get('language_confidence', 0)*100)}%)")
    if signals.get("vip_signal_count", 0) > 0:
        fired.append(f"VIP terms: {signals['vip_signal_count']} hit(s)")
    if signals.get("risk_signal_count", 0) > 0:
        fired.append(f"Risk terms: {signals['risk_signal_count']} hit(s)")
    if signals.get("billing_signal_count", 0) > 0:
        fired.append(f"Billing terms: {signals['billing_signal_count']} hit(s)")
    if signals.get("complaint_signal_count", 0) > 0:
        fired.append(f"Complaint terms: {signals['complaint_signal_count']} hit(s)")
    if signals.get("accessibility_signal_count", 0) > 0:
        fired.append(f"Accessibility terms: {signals['accessibility_signal_count']} hit(s)")
    if signals.get("same_day_signal_count", 0) > 0:
        fired.append("Same-day arrival indicator")
    if signals.get("is_follow_up"):
        fired.append("Follow-up detected")
    if signals.get("no_response_detected"):
        fired.append("No-response frustration detected")
    if signals.get("is_duplicate_followup"):
        fired.append("Likely duplicate follow-up (short reply in thread)")
    if signals.get("is_completion_update"):
        fired.append("Completion update (urgency capped)")
    if signals.get("is_thank_you_only"):
        fired.append("Thank-you only (no action needed)")
    if signals.get("has_dollar_amount"):
        amt = signals.get("max_mentioned_amount")
        fired.append(f"Dollar amount(s) mentioned" + (f" (max ${amt:,.0f})" if amt else ""))
    if signals.get("is_group_inquiry"):
        n = signals.get("room_block_size_hint")
        fired.append(f"Group inquiry" + (f" ({n} rooms)" if n else ""))
    if signals.get("sender_is_internal"):
        fired.append("Internal sender (Waldorf/Hilton domain)")
    if signals.get("sender_is_travel_agency"):
        fired.append("Travel agency sender")
    if signals.get("is_reply"):
        fired.append(f"Reply thread (depth {signals.get('reply_depth', 1)})")
    if signals.get("is_after_hours"):
        h = signals.get("hour_received")
        fired.append(f"Received after hours (hour {h})")
    if signals.get("is_weekend"):
        fired.append("Received on weekend")
    if signals.get("peak_season_signal_count", 0) > 0:
        fired.append("NYC peak season event mentioned")
    if signals.get("concierge_signal_count", 0) > 0:
        fired.append(f"Concierge terms: {signals['concierge_signal_count']} hit(s)")
    if not fired:
        fired.append("No strong signals detected — default heuristics applied")
    return fired

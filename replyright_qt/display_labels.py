from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

_ACRONYMS = {
    "ada": "ADA",
    "ai": "AI",
    "api": "API",
    "cca": "CCA",
    "com": "COM",
    "crm": "CRM",
    "id": "ID",
    "kyc": "KYC",
    "ml": "ML",
    "nycwa": "NYCWA",
    "openai": "OpenAI",
    "ota": "OTA",
    "pii": "PII",
    "smtp": "SMTP",
    "url": "URL",
    "vip": "VIP",
}

_LABEL_OVERRIDES = {
    "recommended_action": "Recommended Action",
    "verify_payment_authorization": "Verify Payment Authorization",
    "wait_for_internal_team": "Waiting on Internal Team",
    "wait_for_guest": "Waiting on Guest",
    "no_action_likely": "No Action Likely",
    "needs_review": "Needs Human Review",
    "low_confidence": "Low Confidence",
    "missing_information": "Missing Information",
    "billing_risk": "Billing Risk",
    "vip_travel": "VIP / Travel Advisor",
    "vip_pre_arrival": "VIP Pre-Arrival",
    "reply_guest": "Reply to Guest",
    "loop_reservations": "Loop Reservations",
    "loop_front_office": "Loop Front Office",
    "loop_concierge": "Loop Concierge",
    "loop_housekeeping": "Loop Housekeeping",
    "loop_engineering": "Loop Engineering",
    "escalate_manager": "Escalate for Review",
    "review_folio": "Review Folio",
    "check_reservation": "Check Reservation",
    "request_missing_information": "Request Missing Information",
    "heuristic": "Rules-Based",
    "heuristic rules": "Rules-Based",
    "heuristic_rules": "Rules-Based",
    "rules": "Rules-Based",
    "rules_based": "Rules-Based",
    "local-classifier": "Local Classifier",
    "local_classifier": "Local Classifier",
    "classifier": "Local Classifier",
    "local ml classifier": "Local Classifier",
    "local_ml_classifier": "Local Classifier",
    "external_ai": "AI Assisted",
    "external ai": "AI Assisted",
    "openai": "AI Assisted",
    "openai-refresh": "AI Assisted",
    "openai_refresh": "AI Assisted",
    "google": "AI Assisted",
    "google_ai": "AI Assisted",
    "anthropic": "AI Drafting",
    "claude": "AI Drafting",
    "pywin32-com": "Outlook Desktop",
    "pywin32_com": "Outlook Desktop",
    "outlook_com": "Outlook Desktop",
    "supabase": "Shared Learning",
    "scikit-learn": "Local Classifier",
    "scikit_learn": "Local Classifier",
    "sklearn": "Local Classifier",
    "batch_size": "Batch Size",
    "email_id": "Conversation ID",
    "body_text": "Message Body",
    "graph_message_id": "Outlook Message ID",
    "sender_email": "Sender",
    "created_at": "Created",
    "fetched_count": "Messages Read",
    "total_emails": "Total Conversations",
    "total_feedback": "Feedback Submitted",
    "total_users": "Users",
    "low_confidence_count": "Low Confidence",
    "needs_review_count": "Needs Human Review",
    "classifier_status": "Local Classifier Status",
    "ai_provider_configuration": "AI Configuration",
}


def display_label(value: object, fallback: str = "Not Set") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback

    normalized = _normalize_key(text)
    if normalized in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[normalized]

    words = []
    for word in re.sub(r"[_\-]+", " ", text).split():
        clean = re.sub(r"[^A-Za-z0-9/]+", "", word)
        lower = clean.lower()
        if lower in _ACRONYMS:
            words.append(_ACRONYMS[lower])
        elif "/" in word:
            words.append(" / ".join(display_label(part) for part in word.split("/") if part))
        else:
            words.append(lower.capitalize())
    return " ".join(words) or fallback


def display_action(value: object) -> str:
    return display_label(value, "Not Set")


def display_engine(value: object) -> str:
    return display_label(value, "Unknown")


def display_role(value: object) -> str:
    return display_label(value or "reservations", "Reservations")


def display_value(value: object) -> str:
    if value is None or value == "":
        return "Not Set"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Mapping):
        parts = [
            f"{display_label(key)}: {display_value(val)}"
            for key, val in list(value.items())[:3]
        ]
        return ", ".join(parts) if parts else "Not Set"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return ", ".join(display_value(item) for item in value) or "Not Set"
    return display_label(value) if _looks_like_key(value) else str(value)


def _normalize_key(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("-", "_")
    text = re.sub(r"\s+", "_", text)
    return text


def _looks_like_key(value: object) -> bool:
    text = str(value or "")
    return "_" in text or "-" in text or text.lower() in _LABEL_OVERRIDES

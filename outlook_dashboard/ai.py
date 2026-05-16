from __future__ import annotations

import json
import re
from typing import Any

from .config import Settings
from .redaction import redact_sensitive_text
from .taxonomy import CATEGORIES, DEPARTMENT_OWNERS, PRIORITY_LEVELS, RISK_FLAGS


INTERNAL_DOMAINS = ("waldorfastoria.com", "hilton.com")


def analyze_email(email: dict[str, Any], settings: Settings) -> dict[str, Any]:
    heuristic = heuristic_analysis(email, settings)
    if not settings.openai_configured:
        return heuristic

    try:
        return _analyze_with_openai(email, settings)
    except Exception as exc:  # OpenAI should never block local triage usability.
        heuristic["analysis_error"] = str(exc)[:500]
        return heuristic


def heuristic_analysis(email: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    subject = email.get("subject") or "(No subject)"
    body = email.get("body_text") or email.get("body_content") or email.get("body_preview") or ""
    sender_name = email.get("sender_name") or email.get("from_name") or ""
    sender_email = (email.get("sender_email") or email.get("from_email") or "").lower()
    text = f"{subject}\n{body}".lower()

    category = _category_for(text, sender_email)
    risks = _risk_flags_for(text, category)
    priority = _priority_for(text, category, risks, email.get("importance"))
    sentiment = _sentiment_for(text, category)
    owner = _owner_for(category, risks)
    missing = _missing_information_for(text, category)
    next_steps = _next_steps_for(category, risks, missing)
    summary = _summary_for(subject, category, priority, missing)
    draft = _draft_reply(sender_name, sender_email, category, missing)

    return {
        "ai_summary": summary,
        "category": category,
        "priority_level": priority,
        "guest_sentiment": sentiment,
        "internal_next_steps": next_steps,
        "missing_information": missing,
        "risk_flags": risks,
        "recommended_department_owner": owner,
        "suggested_reply_draft": draft,
        "model": settings.openai_model if settings else "heuristic",
        "analysis_engine": "heuristic",
        "analysis_error": "",
        "redaction_counts": {},
    }


def _analyze_with_openai(email: dict[str, Any], settings: Settings) -> dict[str, Any]:
    from openai import OpenAI

    body = email.get("body_text") or email.get("body_content") or email.get("body_preview") or ""
    redacted_body, redaction_counts = redact_sensitive_text(body)
    payload = {
        "subject": email.get("subject"),
        "sender_name": email.get("sender_name"),
        "sender_email": email.get("sender_email"),
        "received_datetime": email.get("received_datetime"),
        "body_preview": email.get("body_preview"),
        "body": redacted_body,
        "importance": email.get("importance"),
        "has_attachments": bool(email.get("has_attachments")),
        "allowed_categories": CATEGORIES,
        "allowed_priority_levels": PRIORITY_LEVELS,
        "allowed_risk_flags": RISK_FLAGS,
        "allowed_department_owners": DEPARTMENT_OWNERS,
    }
    client = OpenAI(api_key=settings.openai_api_key)
    raw = _responses_json(client, settings.openai_model, payload)
    data = json.loads(raw)
    normalized = _normalize_analysis(data)
    normalized.update(
        {
            "model": settings.openai_model,
            "analysis_engine": "openai",
            "analysis_error": "",
            "redaction_counts": redaction_counts,
        }
    )
    return normalized


def _responses_json(client: Any, model: str, payload: dict[str, Any]) -> str:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ai_summary": {"type": "string"},
            "category": {"type": "string", "enum": CATEGORIES},
            "priority_level": {"type": "string", "enum": PRIORITY_LEVELS},
            "guest_sentiment": {"type": "string"},
            "internal_next_steps": {"type": "array", "items": {"type": "string"}},
            "missing_information": {"type": "array", "items": {"type": "string"}},
            "risk_flags": {"type": "array", "items": {"type": "string", "enum": RISK_FLAGS}},
            "recommended_department_owner": {"type": "string", "enum": DEPARTMENT_OWNERS},
            "suggested_reply_draft": {"type": "string"},
        },
        "required": [
            "ai_summary",
            "category",
            "priority_level",
            "guest_sentiment",
            "internal_next_steps",
            "missing_information",
            "risk_flags",
            "recommended_department_owner",
            "suggested_reply_draft",
        ],
    }
    system = (
        "You classify and draft replies for a luxury hotel shared Outlook inbox. "
        "The app is read-only: do not instruct the user to send, delete, archive, move, "
        "or modify Outlook messages. Drafts are for human review only. "
        "Use polished, calm, warm, precise, professional luxury-hospitality language. "
        "Do not guarantee upgrades, views, early check-in, late checkout, connecting rooms, "
        "amenities, or special requests unless explicitly confirmed in the email. "
        "Use 'subject to availability' where appropriate. Do not admit fault unless confirmed. "
        "Never invent policies, rates, fees, or availability. If information is missing, "
        "ask for it politely. Address external guests as Mr./Ms. Last Name when available; "
        "address Hilton colleagues by first name."
    )
    user = json.dumps(payload, ensure_ascii=True)

    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "hotel_email_intelligence",
                    "schema": schema,
                    "strict": True,
                }
            },
            temperature=0.2,
        )
        return response.output_text
    except Exception:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Return JSON matching this schema: {json.dumps(schema)}\n\nEmail:\n{user}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return response.choices[0].message.content or "{}"


def _normalize_analysis(data: dict[str, Any]) -> dict[str, Any]:
    category = data.get("category") if data.get("category") in CATEGORIES else "General inquiry"
    priority = data.get("priority_level") if data.get("priority_level") in PRIORITY_LEVELS else "Normal"
    owner = (
        data.get("recommended_department_owner")
        if data.get("recommended_department_owner") in DEPARTMENT_OWNERS
        else "Reservations"
    )
    risks = [flag for flag in _as_list(data.get("risk_flags")) if flag in RISK_FLAGS]
    return {
        "ai_summary": str(data.get("ai_summary") or ""),
        "category": category,
        "priority_level": priority,
        "guest_sentiment": str(data.get("guest_sentiment") or "Neutral"),
        "internal_next_steps": _as_list(data.get("internal_next_steps")),
        "missing_information": _as_list(data.get("missing_information")),
        "risk_flags": risks,
        "recommended_department_owner": owner,
        "suggested_reply_draft": str(data.get("suggested_reply_draft") or ""),
    }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(value)]


def _category_for(text: str, sender_email: str) -> str:
    if any(domain in sender_email for domain in INTERNAL_DOMAINS):
        if "rooming list" in text or "group" in text or "block" in text:
            return "Rooming list / group"
        return "Internal request"
    if "same-day" in text or ("arrival" in text and any(term in text for term in ["today", "tonight"])):
        return "Urgent same-day arrival"
    if "vip" in text or "owner" in text or "celebrity" in text:
        return "VIP pre-arrival"
    if any(term in text for term in ["billing", "charged", "charge", "refund", "folio", "invoice"]):
        return "Billing dispute"
    if any(term in text for term in ["ada", "accessible", "accessibility", "roll-in", "wheelchair", "shower chair"]):
        return "Accessibility request"
    if any(term in text for term in ["virtuoso", "fhr", "fine hotels", "consortia", "amex"]):
        return "Consortia / FHR / Virtuoso"
    if any(term in text for term in ["complaint", "disappointed", "unacceptable", "manager", "poor experience"]):
        return "Complaint"
    if any(term in text for term in ["amenity", "champagne", "flowers", "cake", "birthday", "anniversary"]):
        return "Amenity request"
    if "rooming list" in text or "group" in text or "block" in text:
        return "Rooming list / group"
    if any(term in text for term in ["cancel", "cancellation", "modify", "modification", "change my reservation"]):
        return "Cancellation / modification"
    if any(term in text for term in ["following up", "follow-up", "checking again", "second request"]):
        return "Duplicate follow-up"
    if any(term in text for term in ["rate", "quote", "pricing", "best available"]):
        return "Rate inquiry"
    return "General inquiry"


def _risk_flags_for(text: str, category: str) -> list[str]:
    risks: list[str] = []
    if category == "Billing dispute" or any(term in text for term in ["billing", "chargeback", "charged", "refund"]):
        risks.append("Billing")
    if "chargeback" in text:
        risks.append("Chargeback")
    if any(term in text for term in ["legal", "lawyer", "attorney", "lawsuit"]):
        risks.append("Legal")
    if any(term in text for term in ["medical", "doctor", "hospital", "allergy", "injury"]):
        risks.append("Medical")
    if category == "Accessibility request":
        risks.append("ADA / accessibility")
    if any(term in text for term in ["discrimination", "discriminated"]):
        risks.append("Discrimination")
    if category == "VIP pre-arrival" or "vip" in text:
        risks.append("VIP")
    if category == "Complaint" or any(
        term in text for term in ["social media", "negative review", "online review", "tripadvisor"]
    ):
        risks.append("Reputation risk")
    if any(flag in risks for flag in ["Legal", "Medical", "ADA / accessibility", "Discrimination", "Chargeback"]):
        risks.append("Manager review required")
    return list(dict.fromkeys(risks))


def _priority_for(text: str, category: str, risks: list[str], importance: str | None) -> str:
    if category == "Urgent same-day arrival" or any(
        term in text for term in ["immediately", "urgent", "as soon as possible", "tonight"]
    ):
        return "Immediate"
    if any(flag in risks for flag in ["Legal", "Medical", "Discrimination", "Chargeback"]):
        return "Immediate"
    if category in {"VIP pre-arrival", "Billing dispute", "Complaint", "Accessibility request"}:
        return "High"
    if importance == "high":
        return "High"
    if category in {"Duplicate follow-up", "Internal request"}:
        return "Low"
    return "Normal"


def _sentiment_for(text: str, category: str) -> str:
    if category == "Complaint" or any(term in text for term in ["disappointed", "unacceptable", "angry"]):
        return "Upset"
    if category in {"Billing dispute", "Accessibility request"}:
        return "Concerned"
    if any(term in text for term in ["thank you", "appreciate", "warmly"]):
        return "Positive"
    return "Neutral"


def _owner_for(category: str, risks: list[str]) -> str:
    if "Manager review required" in risks:
        return "Management"
    return {
        "Billing dispute": "Finance",
        "Consortia / FHR / Virtuoso": "Reservations",
        "Complaint": "Guest Relations",
        "Amenity request": "Concierge",
        "Accessibility request": "Accessibility Coordinator",
        "Rooming list / group": "Sales",
        "Rate inquiry": "Revenue Management",
        "Urgent same-day arrival": "Front Office",
        "VIP pre-arrival": "Guest Relations",
    }.get(category, "Reservations")


def _missing_information_for(text: str, category: str) -> list[str]:
    missing: list[str] = []
    if category in {"VIP pre-arrival", "Amenity request", "Cancellation / modification"}:
        if not re.search(r"\b(confirm(?:ation)?|reservation)\s*(number|#)?\s*[:#]?\s*[a-z0-9-]+", text):
            missing.append("Reservation or confirmation number")
    if category == "Rate inquiry":
        if not re.search(r"\b\d{1,2}/\d{1,2}\b|january|february|march|april|may|june|july|august|september|october|november|december", text):
            missing.append("Stay dates")
        if not any(term in text for term in ["king", "queen", "suite", "double"]):
            missing.append("Room type")
    if category == "Billing dispute" and not any(term in text for term in ["folio", "invoice", "receipt", "attachment"]):
        missing.append("Folio, invoice, or receipt details")
    if category == "Accessibility request" and "arrival" not in text and "beginning" not in text:
        missing.append("Arrival date")
    return missing


def _next_steps_for(category: str, risks: list[str], missing: list[str]) -> list[str]:
    steps = []
    if missing:
        steps.append("Request the missing details before confirming any arrangement.")
    steps.extend(
        {
            "VIP pre-arrival": [
                "Verify reservation notes, VIP profile, arrival time, and confirmed amenities.",
                "Coordinate any confirmed recognition with Guest Relations and Front Office.",
            ],
            "Rate inquiry": [
                "Check available rates and package inclusions before quoting.",
                "Confirm dates, room type, cancellation terms, taxes, and fees before replying.",
            ],
            "Billing dispute": [
                "Review folio and payment records with Finance.",
                "Escalate any duplicate charge or chargeback risk before responding definitively.",
            ],
            "Consortia / FHR / Virtuoso": [
                "Confirm eligible program benefits and booking channel requirements.",
                "Avoid promising upgrade or amenity fulfillment beyond confirmed program terms.",
            ],
            "Complaint": [
                "Escalate to Guest Relations or a manager for service recovery review.",
                "Acknowledge concern without admitting fault until details are verified.",
            ],
            "Amenity request": [
                "Check availability and operational feasibility with Concierge or In-Room Dining.",
                "Phrase special requests as noted or subject to availability unless confirmed.",
            ],
            "Accessibility request": [
                "Escalate to the accessibility owner and verify room features before confirming.",
                "Document accessibility needs clearly in the reservation profile.",
            ],
            "Rooming list / group": [
                "Compare the submitted list against the group block.",
                "Confirm missing names, room types, and billing instructions with Sales.",
            ],
            "Urgent same-day arrival": [
                "Prioritize reservation verification and alert Front Office if action is needed today.",
                "Confirm only arrangements already visible as approved or available.",
            ],
        }.get(category, ["Review the reservation context and respond with confirmed information only."])
    )
    if "Manager review required" in risks:
        steps.append("Route to a manager before final response.")
    return steps


def _summary_for(subject: str, category: str, priority: str, missing: list[str]) -> str:
    suffix = ""
    if missing:
        suffix = f" Missing: {', '.join(missing)}."
    return f"{priority} {category.lower()} email about: {subject}.{suffix}"


def _draft_reply(sender_name: str, sender_email: str, category: str, missing: list[str]) -> str:
    salutation = _salutation(sender_name, sender_email)
    if missing:
        missing_sentence = "To assist further, may we kindly ask you to provide " + ", ".join(missing) + "?"
    else:
        missing_sentence = "We will review the reservation details and follow up with confirmed information shortly."

    body_by_category = {
        "VIP pre-arrival": (
            "Thank you for reaching out. We would be delighted to note your preferences for the stay. "
            "Any view, upgrade, early arrival, amenity, or special request remains subject to availability "
            "unless it has already been confirmed by the hotel."
        ),
        "Rate inquiry": (
            "Thank you for your inquiry. We would be pleased to review available options for your requested stay "
            "and share confirmed rate details, inclusions, taxes, fees, and cancellation terms."
        ),
        "Billing dispute": (
            "Thank you for bringing this to our attention. We will review the folio and payment details with the "
            "appropriate team before providing a confirmed update."
        ),
        "Consortia / FHR / Virtuoso": (
            "Thank you for your message. We will verify the eligible program benefits and booking details before "
            "confirming any inclusions or availability-based amenities."
        ),
        "Complaint": (
            "Thank you for sharing your concerns. We are sorry to learn that your experience may not have reflected "
            "the level of care we strive to provide, and we will review the details with the appropriate leadership team."
        ),
        "Amenity request": (
            "Thank you for your thoughtful request. We will note the preference and review what may be arranged, "
            "subject to availability and operational confirmation."
        ),
        "Accessibility request": (
            "Thank you for advising us of these requirements. We will review the accessible room features and "
            "related notes carefully before confirming the details."
        ),
        "Rooming list / group": (
            "Thank you for the updated information. We will compare the details against the current group block "
            "and advise if any names, room types, or billing details require clarification."
        ),
        "Internal request": (
            "Thank you. I will review the details and follow up with any questions or confirmed updates."
        ),
        "Cancellation / modification": (
            "Thank you for your message. We will review the reservation details and applicable terms before "
            "confirming any cancellation or modification."
        ),
        "Urgent same-day arrival": (
            "Thank you for reaching out. We are reviewing this promptly with the appropriate team and will follow "
            "up with confirmed information as soon as possible."
        ),
        "Duplicate follow-up": (
            "Thank you for following up. We are reviewing the prior correspondence and will respond with confirmed "
            "information as soon as possible."
        ),
        "General inquiry": (
            "Thank you for your message. We will review the details and follow up with confirmed information shortly."
        ),
    }
    body = body_by_category.get(category, body_by_category["General inquiry"])
    return f"{salutation}\n\n{body}\n\n{missing_sentence}\n\nWarm regards,\nWaldorf Astoria Reservations"


def _salutation(sender_name: str, sender_email: str) -> str:
    clean_name = " ".join((sender_name or "").split())
    if any(sender_email.endswith(domain) for domain in INTERNAL_DOMAINS):
        first_name = clean_name.split()[0] if clean_name else "there"
        return f"Hi {first_name},"
    parts = clean_name.split()
    if len(parts) >= 2:
        return f"Dear Mr./Ms. {parts[-1]},"
    if len(parts) == 1:
        return f"Dear Mr./Ms. {parts[0]},"
    return "Dear Guest,"

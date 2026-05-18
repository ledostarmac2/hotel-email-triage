"""Rich metadata for taxonomy values.

Extends taxonomy.py with SLA times, escalation paths, color codes,
display descriptions, and routing rules per category/urgency/owner.
Used by the admin UI, signal inspector, and SLA alerting.
"""
from __future__ import annotations

from typing import Any

# ── Category metadata ──────────────────────────────────────────────────────────

CATEGORY_META: dict[str, dict[str, Any]] = {
    "VIP pre-arrival": {
        "response_sla_hours": 1,
        "escalation_urgency": 4,
        "default_owner": "Reservations",
        "color": "#2563EB",
        "icon": "star",
        "description": "Pre-arrival coordination for VIP, ultra-luxury, or long-stay guests.",
        "key_risk_flags": ["VIP"],
        "required_fields": ["arrival_date", "room_category"],
        "escalate_to": "Front Desk",
        "reply_tone": "warm_formal",
    },
    "Rate inquiry": {
        "response_sla_hours": 4,
        "escalation_urgency": 3,
        "default_owner": "Reservations",
        "color": "#0891B2",
        "icon": "tag",
        "description": "Rate, availability, or package inquiry from guest or travel advisor.",
        "key_risk_flags": [],
        "required_fields": ["arrival_date"],
        "escalate_to": "Sales",
        "reply_tone": "professional",
    },
    "Billing dispute": {
        "response_sla_hours": 2,
        "escalation_urgency": 4,
        "default_owner": "Front Desk",
        "color": "#DC2626",
        "icon": "alert",
        "description": "Disputed charge, incorrect folio, refund request, or chargeback.",
        "key_risk_flags": ["Billing", "Chargeback"],
        "required_fields": [],
        "escalate_to": "All Departments",
        "reply_tone": "empathetic_formal",
    },
    "Consortia / FHR / Virtuoso": {
        "response_sla_hours": 2,
        "escalation_urgency": 3,
        "default_owner": "Reservations",
        "color": "#7C3AED",
        "icon": "diamond",
        "description": "Booking from a preferred travel program (FHR, Virtuoso, STARS, Amex Centurion).",
        "key_risk_flags": ["VIP"],
        "required_fields": ["arrival_date", "rate_code"],
        "escalate_to": "Sales",
        "reply_tone": "warm_formal",
    },
    "Complaint": {
        "response_sla_hours": 1,
        "escalation_urgency": 4,
        "default_owner": "Front Desk",
        "color": "#B91C1C",
        "icon": "warning",
        "description": "Guest dissatisfaction, negative experience, or service failure.",
        "key_risk_flags": ["Reputation risk", "Leadership review required"],
        "required_fields": [],
        "escalate_to": "All Departments",
        "reply_tone": "empathetic_apologetic",
    },
    "Amenity request": {
        "response_sla_hours": 4,
        "escalation_urgency": 3,
        "default_owner": "Housekeeping",
        "color": "#065F46",
        "icon": "gift",
        "description": "Request for in-room amenity, special setup, or pre-arrival preparation.",
        "key_risk_flags": [],
        "required_fields": ["arrival_date"],
        "escalate_to": "Concierge",
        "reply_tone": "warm_service",
    },
    "Accessibility request": {
        "response_sla_hours": 1,
        "escalation_urgency": 5,
        "default_owner": "Front Desk",
        "color": "#0284C7",
        "icon": "accessibility",
        "description": "ADA accommodation, mobility access, or medical device requirement.",
        "key_risk_flags": ["ADA/accessibility"],
        "required_fields": ["arrival_date"],
        "escalate_to": "Engineering",
        "reply_tone": "empathetic_formal",
    },
    "Rooming list / group": {
        "response_sla_hours": 4,
        "escalation_urgency": 3,
        "default_owner": "Sales",
        "color": "#92400E",
        "icon": "users",
        "description": "Group block, rooming list, or corporate event coordination.",
        "key_risk_flags": [],
        "required_fields": ["arrival_date", "room_count"],
        "escalate_to": "Sales",
        "reply_tone": "professional",
    },
    "Internal request": {
        "response_sla_hours": 8,
        "escalation_urgency": 2,
        "default_owner": "Reservations",
        "color": "#374151",
        "icon": "building",
        "description": "Operational update, notification, or request from another Waldorf/Hilton team.",
        "key_risk_flags": [],
        "required_fields": [],
        "escalate_to": None,
        "reply_tone": "informal_colleague",
    },
    "Cancellation / modification": {
        "response_sla_hours": 3,
        "escalation_urgency": 3,
        "default_owner": "Reservations",
        "color": "#9333EA",
        "icon": "edit",
        "description": "Request to cancel, modify dates, room type, or guest count.",
        "key_risk_flags": [],
        "required_fields": ["arrival_date"],
        "escalate_to": "Front Desk",
        "reply_tone": "professional",
    },
    "Urgent same-day arrival": {
        "response_sla_hours": 0.5,
        "escalation_urgency": 5,
        "default_owner": "Front Desk",
        "color": "#DC2626",
        "icon": "clock",
        "description": "Guest arriving today or within hours; same-day coordination required.",
        "key_risk_flags": ["VIP"],
        "required_fields": [],
        "escalate_to": "All Departments",
        "reply_tone": "urgent_warm",
    },
    "Duplicate follow-up": {
        "response_sla_hours": 2,
        "escalation_urgency": 3,
        "default_owner": "Reservations",
        "color": "#6B7280",
        "icon": "repeat",
        "description": "Follow-up on an unanswered request — escalate if >24h elapsed.",
        "key_risk_flags": [],
        "required_fields": [],
        "escalate_to": "Front Desk",
        "reply_tone": "professional",
    },
    "General inquiry": {
        "response_sla_hours": 8,
        "escalation_urgency": 2,
        "default_owner": "Reservations",
        "color": "#6B7280",
        "icon": "question",
        "description": "General question or informational request with no specific urgency.",
        "key_risk_flags": [],
        "required_fields": [],
        "escalate_to": None,
        "reply_tone": "professional",
    },
}

# ── Urgency metadata ───────────────────────────────────────────────────────────

URGENCY_META: dict[int, dict[str, Any]] = {
    5: {
        "label": "Immediate",
        "color": "#DC2626",
        "badge_color": "#FEF2F2",
        "text_color": "#991B1B",
        "sla_minutes": 30,
        "description": "Same-day arrival, medical emergency, active complaint, legal threat, or in-house guest crisis.",
        "icon": "fire",
        "notify_management": True,
    },
    4: {
        "label": "High",
        "color": "#EA580C",
        "badge_color": "#FFF7ED",
        "text_color": "#9A3412",
        "sla_minutes": 120,
        "description": "Arrival within 48h, VIP pre-arrival, billing dispute, or unanswered follow-up.",
        "icon": "chevron-up",
        "notify_management": False,
    },
    3: {
        "label": "Normal",
        "color": "#CA8A04",
        "badge_color": "#FEFCE8",
        "text_color": "#854D0E",
        "sla_minutes": 240,
        "description": "Pre-arrival coordination 3–14 days out, travel advisor booking request.",
        "icon": "minus",
        "notify_management": False,
    },
    2: {
        "label": "Low",
        "color": "#16A34A",
        "badge_color": "#F0FDF4",
        "text_color": "#166534",
        "sla_minutes": 480,
        "description": "Rate inquiry with flexible dates, general question, future modification.",
        "icon": "chevron-down",
        "notify_management": False,
    },
    1: {
        "label": "Low",
        "color": "#6B7280",
        "badge_color": "#F9FAFB",
        "text_color": "#374151",
        "sla_minutes": 1440,
        "description": "Informational, completed update, thank-you acknowledgment.",
        "icon": "archive",
        "notify_management": False,
    },
}

# ── Owner metadata ─────────────────────────────────────────────────────────────

OWNER_META: dict[str, dict[str, Any]] = {
    "Front Desk": {
        "color": "#2563EB",
        "handles": [
            "Same-day and next-day arrivals",
            "In-house guest issues",
            "Early check-in / late checkout",
            "Key and room assignment problems",
            "Luggage and bell service",
        ],
        "escalation_contact": "FOM (Front Office Manager)",
    },
    "Reservations": {
        "color": "#0891B2",
        "handles": [
            "Pre-arrival inquiries (>48h out)",
            "Rate and availability requests",
            "Booking modifications and cancellations",
            "Travel advisor bookings (Virtuoso, FHR, etc.)",
            "CCA / payment authorization forms",
            "Special packages and honeymoon setups",
        ],
        "escalation_contact": "Director of Revenue / Rooms Experience Manager",
    },
    "Concierge": {
        "color": "#065F46",
        "handles": [
            "Restaurant and show reservations",
            "NYC tours and sightseeing",
            "Transportation (car service, limo, helicopter)",
            "Amenity sourcing (flowers, champagne, gifts)",
            "Pet and grocery services",
            "Business center requests",
        ],
        "escalation_contact": "Chief Concierge",
    },
    "Sales": {
        "color": "#92400E",
        "handles": [
            "Group blocks (10+ rooms)",
            "Corporate account RFPs",
            "Wedding and social event inquiries",
            "Long-term stays (7+ nights)",
            "Buyout and exclusive-use inquiries",
            "Consortia / FHR / Virtuoso account management",
        ],
        "escalation_contact": "Director of Sales",
    },
    "Housekeeping": {
        "color": "#4B5563",
        "handles": [
            "Room preparation (flowers, champagne, turndown)",
            "Rollaway / crib setup",
            "Linen and pillow preferences",
            "Room condition complaints",
            "Pet accommodation preparation",
        ],
        "escalation_contact": "Executive Housekeeper",
    },
    "Engineering": {
        "color": "#57534E",
        "handles": [
            "HVAC and temperature issues",
            "Plumbing and water complaints",
            "TV / tech / internet malfunctions",
            "Room defects and maintenance requests",
            "ADA room modifications",
            "Elevator and accessibility issues",
        ],
        "escalation_contact": "Chief Engineer",
    },
    "All Departments": {
        "color": "#1D4ED8",
        "handles": [
            "Property-wide disruptions",
            "Major VIP coordination requiring all teams",
            "Multi-department requests that cannot be assigned to one team",
            "Crisis response",
        ],
        "escalation_contact": "General Manager",
    },
}

# ── Contact type metadata ──────────────────────────────────────────────────────

CONTACT_TYPE_META: dict[str, dict[str, Any]] = {
    "Internal": {
        "color": "#374151",
        "description": "Waldorf Astoria or Hilton colleague — use first name.",
        "sla_multiplier": 1.5,  # Internal emails get relaxed SLA
    },
    "Group contact": {
        "color": "#92400E",
        "description": "Corporate planner, wedding coordinator, or group organizer (10+ rooms).",
        "sla_multiplier": 1.0,
    },
    "Travel agency": {
        "color": "#7C3AED",
        "description": "Virtuoso, FHR, Amex Centurion, or other luxury travel program advisor.",
        "sla_multiplier": 0.8,  # Travel agencies get tighter SLA (key relationships)
    },
    "Direct guest": {
        "color": "#2563EB",
        "description": "Individual guest booking direct — use Mr./Ms. [Last Name].",
        "sla_multiplier": 0.9,
    },
}

# ── Risk flag metadata ─────────────────────────────────────────────────────────

RISK_META: dict[str, dict[str, Any]] = {
    "Billing": {"color": "#DC2626", "notify_management": False, "sla_override_hours": 2},
    "Legal": {"color": "#7F1D1D", "notify_management": True, "sla_override_hours": 1},
    "Medical": {"color": "#DC2626", "notify_management": True, "sla_override_hours": 0.5},
    "ADA/accessibility": {"color": "#0284C7", "notify_management": True, "sla_override_hours": 1},
    "Discrimination": {"color": "#7F1D1D", "notify_management": True, "sla_override_hours": 1},
    "VIP": {"color": "#2563EB", "notify_management": False, "sla_override_hours": None},
    "Chargeback": {"color": "#DC2626", "notify_management": True, "sla_override_hours": 2},
    "Reputation risk": {"color": "#B91C1C", "notify_management": True, "sla_override_hours": 1},
    "Leadership review required": {"color": "#7C3AED", "notify_management": True, "sla_override_hours": 1},
}


# ── Helper functions ───────────────────────────────────────────────────────────

def get_effective_sla_hours(
    category: str,
    urgency: int,
    contact_type: str,
    risk_flags: list[str] | None = None,
) -> float:
    """Compute the effective SLA in hours considering all factors.

    Risk flags can override the category SLA to a shorter deadline.
    Contact type multipliers adjust the nominal SLA.
    Urgency level 5 always caps at 0.5h; level 4 at 2h.
    """
    # Hard urgency caps
    if urgency >= 5:
        return 0.5
    if urgency >= 4:
        return 2.0

    # Base SLA from category
    base = CATEGORY_META.get(category, {}).get("response_sla_hours", 8.0)

    # Apply contact type multiplier
    multiplier = CONTACT_TYPE_META.get(contact_type, {}).get("sla_multiplier", 1.0)
    effective = base * multiplier

    # Apply the tightest risk flag override if present
    if risk_flags:
        for flag in risk_flags:
            override = RISK_META.get(flag, {}).get("sla_override_hours")
            if override is not None:
                effective = min(effective, override)

    return round(effective, 2)


def urgency_label(urgency: int) -> str:
    return URGENCY_META.get(urgency, URGENCY_META[2])["label"]


def urgency_color(urgency: int) -> str:
    return URGENCY_META.get(urgency, URGENCY_META[2])["color"]


def category_color(category: str) -> str:
    return CATEGORY_META.get(category, {}).get("color", "#6B7280")


def requires_management_notification(
    risk_flags: list[str] | None = None,
    urgency: int = 1,
) -> bool:
    if urgency >= 5:
        return True
    for flag in (risk_flags or []):
        if RISK_META.get(flag, {}).get("notify_management"):
            return True
    return False

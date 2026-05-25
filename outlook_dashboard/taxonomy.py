from __future__ import annotations

CATEGORIES = [
    "VIP pre-arrival",
    "Rate inquiry",
    "Billing dispute",
    "Billing — group master",
    "Billing — no-show / PG",
    "Billing — high balance alert",
    "Billing — extended stay",
    "Billing — VIP extended stay",
    "Billing — card update",
    "Billing authorization",
    "Consortia / FHR / Virtuoso",
    "Complaint",
    "Amenity request",
    "Accessibility request",
    "Rooming list / group",
    "Internal request",
    "Internal report",
    "Internal notification",
    "Cancellation / modification",
    "Urgent same-day arrival",
    "Duplicate follow-up",
    "General inquiry",
    "Guest communication",
    "Hilton Honors / loyalty",
    "OTA pending messages",
]

PRIORITY_LEVELS = ["Low", "Normal", "High", "Immediate", "Urgent"]

RISK_FLAGS = [
    "Billing",
    "Legal",
    "Medical",
    "ADA / accessibility",
    "Discrimination",
    "VIP",
    "Chargeback",
    "Reputation risk",
    "Leadership review required",
]

STATUSES = ["New", "Reviewed", "Drafted", "Completed", "Escalated"]

DEPARTMENT_OWNERS = [
    "Front Desk",
    "Front Office",
    "Reservations",
    "Group Reservations",
    "Concierge",
    "Pre-Arrival",
    "Sales",
    "Finance",
    "Events",
    "Marketing",
    "Revenue Management",
    "Managing Director",
    "Housekeeping",
    "Engineering",
    "All Departments",
]

CONTACT_TYPES = [
    "Internal",
    "Automated",
    "Group contact",
    "Travel agent",
    "Travel agency",
    "OTA",
    "Corporate",
    "Direct guest",
]

RECOMMENDED_ACTIONS = [
    "reply_guest",
    "loop_reservations",
    "loop_front_office",
    "loop_concierge",
    "loop_housekeeping",
    "loop_engineering",
    "escalate_manager",
    "verify_payment_authorization",
    "review_folio",
    "check_reservation",
    "request_missing_information",
    "wait_for_guest",
    "wait_for_internal_team",
    "no_action_likely",
]

OPERATIONAL_QUEUES = [
    "Immediate",
    "Today",
    "Waiting on Guest",
    "Waiting on Internal Team",
    "Billing Risk",
    "VIP / Travel Advisor",
    "Complaints",
    "Low Confidence",
    "No Action Likely",
]

"""Sanitized hotel-operations golden cases for deterministic triage.

These examples are synthetic but mirror recurring ReplyRight work patterns:
payment authorization, folio review, VIP/travel advisor handling, rooming lists,
accessibility, internal routing, no-action replies, and urgent escalations.
"""
from __future__ import annotations

import pytest

from outlook_dashboard.ai import heuristic_analysis


GOLDEN_CASES = [
    ("same_day_payment", "Payment needed today", "Guest arrives today and the card authorization is missing. Please advise.", "guest@example.com", "General inquiry", "Reservations", "High", "reply_guest"),
    ("completed_cca", "Completed CCA attached", "Attached is the completed credit card authorization form. Thank you.", "advisor@agency.example", "General inquiry", "Reservations", "Normal", "verify_payment_authorization"),
    ("billing_dispute", "Incorrect folio charge", "The folio has an incorrect minibar charge and I need it reviewed.", "guest@example.com", "Billing dispute", "Reservations", "High", "review_folio"),
    ("vip_amenity", "Virtuoso VIP amenity", "Virtuoso guest arrives tomorrow. Please confirm welcome amenity and upgrade priority.", "advisor@virtuoso.example", "VIP pre-arrival", "Concierge", "High", "loop_concierge"),
    ("accessibility", "Accessible room request", "Guest needs a roll-in shower and shower chair for arrival next week.", "guest@example.com", "Accessibility request", "Reservations", "High", "escalate_manager"),
    ("rooming_list", "Final rooming list", "Attached is the final rooming list for the group block arriving Monday.", "planner@events.example", "Rooming list / group", "Sales", "Normal", "loop_reservations"),
    ("engineering", "AC not working", "Guest reports the air conditioning is not working in the room.", "frontoffice@waldorfastoria.com", "Internal request", "Engineering", "Low", "loop_engineering"),
    ("housekeeping", "Extra towels", "Please place extra towels and feather-free pillows in the room.", "guest@example.com", "General inquiry", "Housekeeping", "Normal", "loop_housekeeping"),
    ("concierge", "Dinner reservation", "Can concierge arrange dinner reservations for Saturday night?", "guest@example.com", "General inquiry", "Concierge", "Normal", "loop_concierge"),
    ("cancel", "Cancel reservation", "Please cancel my reservation for next month.", "guest@example.com", "Cancellation / modification", "Reservations", "Normal", "check_reservation"),
    ("rate", "Rate question", "Can you confirm the flexible rate and taxes for June 12?", "guest@example.com", "Rate inquiry", "Reservations", "Normal", "request_missing_information"),
    ("internal_report", "Daily report", "Attached is the daily pickup report for review.", "revenue@hilton.com", "Internal request", "Reservations", "Low", "loop_reservations"),
    ("no_action", "Thank you", "Thank you, this is all set.", "advisor@agency.example", "General inquiry", "Reservations", "Normal", "no_action_likely"),
    ("duplicate", "Following up", "Following up on my previous email below. Can someone respond?", "guest@example.com", "Duplicate follow-up", "Reservations", "Low", "reply_guest"),
    ("legal", "Attorney escalation", "My attorney will contact the hotel if this charge is not corrected.", "guest@example.com", "Billing dispute", "Reservations", "Immediate", "escalate_manager"),
    ("honors", "Hilton Honors points", "My Hilton Honors number is missing from the reservation.", "guest@example.com", "General inquiry", "Reservations", "High", "reply_guest"),
    ("ota", "Booking.com message", "Booking.com pending guest message asks to confirm check-in time.", "noreply@booking.com", "General inquiry", "Reservations", "Normal", "wait_for_guest"),
    ("group_billing", "Group master account", "Please route these charges to the group master account.", "planner@events.example", "Billing dispute", "Reservations", "High", "review_folio"),
    ("no_show", "No show charge", "Why was I charged a no-show fee when I cancelled?", "guest@example.com", "Billing dispute", "Reservations", "High", "review_folio"),
    ("card_update", "Update card", "Please update the card on file for my reservation.", "guest@example.com", "General inquiry", "Reservations", "Normal", "reply_guest"),
    ("extended", "Extend stay", "Guest would like to extend the stay by two nights.", "frontoffice@waldorfastoria.com", "Internal request", "Reservations", "Low", "loop_reservations"),
    ("vip_extended", "VIP extend stay", "Diamond VIP in house wants to extend the stay tonight.", "frontoffice@waldorfastoria.com", "Internal request", "Reservations", "Immediate", "loop_reservations"),
    ("high_balance", "High balance", "High balance alert for in-house guest requires review.", "finance@hilton.com", "Internal request", "Reservations", "Low", "loop_reservations"),
    ("guest_comms", "Guest asks arrival", "Guest asks whether early check-in is possible.", "guest@example.com", "General inquiry", "Reservations", "Normal", "reply_guest"),
    ("internal_notification", "FYI outage", "FYI the elevator maintenance notice has been posted.", "engineering@hilton.com", "Internal request", "Engineering", "Low", "loop_engineering"),
    ("medical", "Medical concern", "Guest reports a medical issue and needs immediate assistance.", "guest@example.com", "General inquiry", "Reservations", "Immediate", "escalate_manager"),
    ("refund", "Refund request", "I need a refund for the duplicate charge on my card.", "guest@example.com", "Billing dispute", "Reservations", "High", "review_folio"),
    ("travel_agency_confirm", "Agency confirmation", "Please confirm the reservation, amenities, and commission for our client.", "advisor@fhr.example", "General inquiry", "Reservations", "Normal", "reply_guest"),
    ("missing_info", "Need dates", "I want to book a room but did not include dates yet.", "guest@example.com", "General inquiry", "Reservations", "Normal", "reply_guest"),
    ("wait_internal", "Waiting on front desk", "Front desk will confirm and get back to reservations.", "frontdesk@hilton.com", "Internal request", "Reservations", "Low", "loop_reservations"),
]


@pytest.mark.parametrize(
    "case_id,subject,body,sender,category,owner,priority,recommended_action",
    GOLDEN_CASES,
    ids=[case[0] for case in GOLDEN_CASES],
)
def test_hotel_golden_case_triage(
    case_id: str,
    subject: str,
    body: str,
    sender: str,
    category: str,
    owner: str,
    priority: str,
    recommended_action: str,
) -> None:
    result = heuristic_analysis(
        {
            "subject": subject,
            "body_text": body,
            "sender_email": sender,
            "sender_name": "Sanitized Sender",
        }
    )

    assert result["category"] == category, f"{case_id}: category drifted"
    assert result["recommended_department_owner"] == owner, f"{case_id}: owner drifted"
    assert result["priority_level"] == priority, f"{case_id}: priority drifted"
    assert result["recommended_action"] == recommended_action, f"{case_id}: action drifted"

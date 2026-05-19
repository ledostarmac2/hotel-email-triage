"""Real-world hotel email triage scenarios — heuristic_analysis() only, no API keys needed."""
from __future__ import annotations

import pytest

from outlook_dashboard.ai import heuristic_analysis, urgency_score


# ── Helpers ──────────────────────────────────────────────────────────────────


def _email(subject: str = "", body: str = "", sender_email: str = "guest@example.com",
           sender_name: str = "Guest", importance: str = "normal") -> dict:
    return {
        "subject": subject,
        "body_text": body,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "importance": importance,
    }


def analyse(subject: str = "", body: str = "", sender_email: str = "guest@example.com",
            sender_name: str = "Guest", importance: str = "normal") -> dict:
    return heuristic_analysis(_email(subject, body, sender_email, sender_name, importance))


# ── VIP Pre-Arrival ───────────────────────────────────────────────────────────
# Category triggers on: "vip", "owner", "celebrity" in combined subject+body


def test_vip_keyword_triggers_category() -> None:
    r = analyse("VIP arrival", "Our VIP guest requires the presidential suite.")
    assert r["category"] == "VIP pre-arrival"


def test_vip_waldorf_suite_with_vip_keyword() -> None:
    r = analyse("Suite booking", "Our VIP client requires the Waldorf Suite for three nights.")
    assert r["category"] == "VIP pre-arrival"


def test_vip_celebrity_keyword() -> None:
    r = analyse("Celebrity check-in", "Celebrity guest needs special arrangement — full media blackout required.")
    assert r["category"] == "VIP pre-arrival"


def test_vip_owner_keyword() -> None:
    r = analyse("Owner arrival", "The property owner is arriving Friday, please arrange.")
    assert r["category"] == "VIP pre-arrival"


def test_vip_head_of_state_with_vip_keyword() -> None:
    r = analyse("VIP delegation", "VIP head of state delegation arriving Monday, towers check-in required.")
    assert r["category"] == "VIP pre-arrival"


def test_vip_ambassador_with_vip_keyword() -> None:
    r = analyse("VIP ambassador pre-arrival", "Our VIP ambassador requires the penthouse for three nights.")
    assert r["category"] == "VIP pre-arrival"


def test_vip_diamond_with_vip_keyword() -> None:
    r = analyse("Diamond VIP member", "Hilton Honors Diamond VIP member arriving, requesting upgrade and amenity.")
    assert r["category"] == "VIP pre-arrival"


def test_vip_risk_flag_present() -> None:
    r = analyse("VIP arrival", "Our VIP guest requires special treatment.")
    assert "VIP" in r.get("risk_flags", [])


def test_vip_owner_is_reservations() -> None:
    r = analyse("VIP guest", "VIP guest arriving this weekend.")
    assert r["recommended_department_owner"] == "Reservations"


# ── Billing Disputes ──────────────────────────────────────────────────────────


def test_billing_overcharge() -> None:
    r = analyse("Billing issue", "I was overcharged on my folio. Please review the incorrect charge.")
    assert r["category"] == "Billing dispute"


def test_billing_chargeback() -> None:
    r = analyse("Disputing charge", "I am initiating a chargeback with my bank for the double charge.")
    assert r["category"] == "Billing dispute"
    assert "Chargeback" in r.get("risk_flags", [])


def test_billing_folio_dispute() -> None:
    r = analyse("Folio question", "There is an error on my folio from last night. Please review.")
    assert r["category"] == "Billing dispute"


def test_billing_refund_request() -> None:
    r = analyse("Request refund", "The rate on my invoice is incorrect, I need a refund immediately.")
    assert r["category"] == "Billing dispute"


def test_billing_rate_wrong() -> None:
    r = analyse("Wrong rate applied", "The wrong rate was applied to my reservation. Please correct the invoice.")
    assert r["category"] == "Billing dispute"


def test_billing_department_is_reservations() -> None:
    r = analyse("Invoice question", "I have a billing question about my folio from last week.")
    assert r["recommended_department_owner"] == "Reservations"


def test_billing_dispute_urgency_at_least_4() -> None:
    r = analyse("Overcharge — unacceptable", "I was overcharged and this is completely unacceptable, furious.")
    score = urgency_score(r)
    assert score >= 4


def test_billing_legal_risk_flag() -> None:
    r = analyse("Legal action over billing", "I will take legal action over this billing dispute and contact my attorney.")
    assert "Legal" in r.get("risk_flags", [])


# ── Accessibility / ADA ───────────────────────────────────────────────────────


def test_accessibility_wheelchair() -> None:
    r = analyse("Accessible room", "Our guest uses a wheelchair and needs an accessible room with grab bars.")
    assert r["category"] == "Accessibility request"
    assert "ADA / accessibility" in r.get("risk_flags", [])


def test_accessibility_roll_in_shower() -> None:
    r = analyse("Roll-in shower", "Please confirm accessible room with roll-in shower and shower chair.")
    assert r["category"] == "Accessibility request"


def test_accessibility_service_animal() -> None:
    r = analyse(
        "Service animal accommodation",
        "Guest requires accessible room and will arrive with a service animal.",
    )
    assert r["category"] == "Accessibility request"


def test_accessibility_visual_impairment() -> None:
    r = analyse(
        "Vision accommodation",
        "Guest with visual impairment needs accessible accommodation with orientation assistance.",
    )
    assert r["category"] == "Accessibility request"


def test_accessibility_mobility() -> None:
    r = analyse(
        "Mobility request",
        "Guest requires wheelchair-accessible room due to mobility impairment.",
    )
    assert r["category"] == "Accessibility request"


def test_accessibility_ada_keyword() -> None:
    r = analyse("ADA accommodation", "Please confirm ADA compliance for our guest's room request.")
    assert r["category"] == "Accessibility request"


def test_accessibility_medical_device() -> None:
    r = analyse(
        "Medical accommodation",
        "Guest requires accessible room and carries medical devices including an EpiPen.",
    )
    assert r["category"] == "Accessibility request"


def test_accessibility_ada_risk_flag() -> None:
    r = analyse("Wheelchair accessible", "Guest requires wheelchair-accessible suite.")
    assert "ADA / accessibility" in r.get("risk_flags", [])


# ── Cancellation / Modification ───────────────────────────────────────────────


def test_cancellation_simple() -> None:
    r = analyse("Cancel my reservation", "I need to cancel my reservation for next week.")
    assert r["category"] == "Cancellation / modification"


def test_cancellation_modify_dates() -> None:
    r = analyse("Change check-in date", "Please modify my reservation to check in one day earlier.")
    assert r["category"] == "Cancellation / modification"


def test_cancellation_extend_stay() -> None:
    r = analyse("Modification request", "I would like to modify my reservation and extend by two nights.")
    assert r["category"] == "Cancellation / modification"


def test_cancellation_change_reservation() -> None:
    r = analyse("Change my reservation", "Please change my reservation to a different room type.")
    assert r["category"] == "Cancellation / modification"


# ── Rooming Lists / Group Blocks ──────────────────────────────────────────────


def test_rooming_list_keyword() -> None:
    r = analyse("Group rooming list", "Please find attached the rooming list for our group arriving Monday.")
    assert r["category"] == "Rooming list / group"


def test_group_block_keyword() -> None:
    r = analyse("Room block", "We need to confirm a room block of 20 rooms for our conference.")
    assert r["category"] == "Rooming list / group"


def test_group_contact_type() -> None:
    r = analyse("Group block inquiry", "We have a group block of 50 rooms for a corporate event.")
    assert r["contact_type"] == "Group contact"


def test_rooming_list_owner_is_sales() -> None:
    r = analyse("Rooming list attached", "Please see the attached rooming list for our group arrival.")
    assert r["recommended_department_owner"] == "Sales"


def test_group_not_misclassified_as_billing() -> None:
    r = analyse("Group billing instructions", "Please find the rooming list and group billing instructions attached.")
    assert r["category"] == "Rooming list / group"


# ── Same-Day / Urgent Arrivals ────────────────────────────────────────────────
# "Urgent same-day arrival" category requires "arrival" (not "arriving") in text
# alongside "today"/"tonight", OR "same-day" in text.
# urgency_score = 5 for "arriving today" / "arrival today" / "tonight" regardless of category.


def test_same_day_arrival_tonight_category() -> None:
    r = analyse("Urgent arrival tonight", "Guest arrival tonight - no confirmation received yet.")
    assert r["category"] == "Urgent same-day arrival"


def test_same_day_arrival_today_category() -> None:
    r = analyse("Arrival today", "Guest arrival today — room must be ready.")
    assert r["category"] == "Urgent same-day arrival"


def test_same_day_urgency_score_5_arriving_today() -> None:
    r = analyse("Check-in today", "Our CEO is arriving today and needs the suite immediately.")
    score = urgency_score(r)
    assert score == 5


def test_same_day_urgency_score_5_tonight() -> None:
    r = analyse("Urgent", "Guest arriving tonight, please confirm the room.")
    score = urgency_score(r)
    assert score == 5


def test_same_day_urgency_score_5_arriving_tomorrow() -> None:
    r = analyse("Arriving tomorrow", "Guest arriving tomorrow for an early check-in.")
    score = urgency_score(r)
    assert score == 5


def test_urgent_keyword_boosts_score() -> None:
    r = analyse("URGENT request", "Please respond ASAP, this is urgent and needs immediate attention.")
    score = urgency_score(r)
    assert score >= 4


# ── Complaints / Legal ────────────────────────────────────────────────────────


def test_complaint_attorney() -> None:
    r = analyse("Formal complaint", "I am furious and will contact my attorney and pursue legal action.")
    assert r["category"] == "Complaint"
    assert "Legal" in r.get("risk_flags", [])
    score = urgency_score(r)
    assert score >= 5


def test_complaint_negative_review() -> None:
    r = analyse("Terrible stay", "This was terrible and I will be leaving a negative review on TripAdvisor.")
    assert r["category"] == "Complaint"
    assert "Reputation risk" in r.get("risk_flags", [])


def test_complaint_google_review() -> None:
    r = analyse("Disappointed", "I'm extremely disappointed and will post a negative review on Google Review.")
    assert r["category"] == "Complaint"


def test_complaint_social_media() -> None:
    r = analyse("Disgraceful service", "This is disgraceful. I will share on social media immediately.")
    assert r["category"] == "Complaint"
    score = urgency_score(r)
    assert score >= 4


def test_complaint_manager_request() -> None:
    r = analyse("Escalate please", "I need to speak to a manager immediately, this is unacceptable.")
    assert r["category"] == "Complaint"


def test_complaint_lawsuit_urgent() -> None:
    r = analyse("Legal action threat", "I will file a lawsuit if this is not resolved immediately.")
    assert "Legal" in r.get("risk_flags", [])
    score = urgency_score(r)
    assert score >= 5


def test_complaint_front_desk_owner() -> None:
    r = analyse("Complaint", "I am furious about the terrible service and unacceptable conditions.")
    assert r["recommended_department_owner"] == "Front Desk"


# ── CCA / Credit Card Authorization ──────────────────────────────────────────


def test_cca_completed_routes_to_reservations() -> None:
    r = analyse("CCA completed", "I completed the credit card authorization form and sent it back.")
    assert r["recommended_department_owner"] == "Reservations"


def test_cca_category_is_general() -> None:
    r = analyse("CCA form sent", "I have submitted the credit card authorization form.")
    assert r["category"] == "General inquiry"


def test_cca_low_urgency() -> None:
    r = analyse("Authorization form returned", "I completed the credit card authorization form.")
    score = urgency_score(r)
    assert score <= 3


def test_cca_completion_not_upset_sentiment() -> None:
    r = analyse("CCA done", "Thank you for your help. I completed the authorization form and all set!")
    assert r["guest_sentiment"] in {"Positive", "Neutral"}


# ── Concierge / Amenity Requests ──────────────────────────────────────────────


def test_amenity_request_category() -> None:
    r = analyse("Amenity request", "Please arrange a special amenity for our guests on arrival.")
    assert r["category"] == "Amenity request"


def test_amenity_flowers_champagne() -> None:
    r = analyse("Surprise amenity", "Please arrange flowers and champagne as a surprise amenity for arrival.")
    assert r["category"] == "Amenity request"
    assert r["recommended_department_owner"] == "Concierge"


def test_concierge_owner_for_restaurant() -> None:
    r = analyse("Dinner reservation", "Please book a dinner reservation at your best restaurant for tonight.")
    assert r["recommended_department_owner"] == "Concierge"


def test_concierge_owner_for_car_service() -> None:
    r = analyse("Car service request", "Please arrange a car service pickup from JFK.")
    assert r["recommended_department_owner"] == "Concierge"


def test_concierge_owner_for_spa() -> None:
    r = analyse("Spa appointment", "Please book a spa appointment for tomorrow morning.")
    assert r["recommended_department_owner"] == "Concierge"


def test_concierge_owner_for_amenity_keyword() -> None:
    r = analyse("Welcome amenity", "Please arrange a welcome amenity for our guests.")
    assert r["recommended_department_owner"] == "Concierge"


# ── Rate Inquiries ────────────────────────────────────────────────────────────


def test_rate_inquiry_category() -> None:
    r = analyse("Rate inquiry", "Could you please provide the best available rate for a king room next weekend?")
    assert r["category"] == "Rate inquiry"


def test_rate_quote_category() -> None:
    r = analyse("Rate quote", "Please provide a quote for a suite for five nights.")
    assert r["category"] == "Rate inquiry"


def test_rate_pricing_category() -> None:
    r = analyse("Pricing question", "What are your pricing options for a junior suite?")
    assert r["category"] == "Rate inquiry"


def test_rate_missing_info() -> None:
    r = analyse("Rate inquiry", "What is the best available rate?")
    assert "Stay dates" in r.get("missing_information", [])
    assert "Room type" in r.get("missing_information", [])


# ── Travel Agency / Consortia ─────────────────────────────────────────────────


def test_travel_agency_contact_type_from_domain() -> None:
    r = analyse(
        "Virtuoso amenities",
        "Please confirm preferred amenities for our VIP client.",
        sender_email="advisor@virtuoso.com",
    )
    assert r["contact_type"] == "Travel agency"


def test_travel_agency_amex_domain() -> None:
    r = analyse(
        "FHR booking",
        "Booking through Fine Hotels & Resorts program, please confirm amenities.",
        sender_email="agent@amextravel.com",
    )
    assert r["contact_type"] == "Travel agency"


def test_travel_agency_altour_domain() -> None:
    r = analyse(
        "Client arrival",
        "My client is arriving Thursday.",
        sender_email="booking@altour.com",
    )
    assert r["contact_type"] == "Travel agency"


def test_consortia_fhr_keyword_in_body() -> None:
    r = analyse("FHR reservation", "This is a Fine Hotels and Resorts reservation, please confirm inclusions.")
    assert r["category"] == "Consortia / FHR / Virtuoso"


def test_consortia_virtuoso_body() -> None:
    r = analyse("Virtuoso reservation", "This is a Virtuoso booking, please apply the standard amenity package.")
    assert r["category"] == "Consortia / FHR / Virtuoso"


def test_consortia_amex_body() -> None:
    r = analyse("AMEX FHR", "This reservation was booked through Amex Fine Hotels & Resorts program.")
    assert r["category"] == "Consortia / FHR / Virtuoso"


# ── Internal / Hilton Colleagues ──────────────────────────────────────────────


def test_internal_hilton_domain() -> None:
    r = analyse(
        "Internal request",
        "Please arrange a complimentary room for our colleague.",
        sender_email="colleague@hilton.com",
    )
    assert r["contact_type"] == "Internal"
    assert r["category"] == "Internal request"


def test_internal_waldorf_domain() -> None:
    r = analyse(
        "Staff transfer",
        "Need a complimentary room for a hotel transfer.",
        sender_email="ops@waldorfastoria.com",
    )
    assert r["contact_type"] == "Internal"


def test_internal_category_low_urgency() -> None:
    r = analyse(
        "Internal room request",
        "Please set aside a room for our manager traveling from another property.",
        sender_email="mgr@hilton.com",
    )
    score = urgency_score(r)
    assert score <= 2


# ── Duplicate Follow-Up ───────────────────────────────────────────────────────


def test_follow_up_category() -> None:
    r = analyse("Following up", "This is my second request. I am following up on my previous email.")
    assert r["category"] == "Duplicate follow-up"


def test_second_request_category() -> None:
    r = analyse("Second request", "This is a second request regarding my reservation. Still no reply.")
    assert r["category"] == "Duplicate follow-up"


# ── Sentiment Detection ───────────────────────────────────────────────────────


def test_sentiment_positive_completion() -> None:
    r = analyse("Thank you", "Thank you so much, we appreciate your help. We are all set!")
    assert r["guest_sentiment"] in {"Positive", "Neutral"}


def test_sentiment_upset_furious() -> None:
    r = analyse("Terrible experience", "I am furious about the awful service and horrible conditions.")
    assert r["guest_sentiment"] == "Upset"


def test_sentiment_concerned() -> None:
    r = analyse("Issue with reservation", "I'm concerned about an error on my reservation. Please advise.")
    assert r["guest_sentiment"] in {"Concerned", "Neutral"}


def test_sentiment_neutral_quoted_upset() -> None:
    body = (
        "Hi, thank you very much! We completed the form.\n\n"
        "-----Original Message-----\n"
        "I am furious and want a manager immediately, this is unacceptable."
    )
    r = analyse("Re: CCA form", body)
    assert r["guest_sentiment"] in {"Positive", "Neutral"}


def test_sentiment_upset_legal_threat() -> None:
    r = analyse("Legal threat", "I am furious and will contact my attorney.")
    assert r["guest_sentiment"] == "Upset"


# ── Engineering / Housekeeping ────────────────────────────────────────────────


def test_engineering_owner_maintenance() -> None:
    r = analyse("Maintenance issue", "The air conditioning is not working in the room.")
    assert r["recommended_department_owner"] == "Engineering"


def test_engineering_owner_leak() -> None:
    r = analyse("Water leak", "There is a plumbing leak in the bathroom ceiling.")
    assert r["recommended_department_owner"] == "Engineering"


def test_housekeeping_owner_towels() -> None:
    r = analyse("Towels request", "We need fresh towels and clean linens for the room.")
    assert r["recommended_department_owner"] == "Housekeeping"


def test_housekeeping_owner_turndown() -> None:
    r = analyse("Turndown service", "Please arrange for turndown service at 8pm.")
    assert r["recommended_department_owner"] == "Housekeeping"


# ── Contact Type ──────────────────────────────────────────────────────────────


def test_contact_type_direct_guest_default() -> None:
    r = analyse("Room inquiry", "I'd like to book a room for next week.", sender_email="john@gmail.com")
    assert r["contact_type"] == "Direct guest"


def test_contact_type_internal_from_domain() -> None:
    r = analyse("Internal", "Internal note.", sender_email="staff@hilton.com")
    assert r["contact_type"] == "Internal"


def test_contact_type_group_from_rooming_list() -> None:
    r = analyse("Rooming list attached", "Please find the attached rooming list for our group.")
    assert r["contact_type"] == "Group contact"


# ── Priority Level ────────────────────────────────────────────────────────────


def test_priority_high_importance_flag() -> None:
    r = analyse("Important request", "Please confirm this reservation.", importance="high")
    score = urgency_score(r)
    assert score >= 3


def test_priority_low_for_simple_future_inquiry() -> None:
    r = analyse("Availability check", "Just checking if you have rooms available for December.")
    score = urgency_score(r)
    assert score <= 3


def test_priority_5_for_legal_risk() -> None:
    r = analyse("Legal action", "I am initiating a lawsuit and legal action over this chargeback.")
    score = urgency_score(r)
    assert score == 5


def test_priority_immediate_for_immediately() -> None:
    r = analyse("Urgent matter", "Please resolve this immediately.")
    score = urgency_score(r)
    assert score >= 5


# ── Confidence Score ──────────────────────────────────────────────────────────


def test_confidence_ada_is_meaningful() -> None:
    r = analyse("Wheelchair accessible room", "Guest requires a wheelchair-accessible room with roll-in shower.")
    assert int(r.get("confidence_score") or 0) >= 30


def test_confidence_general_inquiry_is_lower() -> None:
    r = analyse("Question", "I have a general question about the hotel.")
    assert int(r.get("confidence_score") or 0) < 70


def test_confidence_same_day_arrival_high() -> None:
    r = analyse("Arrival tonight CEO", "CEO arrival tonight — needs immediate suite confirmation.")
    assert int(r.get("confidence_score") or 0) >= 50


def test_confidence_internal_domain_high() -> None:
    r = analyse("Internal", "Internal request.", sender_email="mgr@hilton.com")
    assert int(r.get("confidence_score") or 0) >= 40


# ── Missing Information ───────────────────────────────────────────────────────


def test_missing_info_for_accessibility() -> None:
    r = analyse("Accessible room", "Guest requires an accessible room.")
    assert isinstance(r.get("missing_information"), (list, type(None)))


def test_next_steps_populated_for_billing() -> None:
    r = analyse("Billing dispute", "I was overcharged and need a refund.")
    assert isinstance(r.get("internal_next_steps"), list)
    assert len(r.get("internal_next_steps", [])) > 0


def test_next_steps_for_vip_pre_arrival() -> None:
    r = analyse("VIP arriving", "Our VIP guest is arriving this weekend.")
    assert isinstance(r.get("internal_next_steps"), list)
    assert len(r.get("internal_next_steps", [])) >= 1


# ── Required fields ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("field", [
    "category",
    "priority_level",
    "recommended_department_owner",
    "guest_sentiment",
    "contact_type",
    "risk_flags",
    "confidence_score",
    "missing_information",
    "internal_next_steps",
    "ai_summary",
])
def test_heuristic_always_returns_required_field(field: str) -> None:
    r = analyse("Hello", "Just a simple message.")
    assert field in r, f"Missing field: {field}"


def test_empty_email_does_not_crash() -> None:
    r = heuristic_analysis({})
    assert "category" in r


def test_all_none_fields_does_not_crash() -> None:
    r = heuristic_analysis({"subject": None, "body_text": None, "sender_email": None})
    assert "category" in r


def test_very_long_body_does_not_crash() -> None:
    body = "guest inquiry " * 2000
    r = analyse("Long email", body)
    assert "category" in r


def test_unicode_body_does_not_crash() -> None:
    r = analyse("Unicode", "Bonjour, je voudrais réserver une chambre. 🏨")
    assert "category" in r


def test_html_body_does_not_crash() -> None:
    r = analyse("HTML email", "<html><body><p>I need to <b>cancel</b> my reservation.</p></body></html>")
    assert "category" in r


def test_body_only_email() -> None:
    r = heuristic_analysis({"body_text": "Please confirm my billing folio has been corrected."})
    assert r["category"] == "Billing dispute"


def test_subject_only_email() -> None:
    r = heuristic_analysis({"subject": "VIP guest arrival tonight"})
    assert "category" in r

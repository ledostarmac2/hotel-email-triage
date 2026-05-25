"""Tests for the deterministic recommended_action field and operational queue filters.

Coverage:
  1. TestRecommendedAction — _recommended_action_for() routing rules and all 14 allowed values
  2. TestRecommendedActionViaHeuristic — recommended_action propagates through heuristic_analysis()
  3. TestOperationalQueueFilter — _apply_queue_filter() server-side filtering
  4. TestQueueEndpoint — GET /api/queues contract
  5. TestRecommendedActionScenarios — realistic hotel email scenarios from Part 6 spec

All tests are synthetic: no live Outlook, Supabase, or external AI.
"""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("GOOGLE_AI_API_KEY", "")
os.environ.setdefault("SUPABASE_URL", "")
os.environ.setdefault("SUPABASE_KEY", "")

from outlook_dashboard.ai import _recommended_action_for, heuristic_analysis
from outlook_dashboard.taxonomy import RECOMMENDED_ACTIONS, OPERATIONAL_QUEUES


# ── helpers ───────────────────────────────────────────────────────────────────


def _email(subject: str = "", body: str = "", sender: str = "guest@example.com") -> dict:
    return {
        "subject": subject,
        "body_text": body,
        "sender_email": sender,
        "sender_name": "Test Sender",
    }


def _action(**kwargs) -> str:
    """Call _recommended_action_for with sensible defaults."""
    defaults = dict(
        text="",
        category="General inquiry",
        owner="Reservations",
        urgency=2,
        risks=[],
        missing=[],
        contact_type="Direct guest",
        confidence=70,
    )
    defaults.update(kwargs)
    return _recommended_action_for(**defaults)


# ── 1. TestRecommendedAction ──────────────────────────────────────────────────


class TestRecommendedAction:
    """Unit tests for _recommended_action_for() routing logic."""

    # ── Taxonomy completeness ─────────────────────────────────────────────────

    def test_recommended_actions_constant_has_14_values(self) -> None:
        assert len(RECOMMENDED_ACTIONS) == 14

    def test_all_recommended_action_values_are_strings(self) -> None:
        for v in RECOMMENDED_ACTIONS:
            assert isinstance(v, str) and v

    def test_recommended_action_always_returns_known_value(self) -> None:
        result = _action()
        assert result in RECOMMENDED_ACTIONS

    # ── no_action_likely ─────────────────────────────────────────────────────

    def test_thank_you_note_is_no_action(self) -> None:
        assert _action(text="thank you for the wonderful stay") == "no_action_likely"

    def test_completed_non_cca_form_is_no_action(self) -> None:
        # Non-CCA completion terms: "sent it back" and "filled out" without CCA context
        assert _action(text="i have filled out the feedback survey and sent it back") == "no_action_likely"

    def test_looking_forward_is_no_action(self) -> None:
        assert _action(text="looking forward to our stay at the waldorf") == "no_action_likely"

    def test_internal_report_low_urgency_is_no_action(self) -> None:
        assert _action(category="Internal report", urgency=1) == "no_action_likely"
        assert _action(category="Internal notification", urgency=2) == "no_action_likely"

    def test_internal_report_high_urgency_not_no_action(self) -> None:
        result = _action(category="Internal report", urgency=4, text="urgent escalation needed")
        assert result != "no_action_likely"

    # ── wait_for_internal_team ────────────────────────────────────────────────

    def test_internal_says_handling_is_wait_for_internal(self) -> None:
        assert _action(
            text="i'll take care of this right away",
            contact_type="Internal",
        ) == "wait_for_internal_team"

    def test_internal_we_are_looking_into_is_wait_for_internal(self) -> None:
        assert _action(
            text="we are looking into the guest's request",
            contact_type="Internal",
        ) == "wait_for_internal_team"

    def test_non_internal_handling_phrase_not_wait_for_internal(self) -> None:
        # Same phrase from a guest does NOT trigger wait_for_internal_team
        result = _action(
            text="i'll take care of this right away",
            contact_type="Direct guest",
        )
        assert result != "wait_for_internal_team"

    # ── wait_for_guest ────────────────────────────────────────────────────────

    def test_please_provide_triggers_wait_for_guest(self) -> None:
        assert _action(text="please provide your arrival date") == "wait_for_guest"

    def test_awaiting_your_response_triggers_wait_for_guest(self) -> None:
        assert _action(text="awaiting your response on the reservation details") == "wait_for_guest"

    def test_duplicate_followup_internal_is_wait_for_guest(self) -> None:
        assert _action(
            category="Duplicate follow-up",
            contact_type="Internal",
            text="still waiting for the guest to confirm",
        ) == "wait_for_guest"

    # ── verify_payment_authorization ─────────────────────────────────────────

    def test_credit_card_authorization_form_is_verify_payment(self) -> None:
        assert _action(text="please return the credit card authorization form") == "verify_payment_authorization"

    def test_cca_term_triggers_verify_payment(self) -> None:
        # The word "cca" is detected as a whole token now (CCA fix from v0.5.4)
        assert _action(text="we need the cca completed before arrival") == "verify_payment_authorization"

    def test_billing_authorization_category_is_verify_payment(self) -> None:
        assert _action(category="Billing authorization") == "verify_payment_authorization"

    def test_billing_card_update_category_is_verify_payment(self) -> None:
        assert _action(category="Billing — card update") == "verify_payment_authorization"

    # ── escalate_manager ─────────────────────────────────────────────────────

    def test_legal_risk_flag_escalates(self) -> None:
        assert _action(risks=["Legal"]) == "escalate_manager"

    def test_medical_risk_flag_escalates(self) -> None:
        assert _action(risks=["Medical"]) == "escalate_manager"

    def test_chargeback_risk_flag_escalates(self) -> None:
        assert _action(risks=["Chargeback"]) == "escalate_manager"

    def test_reputation_risk_flag_escalates(self) -> None:
        assert _action(risks=["Reputation risk"]) == "escalate_manager"

    def test_complaint_urgency_4_escalates(self) -> None:
        assert _action(category="Complaint", urgency=4) == "escalate_manager"

    def test_complaint_urgency_5_escalates(self) -> None:
        assert _action(category="Complaint", urgency=5) == "escalate_manager"

    def test_accessibility_urgency_5_escalates(self) -> None:
        assert _action(category="Accessibility request", urgency=5) == "escalate_manager"

    # ── request_missing_information ───────────────────────────────────────────

    def test_missing_field_triggers_request_info_for_guest(self) -> None:
        assert _action(missing=["Stay dates"], contact_type="Direct guest") == "request_missing_information"

    def test_missing_field_does_not_trigger_request_info_for_internal(self) -> None:
        result = _action(missing=["Stay dates"], contact_type="Internal")
        assert result != "request_missing_information"

    def test_empty_missing_does_not_trigger_request_info(self) -> None:
        result = _action(missing=[], contact_type="Direct guest")
        assert result != "request_missing_information"

    # ── review_folio ──────────────────────────────────────────────────────────

    def test_billing_dispute_is_review_folio(self) -> None:
        assert _action(category="Billing dispute") == "review_folio"

    def test_billing_group_master_is_review_folio(self) -> None:
        assert _action(category="Billing — group master") == "review_folio"

    def test_billing_high_balance_is_review_folio(self) -> None:
        assert _action(category="Billing — high balance alert") == "review_folio"

    def test_billing_noshow_is_review_folio(self) -> None:
        assert _action(category="Billing — no-show / PG") == "review_folio"

    def test_billing_extended_stay_is_review_folio(self) -> None:
        assert _action(category="Billing — extended stay") == "review_folio"

    # ── loop_front_office ─────────────────────────────────────────────────────

    def test_same_day_arrival_is_loop_front_office(self) -> None:
        assert _action(category="Urgent same-day arrival") == "loop_front_office"

    def test_accessibility_non_escalation_is_loop_front_office(self) -> None:
        assert _action(category="Accessibility request", urgency=3) == "loop_front_office"

    def test_front_desk_owner_is_loop_front_office(self) -> None:
        assert _action(owner="Front Desk", category="General inquiry") == "loop_front_office"

    # ── loop_engineering ──────────────────────────────────────────────────────

    def test_engineering_owner_is_loop_engineering(self) -> None:
        assert _action(owner="Engineering", category="General inquiry") == "loop_engineering"

    # ── loop_housekeeping ─────────────────────────────────────────────────────

    def test_housekeeping_owner_is_loop_housekeeping(self) -> None:
        assert _action(owner="Housekeeping", category="Amenity request") == "loop_housekeeping"

    # ── loop_concierge ────────────────────────────────────────────────────────

    def test_concierge_owner_is_loop_concierge(self) -> None:
        assert _action(owner="Concierge", category="Amenity request") == "loop_concierge"

    # ── check_reservation ────────────────────────────────────────────────────

    def test_rate_inquiry_is_check_reservation(self) -> None:
        assert _action(category="Rate inquiry") == "check_reservation"

    def test_cancellation_is_check_reservation(self) -> None:
        assert _action(category="Cancellation / modification") == "check_reservation"

    def test_vip_pre_arrival_is_check_reservation(self) -> None:
        assert _action(category="VIP pre-arrival") == "check_reservation"

    def test_consortia_is_check_reservation(self) -> None:
        assert _action(category="Consortia / FHR / Virtuoso") == "check_reservation"

    # ── reply_guest ───────────────────────────────────────────────────────────

    def test_complaint_low_urgency_is_reply_guest(self) -> None:
        assert _action(category="Complaint", urgency=2) == "reply_guest"

    def test_general_inquiry_no_missing_is_reply_guest(self) -> None:
        assert _action(category="General inquiry", missing=[], contact_type="Direct guest") == "reply_guest"

    # ── loop_reservations ─────────────────────────────────────────────────────

    def test_internal_contact_default_is_loop_reservations(self) -> None:
        assert _action(category="General inquiry", contact_type="Internal") == "loop_reservations"

    def test_sales_owner_is_loop_reservations(self) -> None:
        assert _action(owner="Sales", category="General inquiry") == "loop_reservations"


# ── 2. TestRecommendedActionViaHeuristic ─────────────────────────────────────


class TestRecommendedActionViaHeuristic:
    """recommended_action is present in heuristic_analysis() output and has a valid value."""

    def test_heuristic_analysis_includes_recommended_action(self) -> None:
        result = heuristic_analysis(_email("Room inquiry", "Do you have availability in June?"))
        assert "recommended_action" in result

    def test_recommended_action_is_known_value(self) -> None:
        result = heuristic_analysis(_email("Room inquiry", "Do you have availability in June?"))
        assert result["recommended_action"] in RECOMMENDED_ACTIONS

    def test_thank_you_email_produces_no_action_likely(self) -> None:
        result = heuristic_analysis(_email(
            "Re: Stay feedback",
            "Many thanks for your hospitality. Looking forward to our stay again.",
        ))
        assert result["recommended_action"] == "no_action_likely"

    def test_engineering_email_produces_loop_engineering(self) -> None:
        result = heuristic_analysis(_email(
            "Air conditioning broken",
            "The air conditioning in our room is not working. Please send maintenance.",
        ))
        assert result["recommended_action"] == "loop_engineering"

    def test_legal_threat_produces_escalate_manager(self) -> None:
        result = heuristic_analysis(_email(
            "Billing issue — legal action",
            "I have been overcharged and my attorney will contact you if not resolved.",
        ))
        assert result["recommended_action"] == "escalate_manager"

    def test_cca_email_produces_verify_payment(self) -> None:
        result = heuristic_analysis(_email(
            "Credit card authorization",
            "Please find the completed credit card authorization form attached for your records.",
        ))
        assert result["recommended_action"] == "verify_payment_authorization"


# ── 3. TestOperationalQueueFilter ────────────────────────────────────────────


class TestOperationalQueueFilter:
    """Unit tests for _apply_queue_filter() in main.py."""

    def _make_emails(self) -> list[dict]:
        return [
            {"id": 1, "urgency_score": 5, "recommended_action": "escalate_manager", "category": "Complaint",
             "contact_type": "Direct guest", "risk_flags": [], "confidence_score": 70},
            {"id": 2, "urgency_score": 4, "recommended_action": "loop_front_office", "category": "Urgent same-day arrival",
             "contact_type": "Direct guest", "risk_flags": ["VIP"], "confidence_score": 80},
            {"id": 3, "urgency_score": 2, "recommended_action": "wait_for_guest", "category": "Rate inquiry",
             "contact_type": "Internal", "risk_flags": [], "confidence_score": 65},
            {"id": 4, "urgency_score": 1, "recommended_action": "wait_for_internal_team", "category": "Internal request",
             "contact_type": "Internal", "risk_flags": [], "confidence_score": 75},
            {"id": 5, "urgency_score": 2, "recommended_action": "review_folio", "category": "Billing dispute",
             "contact_type": "Direct guest", "risk_flags": ["Billing"], "confidence_score": 80},
            {"id": 6, "urgency_score": 2, "recommended_action": "no_action_likely", "category": "General inquiry",
             "contact_type": "Direct guest", "risk_flags": [], "confidence_score": 40},
            {"id": 7, "urgency_score": 3, "recommended_action": "reply_guest", "category": "Complaint",
             "contact_type": "Travel agency", "risk_flags": [], "confidence_score": 55},
        ]

    def _filter(self, queue: str) -> list[dict]:
        from outlook_dashboard.main import _apply_queue_filter
        return _apply_queue_filter(self._make_emails(), queue)

    def test_none_queue_returns_all(self) -> None:
        from outlook_dashboard.main import _apply_queue_filter
        emails = self._make_emails()
        assert _apply_queue_filter(emails, None) is emails

    def test_empty_queue_returns_all(self) -> None:
        from outlook_dashboard.main import _apply_queue_filter
        emails = self._make_emails()
        assert _apply_queue_filter(emails, "") is emails

    def test_immediate_queue_returns_urgency_5(self) -> None:
        result = self._filter("Immediate")
        assert all(e["urgency_score"] >= 5 for e in result)
        assert len(result) == 1

    def test_today_queue_returns_urgency_4_plus(self) -> None:
        result = self._filter("Today")
        assert all(e["urgency_score"] >= 4 for e in result)
        assert len(result) == 2

    def test_waiting_on_guest_queue(self) -> None:
        result = self._filter("Waiting on Guest")
        assert all(e["recommended_action"] == "wait_for_guest" for e in result)
        assert len(result) == 1

    def test_waiting_on_internal_team_queue(self) -> None:
        result = self._filter("Waiting on Internal Team")
        assert all(e["recommended_action"] == "wait_for_internal_team" for e in result)
        assert len(result) == 1

    def test_billing_risk_queue_matches_billing_categories(self) -> None:
        result = self._filter("Billing Risk")
        ids = {e["id"] for e in result}
        assert 5 in ids  # Billing dispute + Billing risk_flag

    def test_vip_travel_advisor_queue(self) -> None:
        result = self._filter("VIP / Travel Advisor")
        ids = {e["id"] for e in result}
        assert 2 in ids  # VIP risk flag
        assert 7 in ids  # Travel agency contact_type

    def test_complaints_queue(self) -> None:
        result = self._filter("Complaints")
        assert all(e["category"] == "Complaint" for e in result)
        assert {e["id"] for e in result} == {1, 7}

    def test_low_confidence_queue(self) -> None:
        result = self._filter("Low Confidence")
        assert all((e["confidence_score"] or 100) <= 50 for e in result)
        assert {e["id"] for e in result} == {6}

    def test_no_action_likely_queue(self) -> None:
        result = self._filter("No Action Likely")
        assert all(e["recommended_action"] == "no_action_likely" for e in result)
        assert len(result) == 1

    def test_unknown_queue_returns_all(self) -> None:
        from outlook_dashboard.main import _apply_queue_filter
        emails = self._make_emails()
        result = _apply_queue_filter(emails, "NonexistentQueue")
        assert result == emails

    def test_queue_filter_is_case_insensitive_for_known_variants(self) -> None:
        result_lower = self._filter("immediate")
        result_title = self._filter("Immediate")
        assert result_lower == result_title


# ── 4. TestQueueEndpoint ──────────────────────────────────────────────────────


class TestQueueEndpoint:
    """GET /api/queues returns the expected contract."""

    @pytest.fixture
    def client(self, tmp_path):
        import os
        os.environ["DATABASE_PATH"] = str(tmp_path / "test.sqlite3")
        from fastapi.testclient import TestClient
        from outlook_dashboard.database import initialize_database
        from outlook_dashboard.main import app
        initialize_database(db_path=tmp_path / "test.sqlite3")
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    def test_queues_endpoint_returns_200(self, client) -> None:
        resp = client.get("/api/queues")
        assert resp.status_code == 200

    def test_queues_endpoint_has_operational_queues(self, client) -> None:
        data = client.get("/api/queues").json()
        assert "operational_queues" in data
        assert isinstance(data["operational_queues"], list)
        assert len(data["operational_queues"]) >= 1

    def test_queues_endpoint_has_recommended_actions(self, client) -> None:
        data = client.get("/api/queues").json()
        assert "recommended_actions" in data
        assert "reply_guest" in data["recommended_actions"]
        assert "escalate_manager" in data["recommended_actions"]

    def test_queues_endpoint_returns_all_operational_queues(self, client) -> None:
        data = client.get("/api/queues").json()
        assert set(OPERATIONAL_QUEUES) == set(data["operational_queues"])

    def test_queues_endpoint_returns_all_recommended_actions(self, client) -> None:
        data = client.get("/api/queues").json()
        assert set(RECOMMENDED_ACTIONS) == set(data["recommended_actions"])


# ── 5. TestRecommendedActionScenarios ────────────────────────────────────────


class TestRecommendedActionScenarios:
    """Realistic hotel email scenarios covering all cases from Part 6 of the spec."""

    def _analyze(self, subject: str, body: str, sender: str = "guest@example.com") -> dict:
        return heuristic_analysis(_email(subject, body, sender))

    def test_guest_asks_for_availability_rate_quote(self) -> None:
        result = self._analyze(
            "Room availability June 15-18",
            "Hello, do you have availability for a junior suite from June 15 to 18? What is the rate?",
        )
        assert result["recommended_action"] in ("check_reservation", "request_missing_information", "reply_guest")

    def test_guest_provides_dates_but_missing_room_type(self) -> None:
        result = self._analyze(
            "Inquiry for July 4th weekend",
            "We are looking for a room from July 4 to July 7. What are your options?",
        )
        # missing room type → likely request_missing_information or check_reservation
        assert result["recommended_action"] in ("request_missing_information", "check_reservation", "reply_guest")

    def test_guest_asks_to_check_reservation(self) -> None:
        result = self._analyze(
            "Please check my reservation",
            "Could you confirm the details of my reservation? Confirmation #WALDRF123.",
        )
        assert result["recommended_action"] in ("check_reservation", "reply_guest", "loop_reservations")

    def test_missing_credit_card_authorization(self) -> None:
        result = self._analyze(
            "Credit card authorization required",
            "We need the credit card authorization form completed before your arrival date.",
            sender="reservations@waldorfastoria.com",
        )
        assert result["recommended_action"] == "verify_payment_authorization"

    def test_credit_card_authorization_completed(self) -> None:
        result = self._analyze(
            "Re: CCA Form",
            "I have completed the credit card authorization form and sent it back to you.",
        )
        # Completion of CCA — still verify_payment_authorization (must apply form)
        assert result["recommended_action"] == "verify_payment_authorization"

    def test_payment_link_problem(self) -> None:
        result = self._analyze(
            "Payment authorization problem",
            "We are having trouble processing the payment authorization for your stay.",
        )
        assert result["recommended_action"] == "verify_payment_authorization"

    def test_folio_request(self) -> None:
        result = self._analyze(
            "Request for itemized folio",
            "Could you please send me an itemized folio for my recent stay? I need it for expense reporting.",
        )
        # Folio mention under billing dispute category → review_folio
        assert result["recommended_action"] in ("review_folio", "reply_guest", "check_reservation")

    def test_refund_billing_dispute(self) -> None:
        result = self._analyze(
            "Billing dispute — incorrect charge",
            "I was charged $450 but my confirmed rate was $350 per night. Please refund the difference.",
        )
        # Billing dispute category → review_folio; escalate_manager if chargeback/legal risk present
        assert result["recommended_action"] in ("review_folio", "escalate_manager", "request_missing_information")

    def test_vip_travel_advisor_request(self) -> None:
        result = self._analyze(
            "FHR Booking Confirmation",
            "Please confirm the FHR amenities for Mr. Smith arriving June 1.",
            sender="advisor@virtuosotravel.com",
        )
        assert result["recommended_action"] in (
            "check_reservation", "loop_reservations", "reply_guest", "wait_for_guest"
        )

    def test_concierge_request(self) -> None:
        result = self._analyze(
            "Restaurant reservation request",
            "Could you please arrange a dinner reservation at the Bull and Bear for our arrival evening?",
        )
        assert result["recommended_action"] == "loop_concierge"

    def test_housekeeping_amenity_request(self) -> None:
        result = self._analyze(
            "In-room amenity setup",
            "Please ensure the room has champagne and flowers for our anniversary arrival.",
        )
        # Amenity request may need missing info (confirmation#) or route to concierge/housekeeping
        assert result["recommended_action"] in (
            "loop_concierge", "loop_housekeeping", "check_reservation", "request_missing_information"
        )

    def test_engineering_maintenance_issue(self) -> None:
        result = self._analyze(
            "Maintenance issue in room 1412",
            "The thermostat is broken and the air conditioning is not working in our room.",
        )
        assert result["recommended_action"] == "loop_engineering"

    def test_ada_accessibility_request(self) -> None:
        result = self._analyze(
            "ADA accommodation request",
            "I require a wheelchair accessible room with roll-in shower for my stay in August.",
        )
        assert result["recommended_action"] in ("loop_front_office", "escalate_manager", "check_reservation")

    def test_guest_complaint_service_recovery(self) -> None:
        result = self._analyze(
            "Terrible experience",
            "The service at your hotel was absolutely unacceptable. I expect a full refund for my stay.",
        )
        # May categorize as Complaint (escalate_manager / reply_guest) or Billing dispute (review_folio)
        assert result["recommended_action"] in ("escalate_manager", "reply_guest", "review_folio")

    def test_same_day_arrival_blocker(self) -> None:
        result = self._analyze(
            "Arriving today — no reservation found",
            "We are on our way and arriving tonight but cannot find our reservation. Please help.",
        )
        # Depending on category detection (same-day vs. general inquiry) may route to front office or reply_guest
        assert result["recommended_action"] in (
            "loop_front_office", "escalate_manager", "check_reservation", "reply_guest"
        )

    def test_internal_team_says_handling(self) -> None:
        result = self._analyze(
            "Re: Guest complaint",
            "I'm handling this guest's complaint. I have already contacted them and am working on a resolution.",
            sender="staff@waldorfastoria.com",
        )
        assert result["recommended_action"] == "wait_for_internal_team"

    def test_guest_thank_you_completed_no_action(self) -> None:
        result = self._analyze(
            "Thank you for the wonderful stay",
            "Many thanks for your hospitality. We had an amazing time. Nothing further needed.",
        )
        assert result["recommended_action"] == "no_action_likely"

    def test_waiting_on_guest_for_missing_information(self) -> None:
        result = self._analyze(
            "Re: Reservation inquiry",
            "We are still waiting for the guest to confirm their arrival date. Please provide the dates.",
            sender="reservations@waldorfastoria.com",
        )
        assert result["recommended_action"] == "wait_for_guest"

    def test_waiting_on_internal_team_for_followup(self) -> None:
        result = self._analyze(
            "Re: Group block",
            "The sales team is aware and they are looking into the group block status.",
            sender="staff@hilton.com",
        )
        assert result["recommended_action"] == "wait_for_internal_team"

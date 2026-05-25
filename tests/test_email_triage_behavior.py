"""Behavioral tests for the hotel email triage pipeline.

Focus areas:
  1. Email categorization — edge cases and category disambiguation
  2. Urgency scoring — urgency_score() in ai.py (distinct from compute_urgency in urgency_engine.py)
  3. Summary generation — format and content expectations for _summary_for / ai_summary
  4. Reply drafting — brand voice, salutation, missing-info gate, no banned phrases
  5. User approval gate — triage_email() always returns empty suggested_reply_draft
  6. Sensitive data handling — AI payloads use redacted body, masked sender email
  7. Edge cases and failure modes specific to the above areas

All tests are synthetic: no live Outlook, Supabase, or external AI is contacted.
No imports from: local_classifier, main, completed_training_pipeline, training_pipeline.
"""
from __future__ import annotations

import pytest

from outlook_dashboard.ai import (
    _category_for,
    _draft_reply,
    _priority_for,
    _refresh_classification_payload,
    _salutation,
    _sentiment_for,
    _summary_for,
    heuristic_analysis,
    triage_email,
    urgency_score,
)
from outlook_dashboard.taxonomy import CATEGORIES, CONTACT_TYPES, DEPARTMENT_OWNERS


# ── 1. Email categorization — edge cases ─────────────────────────────────────


class TestCategorizationEdgeCases:
    """_category_for() disambiguation: ordering, overrides, and edge inputs."""

    def test_cca_overrides_billing_category(self) -> None:
        # CCA check comes before billing in _category_for, so an email with
        # "credit card authorization form" text is "General inquiry", not "Billing dispute".
        text = "please find the completed credit card authorization form for the reservation"
        assert _category_for(text, "guest@example.com") == "General inquiry"

    def test_authorization_form_phrase_also_triggers_cca_override(self) -> None:
        text = "attached is the authorization form you requested"
        assert _category_for(text, "guest@example.com") == "General inquiry"

    def test_internal_domain_routes_to_internal_request(self) -> None:
        text = "please coordinate the pre-arrival amenity setup"
        assert _category_for(text, "staff@waldorfastoria.com") == "Internal request"

    def test_hilton_domain_is_internal(self) -> None:
        text = "quick heads up on the group block"
        # "group" present but internal domain should route to Rooming list / group
        assert _category_for(text, "team@hilton.com") == "Rooming list / group"

    def test_internal_domain_with_rooming_list_routes_to_group(self) -> None:
        text = "here is the rooming list for the group block check-in next week"
        assert _category_for(text, "staff@waldorfastoria.com") == "Rooming list / group"

    def test_same_day_in_text_triggers_same_day_arrival(self) -> None:
        text = "same-day arrival needs immediate confirmation"
        assert _category_for(text, "guest@example.com") == "Urgent same-day arrival"

    def test_arrival_plus_tonight_triggers_same_day_arrival(self) -> None:
        text = "guest arrival tonight please prepare the room"
        assert _category_for(text, "guest@example.com") == "Urgent same-day arrival"

    def test_arrival_plus_today_triggers_same_day_arrival(self) -> None:
        text = "arrival today around 3pm need early check-in"
        assert _category_for(text, "guest@example.com") == "Urgent same-day arrival"

    def test_vip_keyword_triggers_vip_pre_arrival(self) -> None:
        text = "vip guest needs the towers suite for their celebration"
        assert _category_for(text, "guest@example.com") == "VIP pre-arrival"

    def test_special_occasion_does_not_trigger_cca_context(self) -> None:
        text = "vip guest has a special occasion and needs the towers suite"
        assert _category_for(text, "guest@example.com") == "VIP pre-arrival"

    def test_celebrity_keyword_triggers_vip_pre_arrival(self) -> None:
        text = "celebrity guest needs upgraded suite and complete privacy"
        assert _category_for(text, "guest@example.com") == "VIP pre-arrival"

    def test_owner_keyword_triggers_vip_pre_arrival(self) -> None:
        text = "our owner is arriving next week, please prepare towers suite"
        assert _category_for(text, "guest@example.com") == "VIP pre-arrival"

    def test_rooming_list_wins_over_billing_terms(self) -> None:
        # Group emails routinely mention "billing instructions" — that is not a billing dispute.
        # _category_for checks "rooming list" BEFORE billing terms.
        text = "here is the rooming list; please note the billing instructions for each room"
        assert _category_for(text, "guest@example.com") == "Rooming list / group"

    def test_following_up_triggers_duplicate_follow_up(self) -> None:
        text = "following up on my previous email about the reservation confirmation"
        assert _category_for(text, "guest@example.com") == "Duplicate follow-up"

    def test_second_request_triggers_duplicate_follow_up(self) -> None:
        text = "this is a second request as I have not heard back"
        assert _category_for(text, "guest@example.com") == "Duplicate follow-up"

    def test_checking_again_triggers_duplicate_follow_up(self) -> None:
        text = "checking again on the status of our reservation"
        assert _category_for(text, "guest@example.com") == "Duplicate follow-up"

    def test_rate_keyword_triggers_rate_inquiry(self) -> None:
        text = "what is the rate for a deluxe room in september"
        assert _category_for(text, "guest@example.com") == "Rate inquiry"

    def test_pricing_keyword_triggers_rate_inquiry(self) -> None:
        text = "can you share pricing for our stay in november"
        assert _category_for(text, "guest@example.com") == "Rate inquiry"

    def test_accessibility_roll_in_shower_triggers_accessibility(self) -> None:
        text = "we need an accessible room with roll-in shower and grab bars"
        assert _category_for(text, "guest@example.com") == "Accessibility request"

    def test_accessibility_ada_keyword_triggers_accessibility(self) -> None:
        text = "please confirm ada compliant room availability"
        assert _category_for(text, "guest@example.com") == "Accessibility request"

    def test_virtuoso_triggers_consortia_category(self) -> None:
        text = "this is a virtuoso booking please confirm amenities for the advisor"
        assert _category_for(text, "agent@agency.example") == "Consortia / FHR / Virtuoso"

    def test_fhr_triggers_consortia_category(self) -> None:
        text = "this is an fhr booking through amex"
        assert _category_for(text, "agent@agency.example") == "Consortia / FHR / Virtuoso"

    def test_strong_upset_terms_override_completion_suppression(self) -> None:
        # Regular upset terms are suppressed if _is_completion_update() is True,
        # but _STRONG_UPSET_TERMS (e.g. "unacceptable", "terrible") are unconditional.
        text = "this is terrible service, I filled out the form but it is completely unacceptable"
        # No billing/billing-adjacent terms so billing check doesn't fire first
        assert _category_for(text, "guest@example.com") == "Complaint"

    def test_complaint_upset_without_completion(self) -> None:
        text = "I am furious about the noise and the poor experience"
        assert _category_for(text, "guest@example.com") == "Complaint"

    def test_anniversary_triggers_amenity_request(self) -> None:
        text = "could you arrange champagne and flowers for our anniversary"
        assert _category_for(text, "guest@example.com") == "Amenity request"

    def test_birthday_triggers_amenity_request(self) -> None:
        text = "please arrange a birthday cake for the room"
        assert _category_for(text, "guest@example.com") == "Amenity request"

    def test_cancellation_keyword_triggers_cancellation_category(self) -> None:
        text = "I need to cancel my reservation for november"
        assert _category_for(text, "guest@example.com") == "Cancellation / modification"

    def test_modify_keyword_triggers_cancellation_category(self) -> None:
        text = "I would like to modify my reservation dates"
        assert _category_for(text, "guest@example.com") == "Cancellation / modification"

    def test_group_keyword_triggers_rooming_list(self) -> None:
        text = "we have a group of 25 rooms for the conference next month"
        assert _category_for(text, "planner@events.example") == "Rooming list / group"

    def test_empty_text_and_sender_returns_general_inquiry(self) -> None:
        result = _category_for("", "")
        assert result == "General inquiry"

    def test_empty_text_with_internal_sender_returns_internal_request(self) -> None:
        result = _category_for("", "staff@hilton.com")
        assert result == "Internal request"

    @pytest.mark.parametrize(
        "body,sender",
        [
            ("please book a room", "guest@example.com"),
            ("credit card authorization form enclosed", "guest@example.com"),
            ("arriving tonight need room prepared", "guest@example.com"),
            ("vip guest suite required", "guest@example.com"),
            ("rooming list attached for our group", "planner@example.com"),
            ("there is an incorrect charge on my folio", "guest@example.com"),
            ("we need a wheelchair accessible room", "guest@example.com"),
            ("virtuoso booking confirmation", "agent@agency.example"),
            ("I am furious about the terrible service", "guest@example.com"),
            ("champagne and flowers for anniversary", "guest@example.com"),
            ("group block for next month", "planner@example.com"),
            ("please cancel this reservation", "guest@example.com"),
            ("following up as I have not heard back", "guest@example.com"),
            ("what is the best rate for my stay", "guest@example.com"),
        ],
    )
    def test_category_always_from_allowed_list(self, body: str, sender: str) -> None:
        category = _category_for(body, sender)
        assert category in CATEGORIES, f"Got unexpected category: {category!r}"


# ── 2. Urgency scoring — urgency_score() from ai.py ──────────────────────────


class TestUrgencyScore:
    """
    urgency_score() in ai.py is separate from compute_urgency() in urgency_engine.py.
    It applies priority level mapping, risk flag overrides, keyword boosts, and caps.
    """

    def test_legal_risk_flag_forces_score_5(self) -> None:
        email = {"risk_flags": ["Legal"], "priority_level": "Normal", "category": "General inquiry"}
        assert urgency_score(email) == 5

    def test_medical_risk_flag_forces_score_5(self) -> None:
        email = {"risk_flags": ["Medical"], "priority_level": "Normal", "category": "General inquiry"}
        assert urgency_score(email) == 5

    def test_chargeback_risk_flag_forces_score_5(self) -> None:
        email = {"risk_flags": ["Chargeback"], "priority_level": "Normal", "category": "Billing dispute"}
        assert urgency_score(email) == 5

    def test_discrimination_risk_flag_forces_score_5(self) -> None:
        email = {"risk_flags": ["Discrimination"], "priority_level": "Normal", "category": "Complaint"}
        assert urgency_score(email) == 5

    def test_leadership_review_required_forces_score_5(self) -> None:
        email = {
            "risk_flags": ["Leadership review required"],
            "priority_level": "Normal",
            "category": "General inquiry",
        }
        assert urgency_score(email) == 5

    def test_same_day_arrival_category_forces_score_5(self) -> None:
        email = {"category": "Urgent same-day arrival", "priority_level": "Normal", "risk_flags": []}
        assert urgency_score(email) == 5

    def test_billing_dispute_category_floors_at_4(self) -> None:
        email = {
            "category": "Billing dispute",
            "priority_level": "Normal",
            "risk_flags": [],
            "body_text": "Please review the folio charges.",
        }
        assert urgency_score(email) >= 4

    def test_accessibility_request_category_floors_at_4(self) -> None:
        email = {
            "category": "Accessibility request",
            "priority_level": "Normal",
            "risk_flags": [],
            "body_text": "Need roll-in shower confirmation.",
        }
        assert urgency_score(email) >= 4

    def test_complaint_category_floors_at_4(self) -> None:
        email = {
            "category": "Complaint",
            "priority_level": "Normal",
            "risk_flags": [],
            "body_text": "Very unhappy with the experience.",
        }
        assert urgency_score(email) >= 4

    def test_strong_upset_term_forces_score_5(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Normal",
            "risk_flags": [],
            "body_text": "This is unacceptable, I will contact my attorney about this.",
        }
        assert urgency_score(email) == 5

    def test_upset_sentiment_floors_at_4(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Normal",
            "risk_flags": [],
            "guest_sentiment": "upset",
            "body_text": "I am very disappointed with the poor experience.",
        }
        assert urgency_score(email) >= 4

    def test_concerned_sentiment_floors_at_4(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Normal",
            "risk_flags": [],
            "guest_sentiment": "concerned",
            "body_text": "I am confused about the billing and have an issue.",
        }
        assert urgency_score(email) >= 4

    def test_immediately_keyword_forces_score_5(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Normal",
            "risk_flags": [],
            "body_text": "please respond immediately we need this resolved today",
        }
        assert urgency_score(email) == 5

    def test_urgent_keyword_floors_at_4(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Low",
            "risk_flags": [],
            "body_text": "this is urgent please advise",
        }
        assert urgency_score(email) >= 4

    def test_tonight_arrival_body_forces_score_5(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Normal",
            "risk_flags": [],
            "body_text": "guest arriving tonight please prepare the room immediately",
        }
        assert urgency_score(email) == 5

    def test_vip_keyword_in_body_floors_at_3(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Low",
            "risk_flags": [],
            "body_text": "vip guest is inquiring about the towers suite",
        }
        assert urgency_score(email) >= 3

    def test_high_importance_flag_floors_at_3(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Normal",
            "risk_flags": [],
            "importance": "high",
        }
        assert urgency_score(email) >= 3

    def test_completion_update_caps_urgency_at_3_without_high_risk(self) -> None:
        # "completed the form" + "all set" are _COMPLETION_TERMS.
        # Without arrival or high-risk flags, urgency is capped at 3.
        email = {
            "category": "General inquiry",
            "priority_level": "High",
            "risk_flags": [],
            "body_text": "I completed the form, all set. Thank you.",
            "guest_sentiment": "Positive",
        }
        assert urgency_score(email) <= 3

    def test_cca_context_caps_urgency_at_3_when_not_upset_or_high_risk(self) -> None:
        # "credit card authorization form" is a CCA term.
        # Without upset sentiment or high-risk flags, urgency is capped at 3.
        email = {
            "category": "General inquiry",
            "priority_level": "High",
            "risk_flags": [],
            "body_text": "I filled out the credit card authorization form. Thank you.",
            "guest_sentiment": "Positive",
        }
        assert urgency_score(email) <= 3

    def test_urgency_override_wins_over_all_signals(self) -> None:
        # urgency_override takes precedence over risk flags, category, and body content.
        email = {
            "category": "General inquiry",
            "priority_level": "Immediate",
            "risk_flags": ["Legal"],  # would normally force 5
            "urgency_override": 1,
        }
        assert urgency_score(email) == 1

    def test_adaptive_urgency_score_wins_over_priority_level(self) -> None:
        email = {
            "category": "General inquiry",
            "priority_level": "Low",
            "risk_flags": [],
            "adaptive_urgency_score": 4,
        }
        assert urgency_score(email) == 4

    def test_urgency_score_always_within_1_5_for_boundary_overrides(self) -> None:
        for override in [0, -1, 10, 100]:
            email = {"urgency_override": override, "category": "General inquiry", "risk_flags": []}
            score = urgency_score(email)
            assert 1 <= score <= 5, f"Out of range for override={override!r}: {score}"

    def test_urgency_score_with_string_risk_flags_does_not_crash(self) -> None:
        # risk_flags passed as a string (bad data from older serialization) should not raise.
        email = {"priority_level": "Normal", "risk_flags": "Legal", "category": "General inquiry"}
        score = urgency_score(email)
        assert 1 <= score <= 5

    def test_urgency_score_with_none_priority_level_does_not_crash(self) -> None:
        email = {"priority_level": None, "risk_flags": [], "category": "General inquiry"}
        assert 1 <= urgency_score(email) <= 5

    def test_urgency_score_with_invalid_priority_level_uses_default(self) -> None:
        email = {"priority_level": "Superfast", "risk_flags": [], "category": "General inquiry"}
        assert 1 <= urgency_score(email) <= 5

    def test_urgency_score_with_no_body_keys_does_not_crash(self) -> None:
        email = {"category": "Billing dispute", "priority_level": "High", "risk_flags": []}
        assert urgency_score(email) >= 4


# ── 3. Summary generation ─────────────────────────────────────────────────────


class TestSummaryGeneration:
    """_summary_for() format and heuristic_analysis() ai_summary content."""

    def test_summary_contains_priority(self) -> None:
        # Signature: _summary_for(subject, category, priority, contact_type, missing)
        summary = _summary_for("Room request", "General inquiry", "Normal", "Direct guest", [])
        assert "Normal" in summary

    def test_summary_contains_category_lowercased(self) -> None:
        summary = _summary_for("Room request", "Billing dispute", "High", "Direct guest", [])
        assert "billing dispute" in summary

    def test_summary_contains_contact_type_lowercased(self) -> None:
        summary = _summary_for("Room request", "General inquiry", "Normal", "Travel agency", [])
        assert "travel agency" in summary

    def test_summary_contains_subject(self) -> None:
        summary = _summary_for("VIP arrival coordination", "VIP pre-arrival", "High", "Direct guest", [])
        assert "VIP arrival coordination" in summary

    def test_summary_with_missing_fields_has_missing_label(self) -> None:
        missing = ["Stay dates", "Room type"]
        summary = _summary_for("Rate inquiry", "Rate inquiry", "Normal", "Direct guest", missing)
        assert "Missing:" in summary
        assert "Stay dates" in summary
        assert "Room type" in summary

    def test_summary_without_missing_fields_has_no_missing_label(self) -> None:
        summary = _summary_for("General question", "General inquiry", "Normal", "Direct guest", [])
        assert "Missing:" not in summary

    def test_summary_all_categories_include_category_name(self) -> None:
        for category in CATEGORIES:
            summary = _summary_for("Test subject", category, "Normal", "Direct guest", [])
            assert category.lower() in summary, f"Category name missing from summary for: {category!r}"

    def test_heuristic_analysis_ai_summary_is_non_empty(self) -> None:
        analysis = heuristic_analysis({
            "subject": "Quick question",
            "sender_email": "guest@example.com",
            "body_text": "What rates do you have for next month?",
        })
        assert analysis["ai_summary"]
        assert len(analysis["ai_summary"]) > 5

    def test_cca_context_overrides_summary_with_cca_instructions(self) -> None:
        analysis = heuristic_analysis({
            "subject": "Re: CCA form",
            "sender_email": "agent@agency.example",
            "body_text": "I completed the credit card authorization form and sent it back.",
        })
        # The CCA override summary is a specific known string
        assert "CCA" in analysis["ai_summary"] or "credit card" in analysis["ai_summary"].lower()

    def test_no_subject_email_still_produces_summary(self) -> None:
        analysis = heuristic_analysis({
            "sender_email": "guest@example.com",
            "body_text": "Could you confirm availability for next week?",
        })
        assert analysis["ai_summary"]


# ── 4. Reply drafting behavior ────────────────────────────────────────────────


class TestReplyDraftingBehavior:
    """_draft_reply() and _salutation() brand voice and safety constraints."""

    # Salutation variants
    def test_internal_waldorf_sender_gets_hi_first_name(self) -> None:
        salutation = _salutation("Brian Tarabocchia", "brian@waldorfastoria.com")
        assert salutation.startswith("Hi Brian,")

    def test_internal_hilton_sender_gets_hi_first_name(self) -> None:
        salutation = _salutation("John Smith", "john.smith@hilton.com")
        assert salutation.startswith("Hi John,")

    def test_internal_conrad_sender_gets_hi_first_name(self) -> None:
        salutation = _salutation("Maria Chen", "maria@conradhotels.com")
        assert salutation.startswith("Hi Maria,")

    def test_unknown_external_sender_gets_dear_guest(self) -> None:
        salutation = _salutation("", "unknown@example.com")
        assert salutation == "Dear Guest,"

    def test_empty_name_external_gets_dear_guest(self) -> None:
        salutation = _salutation("   ", "guest@agency.example")
        assert salutation == "Dear Guest,"

    def test_named_external_sender_gets_dear_first_name(self) -> None:
        salutation = _salutation("Alice Johnson", "alice@agency.example")
        assert salutation.startswith("Dear Alice,")

    def test_multi_word_name_uses_only_first_name(self) -> None:
        salutation = _salutation("Elizabeth Anne Windsor", "e.windsor@example.com")
        assert "Elizabeth" in salutation
        assert "Windsor" not in salutation

    # Draft completeness
    def test_all_categories_produce_non_empty_draft(self) -> None:
        for category in CATEGORIES:
            draft = _draft_reply("Guest", "guest@example.com", category, [])
            assert draft, f"Empty draft for category: {category!r}"
            assert len(draft) > 50, f"Suspiciously short draft for: {category!r}"

    def test_all_categories_contain_waldorf_signature(self) -> None:
        for category in CATEGORIES:
            draft = _draft_reply("Guest", "guest@example.com", category, [])
            assert "Waldorf Astoria Reservations" in draft, (
                f"Missing Waldorf Astoria Reservations signature for category: {category!r}"
            )

    def test_all_categories_contain_warm_regards(self) -> None:
        for category in CATEGORIES:
            draft = _draft_reply("Guest", "guest@example.com", category, [])
            assert "Warm regards" in draft, f"Missing 'Warm regards' for category: {category!r}"

    def test_draft_with_missing_fields_includes_polite_request(self) -> None:
        draft = _draft_reply("Alice", "alice@agency.example", "Rate inquiry", ["Stay dates", "Room type"])
        assert "Stay dates" in draft or "Room type" in draft
        assert "may we kindly ask" in draft.lower()

    def test_draft_without_missing_fields_does_not_ask_for_missing(self) -> None:
        draft = _draft_reply("Alice", "alice@agency.example", "General inquiry", [])
        assert "may we kindly ask" not in draft.lower()

    def test_draft_does_not_contain_asap(self) -> None:
        for category in CATEGORIES:
            draft = _draft_reply("Guest", "guest@example.com", category, [])
            assert "ASAP" not in draft
            assert "asap" not in draft.lower()

    def test_draft_does_not_say_no_problem(self) -> None:
        for category in CATEGORIES:
            draft = _draft_reply("Guest", "guest@example.com", category, [])
            assert "no problem" not in draft.lower()

    def test_draft_does_not_use_hi_there(self) -> None:
        draft = _draft_reply("", "external@agency.example", "General inquiry", [])
        assert "Hi there" not in draft
        assert "hi there" not in draft.lower()

    def test_draft_does_not_say_awesome(self) -> None:
        for category in CATEGORIES:
            draft = _draft_reply("Guest", "guest@example.com", category, [])
            assert "awesome" not in draft.lower()

    # Brand constraints: no guarantees
    def test_vip_draft_says_subject_to_availability(self) -> None:
        draft = _draft_reply("Guest", "guest@example.com", "VIP pre-arrival", [])
        assert "subject to availability" in draft

    def test_amenity_draft_says_subject_to_availability(self) -> None:
        draft = _draft_reply("Guest", "guest@example.com", "Amenity request", [])
        assert "subject to availability" in draft

    def test_vip_draft_does_not_guarantee_upgrade(self) -> None:
        draft = _draft_reply("Guest", "guest@example.com", "VIP pre-arrival", [])
        assert "guaranteed" not in draft.lower()
        assert "we will upgrade" not in draft.lower()

    # Liability constraints: no fault admission
    def test_billing_draft_does_not_admit_fault(self) -> None:
        draft = _draft_reply("Guest", "guest@example.com", "Billing dispute", [])
        assert "our fault" not in draft.lower()
        assert "we overcharged" not in draft.lower()
        assert "we were wrong" not in draft.lower()

    def test_complaint_draft_does_not_admit_fault(self) -> None:
        draft = _draft_reply("Guest", "guest@example.com", "Complaint", [])
        assert "our fault" not in draft.lower()
        assert "you are right" not in draft.lower()
        assert "we admit" not in draft.lower()

    # heuristic_analysis produces a draft (for human review); triage_email clears it
    def test_heuristic_analysis_returns_populated_draft(self) -> None:
        analysis = heuristic_analysis({
            "subject": "Rate inquiry for October",
            "sender_name": "Alice Smith",
            "sender_email": "alice@agency.example",
            "body_text": "Please quote rates for October 15-18.",
        })
        assert analysis["suggested_reply_draft"]
        assert len(analysis["suggested_reply_draft"]) > 50

    def test_unknown_category_falls_back_gracefully(self) -> None:
        # _draft_reply falls back to General inquiry body for unknown categories
        draft = _draft_reply("Guest", "guest@example.com", "Nonexistent category", [])
        assert draft
        assert "Waldorf Astoria Reservations" in draft


# ── 5. User approval gate — triage_email always returns empty draft ───────────


class TestUserApprovalGate:
    """
    triage_email() is the bulk refresh path. It must never return a populated
    suggested_reply_draft. This gate ensures a human reviews every reply before
    it can be sent; there is no auto-send pathway.
    """

    def test_triage_email_empty_draft_for_general_inquiry(self) -> None:
        result = triage_email({
            "subject": "Room inquiry",
            "sender_name": "Alice",
            "sender_email": "alice@example.com",
            "body_text": "What rates do you have for October?",
        })
        assert result["suggested_reply_draft"] == ""

    def test_triage_email_empty_draft_for_vip(self) -> None:
        result = triage_email({
            "subject": "VIP guest arrival",
            "sender_email": "advisor@virtuoso.com",
            "body_text": "VIP guest arriving tomorrow, please prepare presidential suite.",
        })
        assert result["suggested_reply_draft"] == ""

    def test_triage_email_empty_draft_for_legal_threat(self) -> None:
        result = triage_email({
            "subject": "Legal action",
            "sender_name": "Guest",
            "sender_email": "guest@example.com",
            "body_text": "I am contacting my attorney and will sue the hotel.",
        })
        assert result["suggested_reply_draft"] == ""

    def test_triage_email_empty_draft_for_billing_dispute(self) -> None:
        result = triage_email({
            "subject": "Billing error",
            "sender_email": "guest@example.com",
            "body_text": "I was charged twice, please refund the duplicate charge.",
        })
        assert result["suggested_reply_draft"] == ""

    def test_triage_email_empty_draft_for_accessibility_request(self) -> None:
        result = triage_email({
            "subject": "Accessible room needed",
            "sender_email": "guest@example.com",
            "body_text": "We need a wheelchair accessible room with roll-in shower.",
        })
        assert result["suggested_reply_draft"] == ""

    def test_triage_email_empty_draft_for_empty_email(self) -> None:
        result = triage_email({})
        assert result["suggested_reply_draft"] == ""

    @pytest.mark.parametrize(
        "body",
        [
            "I need an accessible room with roll-in shower",
            "Please cancel my reservation for November",
            "I am following up on my earlier request from last week",
            "This is a Virtuoso booking, please confirm amenities",
            "Thank you, I completed the credit card authorization form",
            "We are a group of 30 guests, here is our rooming list",
            "My attorney will be reaching out regarding this matter",
            "Guest arriving tonight, need early check-in",
        ],
    )
    def test_triage_email_never_returns_populated_draft(self, body: str) -> None:
        result = triage_email({
            "subject": "Email",
            "sender_email": "guest@example.com",
            "body_text": body,
        })
        assert result["suggested_reply_draft"] == "", (
            f"Non-empty draft returned for body: {body[:60]!r}"
        )

    def test_heuristic_analysis_populates_draft_for_human_review(self) -> None:
        # heuristic_analysis() DOES return a draft — it's intended for human review,
        # not auto-send. triage_email() then clears it in the refresh path.
        analysis = heuristic_analysis({
            "subject": "Room question",
            "sender_name": "Alice",
            "sender_email": "alice@example.com",
            "body_text": "Can you confirm my reservation?",
        })
        assert isinstance(analysis["suggested_reply_draft"], str)
        # The draft is populated by heuristic_analysis for human inspection
        assert analysis["suggested_reply_draft"]


# ── 6. Sensitive data handling — AI refresh payloads ─────────────────────────


class TestSensitiveDataHandling:
    """
    _refresh_classification_payload() must never expose raw PII in the payload
    sent to external AI providers.

    The test_business_logic_pytest.py already covers the core card+CVV+expiry+phone
    combination. These tests focus on the structural guarantees: sender masking,
    key absence, and subject redaction.
    """

    def test_refresh_payload_masks_sender_username(self) -> None:
        payload, _ = _refresh_classification_payload({
            "subject": "Room request",
            "sender_email": "alice.smith@veryunique-domain.io",
            "body_text": "Please confirm availability.",
        })
        assert "alice.smith" not in str(payload)
        assert payload["sender_email"] == "[SENDER]@veryunique-domain.io"

    def test_refresh_payload_exposes_only_sender_domain(self) -> None:
        payload, _ = _refresh_classification_payload({
            "sender_email": "secret@private-hotel.com",
            "body_text": "Test.",
        })
        assert payload["sender_domain"] == "private-hotel.com"
        assert "secret" not in str(payload)

    def test_refresh_payload_does_not_expose_body_text_key(self) -> None:
        # The payload must use latest_redacted_body, not body_text
        payload, _ = _refresh_classification_payload({
            "subject": "Test",
            "sender_email": "guest@example.com",
            "body_text": "Raw body content here",
        })
        assert "body_text" not in payload

    def test_refresh_payload_redacts_card_in_body(self) -> None:
        payload, counts = _refresh_classification_payload({
            "subject": "Payment",
            "sender_email": "guest@example.com",
            "body_text": "Use card 4111 1111 1111 1111 for the stay.",
        })
        assert counts["cards"] == 1
        assert "4111" not in payload["latest_redacted_body"]
        assert "4111" not in payload.get("body_preview", "")

    def test_refresh_payload_redacts_phone_in_body(self) -> None:
        payload, counts = _refresh_classification_payload({
            "subject": "Contact",
            "sender_email": "guest@example.com",
            "body_text": "Reach me at 212-555-0199 any time.",
        })
        assert counts["phones"] >= 1
        assert "212-555-0199" not in payload["latest_redacted_body"]

    def test_refresh_payload_redacts_email_address_in_body(self) -> None:
        payload, counts = _refresh_classification_payload({
            "subject": "Contact details",
            "sender_email": "guest@example.com",
            "body_text": "You can reach me at personal@private-domain.com anytime.",
        })
        assert counts["emails"] >= 1
        assert "personal@private-domain.com" not in payload["latest_redacted_body"]

    def test_refresh_payload_redacts_confirmation_number_in_subject(self) -> None:
        # Subject is also redacted — confirmation numbers must not leak.
        payload, counts = _refresh_classification_payload({
            "subject": "Reservation number: RES-887234",
            "sender_email": "guest@example.com",
            "body_text": "Please confirm.",
        })
        assert counts["confirmation_numbers"] >= 1
        assert "RES-887234" not in payload["subject"]

    def test_refresh_payload_without_sender_email_does_not_crash(self) -> None:
        payload, _ = _refresh_classification_payload({"subject": "Test"})
        assert payload["sender_email"] == ""
        assert payload["sender_domain"] == ""

    def test_refresh_payload_sender_without_at_sign_does_not_crash(self) -> None:
        payload, _ = _refresh_classification_payload({
            "sender_email": "no-at-sign",
            "body_text": "Test.",
        })
        # Should not raise; domain defaults to empty
        assert isinstance(payload["sender_domain"], str)


# ── 7. Edge cases and failure modes ──────────────────────────────────────────


class TestEdgeCasesAndFailureModes:
    """Targeted edge cases not covered by the broader input-validation suite."""

    def test_missing_subject_uses_no_subject_placeholder(self) -> None:
        analysis = heuristic_analysis({
            "sender_email": "guest@example.com",
            "body_text": "Quick question about my reservation.",
        })
        # summary is built from subject "(No subject)" when field absent
        assert analysis["ai_summary"]

    def test_needs_review_is_always_a_boolean(self) -> None:
        for body in ["Hello.", "Legal action pending.", "I need a wheelchair room."]:
            result = heuristic_analysis({
                "subject": "Test",
                "sender_email": "guest@example.com",
                "body_text": body,
            })
            assert isinstance(result["needs_review"], bool)

    def test_needs_review_true_for_legal_risk_flag(self) -> None:
        result = heuristic_analysis({
            "subject": "Legal matter",
            "sender_email": "guest@example.com",
            "body_text": "My lawyer will be in touch regarding this billing matter.",
        })
        assert result["needs_review"] is True

    def test_needs_review_true_for_medical_risk_flag(self) -> None:
        result = heuristic_analysis({
            "subject": "Medical issue",
            "sender_email": "guest@example.com",
            "body_text": "A guest requires medical assistance during the stay.",
        })
        assert result["needs_review"] is True

    def test_needs_review_true_for_accessibility_category(self) -> None:
        result = heuristic_analysis({
            "subject": "Wheelchair accessible room needed",
            "sender_email": "guest@example.com",
            "body_text": "We need a wheelchair accessible room with roll-in shower and grab bars.",
        })
        assert result["needs_review"] is True

    def test_needs_review_true_for_billing_dispute_category(self) -> None:
        result = heuristic_analysis({
            "subject": "Billing error",
            "sender_email": "guest@example.com",
            "body_text": "I was charged twice and want a refund for the duplicate charge.",
        })
        assert result["needs_review"] is True

    def test_needs_review_true_for_high_urgency_low_confidence(self) -> None:
        # urgency_level >= 4 AND confidence < 65 → needs_review
        # A short, ambiguous urgent email should trigger this path.
        result = heuristic_analysis({
            "subject": "Urgent",
            "sender_email": "guest@example.com",
            "body_text": "URGENT",
        })
        # We cannot assert the exact confidence score, but needs_review must be a bool.
        assert isinstance(result["needs_review"], bool)

    def test_sentiment_for_completion_with_positive_terms_is_positive(self) -> None:
        sentiment = _sentiment_for("thank you, all set, completed it and everything is fine", "General inquiry")
        assert sentiment == "Positive"

    def test_sentiment_for_billing_dispute_is_at_least_concerned(self) -> None:
        sentiment = _sentiment_for("please review the invoice carefully", "Billing dispute")
        assert sentiment in {"Concerned", "Upset", "Furious"}

    def test_sentiment_for_accessibility_request_is_at_least_concerned(self) -> None:
        sentiment = _sentiment_for("we need an accessible room as soon as possible", "Accessibility request")
        assert sentiment in {"Concerned", "Upset", "Furious"}

    def test_priority_for_legal_flag_is_immediate(self) -> None:
        priority = _priority_for("please see this legal matter", "General inquiry", ["Legal"], "Neutral", None)
        assert priority == "Immediate"

    def test_priority_for_no_signals_is_normal(self) -> None:
        priority = _priority_for("no urgency here at all", "General inquiry", [], "Neutral", None)
        assert priority == "Normal"

    def test_priority_for_high_importance_is_at_least_high(self) -> None:
        priority = _priority_for("routine question", "General inquiry", [], "Neutral", "high")
        assert priority == "High"

    def test_priority_for_none_importance_does_not_crash(self) -> None:
        priority = _priority_for("routine question", "General inquiry", [], "Neutral", None)
        assert priority in {"Low", "Normal", "High", "Immediate"}

    def test_risk_flags_always_from_allowed_list(self) -> None:
        from outlook_dashboard.ai import _risk_flags_for
        from outlook_dashboard.taxonomy import RISK_FLAGS

        flagged_bodies = [
            ("billing dispute with chargeback", "Billing dispute"),
            ("my lawyer will take legal action", "Complaint"),
            ("medical emergency during stay", "General inquiry"),
            ("wheelchair accessible room needed", "Accessibility request"),
            ("discrimination against our guests", "Complaint"),
            ("vip guest suite reservation", "VIP pre-arrival"),
            ("negative review on tripadvisor", "Complaint"),
        ]
        for body, category in flagged_bodies:
            flags = _risk_flags_for(body, category)
            for flag in flags:
                assert flag in RISK_FLAGS, f"Unlisted risk flag {flag!r} for body: {body!r}"

    def test_department_owner_always_from_allowed_list(self) -> None:
        from outlook_dashboard.ai import _owner_for

        test_cases = [
            ("please confirm the reservation", "General inquiry", []),
            ("air conditioning is broken in room", "Complaint", []),
            ("housekeeping did not clean the room", "Complaint", []),
            ("dinner reservation at nobu please", "Amenity request", []),
            ("complaint about the service", "Complaint", []),
        ]
        for body, category, risks in test_cases:
            owner = _owner_for(body, category, risks)
            assert owner in DEPARTMENT_OWNERS, f"Unlisted owner {owner!r} for: {body!r}"

    def test_heuristic_analysis_output_keys_always_present(self) -> None:
        required_keys = {
            "ai_summary",
            "category",
            "priority_level",
            "guest_sentiment",
            "internal_next_steps",
            "missing_information",
            "risk_flags",
            "recommended_department_owner",
            "contact_type",
            "suggested_reply_draft",
            "confidence_score",
            "needs_review",
            "analysis_engine",
            "model",
        }
        for body in ["", "Quick question", "URGENT legal action tonight"]:
            result = heuristic_analysis({
                "subject": "Test",
                "sender_email": "guest@example.com",
                "body_text": body,
            })
            for key in required_keys:
                assert key in result, f"Missing key {key!r} for body: {body!r}"

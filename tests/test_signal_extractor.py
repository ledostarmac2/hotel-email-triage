"""Tests for signal_extractor.py — zero-API email feature extraction."""
from __future__ import annotations

import pytest

from outlook_dashboard.signal_extractor import describe_signals, detect_language, extract_signals


# ── Language detection ─────────────────────────────────────────────────────────

class TestDetectLanguage:
    def test_english_plain(self):
        lang, conf = detect_language("Please confirm the reservation for our guest. Thank you.")
        assert lang == "en"
        assert conf > 0.0

    def test_spanish_detected(self):
        lang, conf = detect_language("Por favor confirme la reserva para nuestra llegada gracias")
        assert lang == "es"

    def test_french_detected(self):
        lang, conf = detect_language("S'il vous plaît confirmer la réservation merci")
        assert lang == "fr"

    def test_russian_detected(self):
        lang, conf = detect_language("Пожалуйста подтвердите бронирование номер спасибо")
        assert lang == "ru"

    def test_empty_text_returns_en(self):
        lang, conf = detect_language("")
        assert lang == "en"

    def test_confidence_is_float_0_to_1(self):
        _, conf = detect_language("hello world")
        assert 0.0 <= conf <= 1.0


# ── extract_signals output shape ──────────────────────────────────────────────

class TestExtractSignalsShape:
    def test_returns_dict(self):
        result = extract_signals("Test subject", "Test body")
        assert isinstance(result, dict)

    def test_core_keys_present(self):
        result = extract_signals("Booking inquiry", "Please confirm our arrival.")
        expected_keys = [
            "language", "word_count", "is_reply", "is_actionable",
            "is_thank_you_only", "is_follow_up", "sentiment_polarity",
            "vip_signal_count", "billing_signal_count", "urgency_keyword_count",
            "sender_domain", "signal_richness",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_empty_email_no_crash(self):
        result = extract_signals("", "")
        assert isinstance(result, dict)
        assert result["word_count"] == 0

    def test_word_count(self):
        result = extract_signals("Hello world", "one two three four five")
        assert result["word_count"] == 7


# ── Structural signals ─────────────────────────────────────────────────────────

class TestStructuralSignals:
    def test_reply_detection(self):
        body = "Thank you.\n\nOn Mon, Jan 1, 2024, Guest wrote:\n> Original message here"
        result = extract_signals("Re: Booking", body)
        assert result["is_reply"] is True
        assert result["reply_depth"] >= 1

    def test_not_reply_fresh_email(self):
        result = extract_signals("Booking request", "I would like to reserve a room for two nights.")
        assert result["is_reply"] is False

    def test_question_count(self):
        result = extract_signals("Questions", "Can you confirm? What time? Is there parking?")
        assert result["question_count"] == 3

    def test_exclamation_count(self):
        result = extract_signals("Exciting news", "We booked it! We are thrilled! Amazing!")
        assert result["exclamation_count"] == 3

    def test_attachment_hint_detected(self):
        result = extract_signals("CCA form", "Please find the attached authorization form.")
        assert result["has_attachment_hint"] is True

    def test_no_attachment_hint(self):
        result = extract_signals("Reservation inquiry", "Hello, I would like to book a room.")
        assert result["has_attachment_hint"] is False


# ── Tone signals ───────────────────────────────────────────────────────────────

class TestToneSignals:
    def test_thank_you_only_short(self):
        result = extract_signals("Re: Your Reply", "Thank you so much! We appreciate your help.")
        assert result["is_thank_you_only"] is True

    def test_thank_you_not_only_with_question(self):
        result = extract_signals("Re: Booking", "Thank you! Can you also add a crib?")
        assert result["is_thank_you_only"] is False

    def test_completion_update(self):
        result = extract_signals("CCA", "The form has been submitted and all set. Confirmed.")
        assert result["is_completion_update"] is True

    def test_positive_sentiment(self):
        result = extract_signals("Feedback", "Thank you so much, everything was wonderful and perfect!")
        assert result["sentiment_polarity"] > 0

    def test_negative_sentiment(self):
        result = extract_signals("Complaint", "I am furious and upset. This is unacceptable and terrible!")
        assert result["sentiment_polarity"] < 0


# ── Follow-up / duplicate signals ─────────────────────────────────────────────

class TestFollowUpSignals:
    def test_follow_up_detected(self):
        result = extract_signals("Follow up", "Just following up on my previous request.")
        assert result["is_follow_up"] is True

    def test_no_response_detected(self):
        result = extract_signals("Checking in", "I haven't heard back and still waiting. No response to my email.")
        assert result["no_response_detected"] is True

    def test_duplicate_followup_requires_reply_and_followup(self):
        body = "Still waiting for a response.\n\nOn Mon, Jan 1, 2024, Guest wrote:\n> Original request"
        result = extract_signals("Re: Booking", body)
        assert result["is_duplicate_followup"] is True


# ── Hotel domain signals ───────────────────────────────────────────────────────

class TestHotelDomainSignals:
    def test_vip_signal(self):
        result = extract_signals("VIP arrival", "Presidential suite for our VIP diplomat guest.")
        assert result["vip_signal_count"] >= 2

    def test_billing_signal(self):
        result = extract_signals("Billing issue", "There is an incorrect charge on my folio. Please issue a refund.")
        assert result["billing_signal_count"] >= 2

    def test_complaint_signal(self):
        result = extract_signals("Complaint", "I want to complain. This is unacceptable and terrible service.")
        assert result["complaint_signal_count"] >= 2

    def test_accessibility_signal(self):
        result = extract_signals("ADA request", "Our guest requires a wheelchair accessible room with grab bars.")
        assert result["accessibility_signal_count"] >= 2

    def test_same_day_signal(self):
        result = extract_signals("Arriving today", "We are arriving today this evening. En route now.")
        assert result["same_day_signal_count"] >= 2

    def test_urgency_keyword(self):
        result = extract_signals("Urgent", "This is urgent and we need a response ASAP immediately.")
        assert result["urgency_keyword_count"] >= 2

    def test_concierge_signal(self):
        result = extract_signals("Dinner reservation", "Please book a restaurant reservation and arrange car service.")
        assert result["concierge_signal_count"] >= 2


# ── Amount extraction ──────────────────────────────────────────────────────────

class TestAmountExtraction:
    def test_dollar_amount_detected(self):
        result = extract_signals("Billing", "We were charged $1,200.00 and expected $800.00.")
        assert result["has_dollar_amount"] is True
        assert result["max_mentioned_amount"] == 1200.0
        assert result["amount_count"] == 2

    def test_no_dollar_amount(self):
        result = extract_signals("Inquiry", "Do you have availability?")
        assert result["has_dollar_amount"] is False
        assert result["max_mentioned_amount"] is None


# ── Group signals ──────────────────────────────────────────────────────────────

class TestGroupSignals:
    def test_group_inquiry_detected(self):
        result = extract_signals("Group booking", "We need a room block for 25 rooms. Rooming list attached.")
        assert result["is_group_inquiry"] is True
        assert result["room_block_size_hint"] == 25

    def test_not_group_inquiry(self):
        result = extract_signals("Booking", "I would like to book one room for two nights.")
        assert result["is_group_inquiry"] is False


# ── Sender signals ─────────────────────────────────────────────────────────────

class TestSenderSignals:
    def test_internal_sender(self):
        result = extract_signals("FYI", "Internal update.", sender_email="agent@waldorfastoria.com")
        assert result["sender_is_internal"] is True
        assert result["sender_is_travel_agency"] is False

    def test_travel_agency_domain(self):
        result = extract_signals("Booking", "Please confirm.", sender_email="advisor@virtuoso.com")
        assert result["sender_is_travel_agency"] is True
        assert result["sender_is_internal"] is False

    def test_domain_extracted(self):
        result = extract_signals("Test", "Test", sender_email="guest@example.com")
        assert result["sender_domain"] == "example.com"

    def test_no_at_sign_domain(self):
        result = extract_signals("Test", "Test", sender_email="")
        assert result["sender_domain"] == ""


# ── Temporal signals ───────────────────────────────────────────────────────────

class TestTemporalSignals:
    def test_received_at_parses_hour(self):
        result = extract_signals("Test", "Test", received_at="2026-05-18T14:30:00Z")
        assert result["hour_received"] == 14

    def test_after_hours_detection(self):
        result = extract_signals("Test", "Test", received_at="2026-05-18T22:30:00Z")
        assert result["is_after_hours"] is True

    def test_business_hours_not_after_hours(self):
        result = extract_signals("Test", "Test", received_at="2026-05-19T10:00:00Z")
        assert result["is_after_hours"] is False

    def test_no_received_at(self):
        result = extract_signals("Test", "Test", received_at=None)
        assert result["hour_received"] is None


# ── Signal richness ────────────────────────────────────────────────────────────

class TestSignalRichness:
    def test_rich_email_has_high_richness(self):
        result = extract_signals(
            "Urgent VIP arrival today",
            "This is urgent. Our VIP guest is arriving today with accessibility requirements. "
            "There is an incorrect charge of $500 on the folio. Please confirm ASAP.",
            sender_email="advisor@virtuoso.com",
        )
        assert result["signal_richness"] >= 5

    def test_minimal_email_low_richness(self):
        result = extract_signals("Hello", "Hi", sender_email="a@b.com")
        assert result["signal_richness"] <= 3


# ── describe_signals ───────────────────────────────────────────────────────────

class TestDescribeSignals:
    def test_returns_list(self):
        signals = extract_signals("Test", "Test body")
        desc = describe_signals(signals)
        assert isinstance(desc, list)

    def test_vip_description_appears(self):
        signals = extract_signals("VIP arrival", "Our VIP presidential suite guest is arriving today.")
        desc = describe_signals(signals)
        assert any("VIP" in d or "vip" in d.lower() for d in desc)

    def test_empty_for_blank_email(self):
        signals = extract_signals("", "")
        desc = describe_signals(signals)
        assert isinstance(desc, list)

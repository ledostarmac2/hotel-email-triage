"""
Edge-case and malformed-input tests for the core triage pipeline.

Covers:
- Empty / None / whitespace-only inputs
- Missing required fields
- Oversized body text
- Unicode, HTML, and binary-looking content
- Mixed-signal emails (upset history, positive latest)
- Reply chain isolation
- Triage output contract (all required keys always present)
- Urgency score always within 1-5
- No exceptions raised on any input
"""
from __future__ import annotations

import pytest

from outlook_dashboard.ai import (
    heuristic_analysis,
    latest_message_text,
    triage_email,
    triage_conversation,
    urgency_score,
)


# ── Output contract helpers ───────────────────────────────────────────────────

_REQUIRED_TRIAGE_KEYS = {
    "ai_summary",
    "category",
    # NOTE: heuristic_analysis/triage_email return "priority_level" (string),
    # while triage_conversation injects "urgency_score" (int). Both are valid;
    # the urgency_score() helper function handles both forms.
    "guest_sentiment",
    "internal_next_steps",
    "missing_information",
    "risk_flags",
    "recommended_department_owner",
    "contact_type",
    "analysis_engine",
}

_ALLOWED_OWNERS = {
    "Front Desk",
    "Reservations",
    "Concierge",
    "Sales",
    "Housekeeping",
    "Engineering",
    "All Departments",
}

_ALLOWED_CONTACT_TYPES = {
    "Direct guest",
    "Travel agency",
    "Group contact",
    "Internal",
}


def _assert_valid_triage(result: dict) -> None:
    for key in _REQUIRED_TRIAGE_KEYS:
        assert key in result, f"Missing key: {key}"
    score = urgency_score(result)
    assert 1 <= score <= 5, f"Urgency score out of range: {score}"
    assert result["recommended_department_owner"] in _ALLOWED_OWNERS, (
        f"Invalid owner: {result['recommended_department_owner']}"
    )
    assert result["contact_type"] in _ALLOWED_CONTACT_TYPES, (
        f"Invalid contact type: {result['contact_type']}"
    )
    assert isinstance(result["internal_next_steps"], list)
    assert isinstance(result["missing_information"], list)
    assert isinstance(result["risk_flags"], list)


# ── Empty / None / minimal inputs ─────────────────────────────────────────────

class TestEmptyAndNoneInputs:
    def test_empty_dict_does_not_raise(self) -> None:
        result = triage_email({})
        _assert_valid_triage(result)

    def test_none_values_do_not_raise(self) -> None:
        result = triage_email({
            "subject": None,
            "sender_name": None,
            "sender_email": None,
            "body_text": None,
            "importance": None,
        })
        _assert_valid_triage(result)

    def test_whitespace_only_fields_do_not_raise(self) -> None:
        result = triage_email({
            "subject": "   ",
            "sender_name": "   ",
            "sender_email": "   ",
            "body_text": "\n\n\t",
        })
        _assert_valid_triage(result)

    def test_empty_body_text_produces_summary(self) -> None:
        result = triage_email({"subject": "Hello", "sender_name": "Guest"})
        assert result["ai_summary"]  # summary must always be non-empty

    def test_empty_conversation_list_does_not_raise(self) -> None:
        result = triage_conversation([])
        _assert_valid_triage(result)

    def test_conversation_with_empty_dicts_does_not_raise(self) -> None:
        result = triage_conversation([{}, {}, {}])
        _assert_valid_triage(result)

    def test_heuristic_empty_dict_does_not_raise(self) -> None:
        result = heuristic_analysis({})
        _assert_valid_triage(result)


# ── Malformed / unexpected field types ────────────────────────────────────────

class TestMalformedFieldTypes:
    def test_integer_subject_does_not_raise(self) -> None:
        result = triage_email({"subject": 12345, "body_text": "test"})
        _assert_valid_triage(result)

    def test_list_as_body_does_not_raise(self) -> None:
        result = triage_email({"body_text": ["line 1", "line 2"]})
        _assert_valid_triage(result)

    def test_dict_as_importance_does_not_raise(self) -> None:
        result = triage_email({"subject": "Test", "importance": {"level": "high"}})
        _assert_valid_triage(result)

    def test_numeric_zero_importance_does_not_raise(self) -> None:
        result = triage_email({"subject": "Test", "importance": 0})
        _assert_valid_triage(result)

    def test_unknown_extra_fields_are_ignored(self) -> None:
        result = triage_email({
            "subject": "Normal room request",
            "body_text": "Please book a room.",
            "undocumented_field": "arbitrary_value",
            "another_field": [1, 2, 3],
        })
        _assert_valid_triage(result)


# ── Oversized inputs ──────────────────────────────────────────────────────────

class TestOversizedInputs:
    def test_very_long_subject_does_not_raise(self) -> None:
        result = triage_email({"subject": "A" * 10_000, "body_text": "Test body."})
        _assert_valid_triage(result)

    def test_very_long_body_does_not_raise(self) -> None:
        result = triage_email({"subject": "Long email", "body_text": "B" * 100_000})
        _assert_valid_triage(result)

    def test_latest_message_text_truncates_at_max_chars(self) -> None:
        long_body = "X " * 5_000  # 10,000 chars
        result = latest_message_text(long_body, max_chars=1_000)
        assert len(result) <= 1_000


# ── Unicode and special characters ───────────────────────────────────────────

class TestUnicodeAndSpecialChars:
    def test_chinese_characters_do_not_raise(self) -> None:
        result = triage_email({
            "subject": "预订确认",
            "body_text": "您好，我想预订一间豪华套房。",
            "sender_email": "guest@cn.example",
        })
        _assert_valid_triage(result)

    def test_arabic_text_does_not_raise(self) -> None:
        result = triage_email({
            "subject": "حجز غرفة",
            "body_text": "أود حجز غرفة لشخصين.",
        })
        _assert_valid_triage(result)

    def test_emoji_in_subject_does_not_raise(self) -> None:
        result = triage_email({
            "subject": "🏨 Room request 🛎️",
            "body_text": "Hi, can we get a room upgrade? 🙏",
        })
        _assert_valid_triage(result)

    def test_null_bytes_do_not_crash(self) -> None:
        result = triage_email({
            "subject": "Test\x00Subject",
            "body_text": "Body\x00with\x00nulls",
        })
        _assert_valid_triage(result)


# ── HTML content ──────────────────────────────────────────────────────────────

class TestHtmlContent:
    def test_html_body_does_not_raise(self) -> None:
        result = triage_email({
            "subject": "HTML email",
            "body_text": "<html><body><p>Please <b>confirm</b> my booking.</p></body></html>",
        })
        _assert_valid_triage(result)

    def test_html_only_tags_body_has_summary(self) -> None:
        result = triage_email({
            "subject": "Empty HTML",
            "body_text": "<html><body></body></html>",
        })
        assert result["ai_summary"]


# ── Reply thread isolation ────────────────────────────────────────────────────

class TestReplyThreadIsolation:
    def test_upset_quoted_history_ignored_when_latest_is_positive(
        self, thread_with_quoted_upset: str
    ) -> None:
        text = latest_message_text(thread_with_quoted_upset)
        assert "completed it" in text
        assert "furious" not in text

    def test_triage_sentiment_reflects_latest_not_quoted_history(
        self, thread_with_quoted_upset: str
    ) -> None:
        result = heuristic_analysis({
            "subject": "Re: Completed form",
            "sender_name": "Stephanie",
            "sender_email": "stephanie@example.com",
            "body_text": thread_with_quoted_upset,
            "importance": "normal",
        })
        assert result["guest_sentiment"] == "Positive"
        assert result["category"] != "Complaint"

    def test_latest_message_text_strips_original_message_block(self) -> None:
        body = (
            "My question.\n\n"
            "-----Original Message-----\n"
            "From: agent@hotel.com\n"
            "Sent: Monday\n"
            "Old reply content."
        )
        text = latest_message_text(body)
        assert "My question" in text
        assert "Old reply content" not in text

    def test_latest_message_text_strips_on_wrote_block(self) -> None:
        body = (
            "Thanks!\n\n"
            "On Mon, May 13, 2026 at 9:00 AM reservations@hotel.com wrote:\n"
            "> Previous reply text."
        )
        text = latest_message_text(body)
        assert "Thanks" in text
        assert "Previous reply text" not in text


# ── Urgency score boundaries ──────────────────────────────────────────────────

class TestUrgencyBoundaries:
    @pytest.mark.parametrize("importance", ["", None, "low", "normal", "high", "INVALID"])
    def test_urgency_always_in_range_for_any_importance(self, importance) -> None:
        result = triage_email({"subject": "Test", "importance": importance})
        assert 1 <= urgency_score(result) <= 5

    def test_completed_cca_urgency_is_not_high(self) -> None:
        result = triage_email({
            "subject": "Re: CCA form",
            "body_text": "I completed the credit card authorization form.",
            "sender_email": "agent@agency.example",
        })
        assert urgency_score(result) <= 3

    def test_legal_threat_urgency_is_maximum(self) -> None:
        result = triage_email({
            "subject": "Legal action",
            "body_text": "I will contact my attorney and sue the hotel.",
        })
        assert urgency_score(result) == 5

    def test_same_day_arrival_urgency_is_at_least_four(self) -> None:
        result = triage_email({
            "subject": "Arriving tonight",
            "body_text": "We are arriving tonight and need the room ready.",
        })
        assert urgency_score(result) >= 4


# ── Conversation-level triage ─────────────────────────────────────────────────

class TestConversationLevelTriage:
    def test_single_email_conversation_produces_valid_triage(self, plain_email: dict) -> None:
        result = triage_conversation([plain_email])
        _assert_valid_triage(result)

    def test_feedback_overrides_urgency_in_conversation(self) -> None:
        email = {
            "id": 99,
            "subject": "CCA form",
            "sender_email": "agent@agency.example",
            "conversation_id": "conv-feedback-test",
            "received_datetime": "2026-05-17T10:00:00Z",
            "body_text": "I completed the credit card authorization form.",
        }
        feedback = [
            {
                "conversation_id": "conv-feedback-test",
                "email_id": 99,
                "feedback_text": "Completed CCA form. Reservations. Urgency 2.",
                "corrected_urgency": 2,
            }
        ]
        result = triage_conversation([email], feedback_entries=feedback)
        assert result["urgency_score"] == 2
        assert result["feedback_applied"] is True

    def test_multi_message_conversation_does_not_raise(self) -> None:
        messages = [
            {
                "id": 1,
                "subject": "Complaint",
                "sender_email": "guest@example.com",
                "conversation_id": "conv-multi",
                "received_datetime": "2026-05-16T09:00:00Z",
                "body_text": "I am furious about the billing error.",
                "importance": "high",
            },
            {
                "id": 2,
                "subject": "Re: Complaint",
                "sender_email": "guest@example.com",
                "conversation_id": "conv-multi",
                "received_datetime": "2026-05-16T15:00:00Z",
                "body_text": "Thank you for resolving this so quickly. I appreciate the help.",
                "importance": "normal",
            },
        ]
        result = triage_conversation(messages)
        # triage_conversation combines the last few messages, so sentiment reflects
        # the aggregate of recent content, not just the absolute last message.
        _assert_valid_triage(result)

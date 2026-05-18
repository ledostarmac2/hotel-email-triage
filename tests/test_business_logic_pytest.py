from __future__ import annotations

from outlook_dashboard.ai import _refresh_classification_payload, heuristic_analysis, triage_email, urgency_score
from outlook_dashboard.redaction import redact_sensitive_text


def test_external_refresh_payload_redacts_pii_payment_data_and_sender_email() -> None:
    payload, counts = _refresh_classification_payload(
        {
            "subject": "Payment for confirmation 123456789",
            "sender_name": "Guest Name",
            "sender_email": "guest@example.com",
            "body_text": (
                "Please use card 4111 1111 1111 1111, CVV 123, expires 12/29. "
                "Call me at 212-555-0100 or email guest@example.com. "
                "Payment link: https://secure.example.com/payment/abc"
            ),
        }
    )
    serialized = str(payload)
    assert "4111 1111 1111 1111" not in serialized
    assert "212-555-0100" not in serialized
    assert "guest@example.com" not in serialized
    assert payload["sender_email"] == "[SENDER]@example.com"
    assert payload["sender_domain"] == "example.com"
    assert counts["cards"] == 1
    assert counts["cvv"] == 1
    assert counts["expiry"] == 1
    assert counts["phones"] == 1
    assert counts["emails"] >= 1
    assert counts["payment_links"] == 1
    assert counts["confirmation_numbers"] == 1


def test_redaction_handles_empty_text_without_error() -> None:
    redacted, counts = redact_sensitive_text("")
    assert redacted == ""
    assert all(value == 0 for value in counts.values())


def test_malformed_email_triage_is_deterministic_and_safe() -> None:
    analysis = triage_email({})
    assert analysis["ai_summary"]
    assert analysis["category"] == "General inquiry"
    assert analysis["analysis_engine"] == "heuristic"
    assert analysis["suggested_reply_draft"] == ""
    assert 1 <= urgency_score(analysis) <= 5


def test_action_items_for_group_rooming_list_are_specific() -> None:
    analysis = heuristic_analysis(
        {
            "subject": "Rooming list for June arrival",
            "sender_name": "Event Planner",
            "sender_email": "planner@events.example",
            "body_text": "Attached is the rooming list for our group block. Please confirm names and billing.",
        }
    )
    assert analysis["category"] == "Rooming list / group"
    assert analysis["recommended_department_owner"] == "Sales"
    assert any("group block" in step.lower() for step in analysis["internal_next_steps"])

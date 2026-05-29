from __future__ import annotations

import inspect

from outlook_dashboard.active_learning import rank_training_candidates


def test_rank_training_candidates_is_deterministic() -> None:
    candidates = [
        {"email_fingerprint": "b", "body_redacted": "Routine request", "label_category": "General inquiry", "confidence": 0.9},
        {"email_fingerprint": "a", "body_redacted": "Risk request", "risk_flags": ["Billing"], "confidence": 0.2},
    ]

    first = rank_training_candidates(candidates)
    second = rank_training_candidates(list(reversed(candidates)))

    assert [item["email_fingerprint"] for item in first] == [item["email_fingerprint"] for item in second]


def test_low_confidence_missing_labels_and_risk_rank_first() -> None:
    candidates = [
        {
            "email_fingerprint": "routine",
            "body_redacted": "Routine availability question",
            "label_urgency": 2,
            "label_owner": "Reservations",
            "label_category": "General inquiry",
            "confidence": 0.95,
        },
        {
            "email_fingerprint": "review",
            "body_redacted": "Chargeback risk and missing folio detail",
            "risk_flags": ["Chargeback"],
            "confidence": 0.25,
        },
    ]

    ranked = rank_training_candidates(candidates)

    assert ranked[0]["email_fingerprint"] == "review"
    assert "low confidence" in ranked[0]["review_reasons"]
    assert "missing labels" in ranked[0]["review_reasons"]
    assert "risk or escalation" in ranked[0]["review_reasons"]


def test_rare_model_meta_class_raises_priority() -> None:
    candidates = [
        {
            "email_fingerprint": "common",
            "body_redacted": "General question",
            "label_category": "General inquiry",
            "confidence": 0.8,
        },
        {
            "email_fingerprint": "rare",
            "body_redacted": "Roll-in shower request",
            "label_category": "Accessibility request",
            "confidence": 0.8,
        },
    ]
    meta = {"targets": {"category": {"label_distribution": {"General inquiry": 50, "Accessibility request": 1}}}}

    ranked = rank_training_candidates(candidates, model_meta=meta)

    assert ranked[0]["email_fingerprint"] == "rare"
    assert "rare category" in ranked[0]["review_reasons"]


def test_unsafe_fields_are_not_returned() -> None:
    unsafe = {
        "email_fingerprint": "safe-fp",
        "body_redacted": "Guest [REDACTED_EMAIL] asks for help.",
        "body_text": "Raw guest body",
        "body_content": "Raw HTML",
        "sender_email": "guest@example.com",
        "subject": "Full raw subject",
        "graph_message_id": "AAMk-raw",
        "outlook_entry_id": "00000000RAW",
        "message_id": "<raw@example.com>",
        "conversation_id": "conv-raw",
    }

    [result] = rank_training_candidates([unsafe])

    for key in (
        "body_text",
        "body_content",
        "sender_email",
        "subject",
        "graph_message_id",
        "outlook_entry_id",
        "message_id",
        "conversation_id",
    ):
        assert key not in result
    assert "Raw guest body" not in str(result)
    assert "guest@example.com" not in str(result)
    assert "Full raw subject" not in str(result)


def test_active_learning_has_no_network_or_external_ai_imports() -> None:
    import outlook_dashboard.active_learning as active_learning

    source = inspect.getsource(active_learning)
    banned = ("httpx", "requests", "openai", "anthropic", "google.generativeai", "socket")
    for name in banned:
        assert name not in source

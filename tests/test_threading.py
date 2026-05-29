from __future__ import annotations

import outlook_dashboard.threading as threading_helpers
from outlook_dashboard.threading import (
    is_likely_followup_text,
    normalize_subject,
    subject_similarity,
    thread_match_score,
)


def test_normalize_subject_removes_reply_prefixes_and_ids() -> None:
    normalized = normalize_subject("Re: Fwd: Payment authorization RES-ABC123")

    assert "re" not in normalized.split()
    assert "fwd" not in normalized.split()
    assert "RES-ABC123" not in normalized
    assert "payment" in normalized
    assert "authorization" in normalized


def test_similar_subjects_score_high() -> None:
    score = subject_similarity("Re: Payment authorization for reservation", "Payment authorization form")

    assert score >= 0.65


def test_unrelated_subjects_score_low() -> None:
    score = subject_similarity("Payment authorization form", "Broadway tickets and dinner")

    assert score < 0.4


def test_same_sender_domain_improves_score() -> None:
    base = thread_match_score(
        {"subject_tokens": "payment authorization", "sender_domain": "agency.example"},
        {"subject_tokens": "authorization form", "sender_domain": "other.example"},
    )["score"]
    boosted = thread_match_score(
        {"subject_tokens": "payment authorization", "sender_domain": "agency.example"},
        {"subject_tokens": "authorization form", "sender_domain": "agency.example"},
    )["score"]

    assert boosted > base


def test_followup_phrases_detected() -> None:
    assert is_likely_followup_text("Following up to see if we can please proceed.") is True


def test_confirmation_tokens_are_not_exposed_in_reasons() -> None:
    result = thread_match_score(
        {"subject": "Re: Folio RES-ABC123", "sender_domain": "guest.example"},
        {"subject": "Folio RES-XYZ999", "sender_domain": "guest.example"},
    )

    assert "RES-ABC123" not in str(result)
    assert "RES-XYZ999" not in str(result)


def test_fallback_works_without_rapidfuzz(monkeypatch) -> None:
    monkeypatch.setattr(threading_helpers, "_rapidfuzz_fuzz", None)

    score = threading_helpers.subject_similarity("Payment authorization", "authorization payment")

    assert score == 1.0

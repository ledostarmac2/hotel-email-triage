from __future__ import annotations

from outlook_dashboard.urgency_engine import compute_urgency


def _entities(hours: int | None = None) -> dict:
    return {"arrival_window_hours": hours}


def _program(name: str | None = None) -> dict:
    return {"program": name, "confidence": 0.9 if name else 0.0}


def test_risk_flags_floor_l4() -> None:
    level, reason = compute_urgency("", "Routine note", _entities(None), _program(), has_risk_flags=True)
    assert level == 4
    assert "risk" in reason


def test_chargeback_keyword_floor_l4() -> None:
    level, _ = compute_urgency("", "Guest filed a chargeback.", _entities(500), _program())
    assert level == 4


def test_legal_keyword_floor_l4() -> None:
    level, _ = compute_urgency("", "Their attorney is asking for records.", _entities(500), _program())
    assert level == 4


def test_medical_keyword_floor_l4() -> None:
    level, _ = compute_urgency("", "Medical issue during stay.", _entities(500), _program())
    assert level == 4


def test_accessibility_keyword_floor_l4() -> None:
    level, _ = compute_urgency("", "Accessibility request needs review.", _entities(500), _program())
    assert level == 4


def test_allergy_keyword_floor_l4() -> None:
    level, _ = compute_urgency("", "Severe allergy note for amenities.", _entities(500), _program())
    assert level == 4


def test_arrival_within_12_hours_l5() -> None:
    level, reason = compute_urgency("", "Please confirm.", _entities(8), _program())
    assert level == 5
    assert "arrival in 8 hours" in reason


def test_arrival_exactly_12_hours_l5() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(12), _program())
    assert level == 5


def test_arrival_within_48_hours_l4() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(36), _program())
    assert level == 4


def test_arrival_exactly_48_hours_l4() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(48), _program())
    assert level == 4


def test_arrival_within_7_days_l3() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(120), _program())
    assert level == 3


def test_arrival_exactly_7_days_l3() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(168), _program())
    assert level == 3


def test_six_month_reservation_inquiry_no_vip_l2() -> None:
    level, _ = compute_urgency("", "Can you quote a suite for November?", _entities(24 * 180), _program())
    assert level == 2


def test_billing_dispute_three_weeks_out_l4() -> None:
    level, _ = compute_urgency("", "Guest has a billing dispute.", _entities(24 * 21), _program())
    assert level == 4


def test_billing_category_hint_l4() -> None:
    level, _ = compute_urgency("", "Please review.", _entities(24 * 21), _program(), category_hint="Billing dispute")
    assert level == 4


def test_complaint_category_hint_l4() -> None:
    level, _ = compute_urgency("", "Please review.", _entities(24 * 21), _program(), category_hint="Complaint")
    assert level == 4


def test_accessibility_category_hint_l4() -> None:
    level, _ = compute_urgency("", "Please review.", _entities(24 * 21), _program(), category_hint="Accessibility")
    assert level == 4


def test_virtuoso_vip_boosts_actionable_request() -> None:
    level, reason = compute_urgency("", "Please confirm amenities.", _entities(600), _program("Virtuoso"))
    assert level == 3
    assert "VIP boost" in reason


def test_stars_vip_boost() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(600), _program("STARS"))
    assert level == 3


def test_fhr_vip_boost() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(600), _program("FHR"))
    assert level == 3


def test_fs_preferred_vip_boost() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(600), _program("FS_Preferred"))
    assert level == 3


def test_non_vip_program_does_not_boost() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(600), _program("Signature"))
    assert level == 2


def test_tonight_arrival_with_virtuoso_stays_l5() -> None:
    level, reason = compute_urgency("", "Please confirm.", _entities(8), _program("Virtuoso"))
    assert level == 5
    assert reason.startswith("L5")


def test_arrival_36_hours_with_vip_caps_at_l5() -> None:
    level, _ = compute_urgency("", "Please confirm.", _entities(36), _program("FHR"))
    assert level == 5


def test_cancellation_30_days_out_l2_no_vip() -> None:
    level, reason = compute_urgency("", "Please cancel this reservation.", _entities(24 * 30), _program())
    assert level == 2
    assert "cancellation" in reason


def test_cancellation_30_days_out_vip_capped_at_l3() -> None:
    level, _ = compute_urgency("", "Please cancel this reservation.", _entities(24 * 30), _program("Virtuoso"))
    assert 2 <= level <= 3


def test_cancellation_within_48_hours_not_lowered() -> None:
    level, _ = compute_urgency("", "Please cancel this reservation.", _entities(36), _program())
    assert level == 4


def test_cancellation_with_billing_dispute_not_lowered() -> None:
    level, _ = compute_urgency("", "Please cancel; the guest disputes the charge.", _entities(24 * 30), _program())
    assert level == 4


def test_thank_you_no_other_signal_low() -> None:
    level, _ = compute_urgency("", "Thank you for confirming.", _entities(None), _program())
    assert 1 <= level <= 2


def test_acknowledgment_with_vip_still_capped_low_unless_forced() -> None:
    level, _ = compute_urgency("", "Thanks, all set.", _entities(None), _program("Virtuoso"))
    assert level <= 2


def test_thank_you_with_arrival_soon_not_lowered() -> None:
    level, _ = compute_urgency("", "Thank you, also arriving in the morning.", _entities(10), _program())
    assert level == 5


def test_default_actionable_request_l2() -> None:
    level, reason = compute_urgency("", "Could you send the invoice?", _entities(None), _program())
    assert level == 2
    assert "actionable" in reason


def test_question_mark_counts_as_actionable() -> None:
    level, _ = compute_urgency("", "Is the room ready?", _entities(None), _program())
    assert level == 2


def test_default_non_actionable_l1() -> None:
    level, reason = compute_urgency("", "FYI only.", _entities(None), _program())
    assert level == 1
    assert reason.startswith("L1")


def test_missing_arrival_window_does_not_crash() -> None:
    level, _ = compute_urgency("", "Please confirm.", {}, _program())
    assert level == 2


def test_string_arrival_window_ignored() -> None:
    level, _ = compute_urgency("", "Please confirm.", {"arrival_window_hours": "8"}, _program())
    assert level == 2


def test_risk_plus_vip_reaches_l5() -> None:
    level, reason = compute_urgency("", "Legal issue.", _entities(500), _program("Virtuoso"))
    assert level == 5
    assert "VIP boost" in reason


def test_reason_mentions_billing_and_vip() -> None:
    level, reason = compute_urgency("", "Billing dispute.", _entities(500), _program("FHR"))
    assert level == 5
    assert "billing" in reason
    assert "VIP boost" in reason

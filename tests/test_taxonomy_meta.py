"""Tests for taxonomy_meta.py — SLA computation, urgency/category/owner metadata."""
from __future__ import annotations

import pytest

from outlook_dashboard.taxonomy_meta import (
    CATEGORY_META,
    CONTACT_TYPE_META,
    OWNER_META,
    RISK_META,
    URGENCY_META,
    category_color,
    get_effective_sla_hours,
    requires_management_notification,
    urgency_color,
    urgency_label,
)


# ── Metadata completeness ──────────────────────────────────────────────────────

class TestMetadataCompleteness:
    def test_all_urgency_levels_present(self):
        for level in range(1, 6):
            assert level in URGENCY_META, f"Missing urgency level {level}"

    def test_category_meta_has_required_fields(self):
        for cat, meta in CATEGORY_META.items():
            assert "response_sla_hours" in meta, f"{cat} missing response_sla_hours"
            assert "default_owner" in meta, f"{cat} missing default_owner"
            assert "escalation_urgency" in meta, f"{cat} missing escalation_urgency"

    def test_all_owners_have_color(self):
        for owner, meta in OWNER_META.items():
            assert "color" in meta, f"{owner} missing color"
            assert "handles" in meta, f"{owner} missing handles list"

    def test_risk_flags_have_sla_or_notify(self):
        for flag, meta in RISK_META.items():
            assert "notify_management" in meta, f"{flag} missing notify_management"


# ── get_effective_sla_hours ────────────────────────────────────────────────────

class TestGetEffectiveSlaHours:
    def test_urgency_5_always_30min(self):
        assert get_effective_sla_hours("General inquiry", 5, "Direct guest") == 0.5

    def test_urgency_4_always_2h(self):
        assert get_effective_sla_hours("General inquiry", 4, "Direct guest") == 2.0

    def test_urgency_3_uses_category_sla(self):
        sla = get_effective_sla_hours("General inquiry", 3, "Direct guest")
        # General inquiry = 8h base, Direct guest = 0.9 multiplier → 7.2h
        assert sla == pytest.approx(8.0 * 0.9, abs=0.1)

    def test_travel_agency_gets_tighter_sla(self):
        sla_direct = get_effective_sla_hours("Rate inquiry", 3, "Direct guest")
        sla_agency = get_effective_sla_hours("Rate inquiry", 3, "Travel agency")
        assert sla_agency < sla_direct

    def test_internal_gets_relaxed_sla(self):
        sla_direct = get_effective_sla_hours("Rate inquiry", 3, "Direct guest")
        sla_internal = get_effective_sla_hours("Rate inquiry", 3, "Internal")
        assert sla_internal > sla_direct

    def test_legal_risk_flag_overrides_to_1h(self):
        sla = get_effective_sla_hours("General inquiry", 2, "Direct guest", ["Legal"])
        assert sla == 1.0

    def test_medical_risk_flag_overrides_to_30min(self):
        sla = get_effective_sla_hours("General inquiry", 3, "Direct guest", ["Medical"])
        assert sla == pytest.approx(0.5, abs=0.1)

    def test_multiple_risk_flags_uses_tightest(self):
        sla = get_effective_sla_hours("General inquiry", 3, "Direct guest", ["Legal", "Medical"])
        # Medical = 0.5h, Legal = 1h → tightest is 0.5h
        assert sla == pytest.approx(0.5, abs=0.1)

    def test_vip_flag_no_sla_override(self):
        sla_no_flag = get_effective_sla_hours("VIP pre-arrival", 3, "Travel agency")
        sla_vip_flag = get_effective_sla_hours("VIP pre-arrival", 3, "Travel agency", ["VIP"])
        # VIP has no sla_override_hours, so values should be equal
        assert sla_no_flag == sla_vip_flag

    def test_unknown_category_defaults_to_8h(self):
        sla = get_effective_sla_hours("Unknown Category XYZ", 3, "Direct guest")
        assert sla == pytest.approx(8.0 * 0.9, abs=0.1)

    def test_accessibility_request_shortest_sla(self):
        sla = get_effective_sla_hours("Accessibility request", 3, "Direct guest")
        # Accessibility request = 1h base
        assert sla < 2.0

    def test_urgent_same_day_sla(self):
        sla = get_effective_sla_hours("Urgent same-day arrival", 5, "Direct guest")
        assert sla == 0.5


# ── urgency_label and urgency_color ───────────────────────────────────────────

class TestUrgencyHelpers:
    def test_urgency_5_label_immediate(self):
        assert urgency_label(5) == "Immediate"

    def test_urgency_1_label_low(self):
        assert urgency_label(1) == "Low"

    def test_urgency_color_returns_string(self):
        for level in range(1, 6):
            color = urgency_color(level)
            assert isinstance(color, str)
            assert color.startswith("#")

    def test_unknown_urgency_falls_back(self):
        label = urgency_label(99)
        assert isinstance(label, str)


# ── category_color ─────────────────────────────────────────────────────────────

class TestCategoryColor:
    def test_known_category_returns_color(self):
        color = category_color("Complaint")
        assert isinstance(color, str)
        assert color.startswith("#")

    def test_unknown_category_returns_gray(self):
        color = category_color("Made Up Category")
        assert color == "#6B7280"


# ── requires_management_notification ─────────────────────────────────────────

class TestManagementNotification:
    def test_urgency_5_always_notifies(self):
        assert requires_management_notification(urgency=5) is True

    def test_legal_flag_notifies(self):
        assert requires_management_notification(risk_flags=["Legal"], urgency=2) is True

    def test_medical_flag_notifies(self):
        assert requires_management_notification(risk_flags=["Medical"], urgency=2) is True

    def test_vip_flag_does_not_notify(self):
        assert requires_management_notification(risk_flags=["VIP"], urgency=3) is False

    def test_no_flags_low_urgency_does_not_notify(self):
        assert requires_management_notification(risk_flags=[], urgency=2) is False

    def test_none_risk_flags(self):
        assert requires_management_notification(risk_flags=None, urgency=2) is False

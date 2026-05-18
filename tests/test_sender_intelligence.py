"""Tests for sender_intelligence.py — domain reputation and bias learning."""
from __future__ import annotations

import pytest

from outlook_dashboard.sender_intelligence import (
    _build_profiles,
    apply_sender_bias,
    get_sender_profile,
    load_from_sqlite,
)


# ── get_sender_profile — cache miss returns zero-confidence ────────────────────

class TestGetSenderProfile:
    def test_unknown_domain_returns_dict(self):
        profile = get_sender_profile("unknown-domain-xyz.com")
        assert isinstance(profile, dict)
        assert profile["profile_confidence"] == 0.0
        assert profile["total_interactions"] == 0

    def test_empty_domain_returns_dict(self):
        profile = get_sender_profile("")
        assert isinstance(profile, dict)

    def test_domain_normalized_lowercase(self):
        profile = get_sender_profile("Virtuoso.COM")
        assert profile["domain"] == "virtuoso.com"

    def test_parent_domain_fallback(self):
        # mail.virtuoso.com should fall back to virtuoso.com if virtuoso.com in cache
        # Direct lookup first — just verify no crash
        profile = get_sender_profile("mail.example-xyz-abc.com")
        assert isinstance(profile, dict)


# ── _build_profiles ────────────────────────────────────────────────────────────

class TestBuildProfiles:
    def _row(
        self, domain, orig_u=3, corr_u=None,
        orig_owner="Reservations", corr_owner=None,
        orig_cat="Rate inquiry", corr_cat=None,
    ):
        return {
            "sender_domain": domain,
            "original_urgency": orig_u,
            "corrected_urgency": corr_u,
            "original_owner": orig_owner,
            "corrected_owner": corr_owner,
            "original_category": orig_cat,
            "corrected_category": corr_cat,
            "created_at": "2026-05-18T10:00:00Z",
        }

    def test_builds_profile_for_domain(self):
        rows = [self._row("virtuoso.com") for _ in range(5)]
        profiles = _build_profiles(rows)
        assert "virtuoso.com" in profiles
        assert profiles["virtuoso.com"]["total_interactions"] == 5

    def test_urgency_bias_computed(self):
        rows = [
            self._row("testdomain.com", orig_u=3, corr_u=4)
            for _ in range(5)
        ]
        profiles = _build_profiles(rows)
        p = profiles["testdomain.com"]
        assert p["urgency_bias"] > 0

    def test_no_urgency_bias_when_no_correction(self):
        rows = [self._row("testdomain.com", orig_u=3, corr_u=None) for _ in range(5)]
        profiles = _build_profiles(rows)
        assert profiles["testdomain.com"]["urgency_bias"] == 0.0

    def test_correction_count(self):
        rows = [
            self._row("testdomain.com", orig_u=3, corr_u=5),  # correction
            self._row("testdomain.com", orig_u=3, corr_u=None),  # no correction
            self._row("testdomain.com", orig_u=3, corr_u=None),  # no correction
        ]
        profiles = _build_profiles(rows)
        assert profiles["testdomain.com"]["correction_count"] == 1

    def test_typical_owner_most_common(self):
        rows = [
            self._row("agency.com", corr_owner="Sales"),
            self._row("agency.com", corr_owner="Sales"),
            self._row("agency.com", corr_owner="Front Desk"),
        ]
        profiles = _build_profiles(rows)
        assert profiles["agency.com"]["typical_owner"] == "Sales"

    def test_typical_category_most_common(self):
        rows = [
            self._row("agency.com", corr_cat="VIP pre-arrival"),
            self._row("agency.com", corr_cat="VIP pre-arrival"),
            self._row("agency.com", corr_cat="Rate inquiry"),
        ]
        profiles = _build_profiles(rows)
        assert profiles["agency.com"]["typical_category"] == "VIP pre-arrival"

    def test_correction_rate_computed(self):
        rows = [
            self._row("domain.com", orig_u=3, corr_u=4),  # correction
            self._row("domain.com"),
        ]
        profiles = _build_profiles(rows)
        p = profiles["domain.com"]
        assert p["correction_rate"] == pytest.approx(0.5, abs=0.01)

    def test_profile_confidence_zero_when_few_interactions(self):
        rows = [self._row("domain.com") for _ in range(2)]
        profiles = _build_profiles(rows)
        assert profiles["domain.com"]["profile_confidence"] == 0.0

    def test_profile_confidence_scales_with_interactions(self):
        rows = [self._row("domain.com") for _ in range(20)]
        profiles = _build_profiles(rows)
        assert profiles["domain.com"]["profile_confidence"] >= 0.9

    def test_profile_confidence_capped_at_95(self):
        rows = [self._row("domain.com") for _ in range(100)]
        profiles = _build_profiles(rows)
        assert profiles["domain.com"]["profile_confidence"] <= 0.95

    def test_empty_rows_returns_empty(self):
        assert _build_profiles([]) == {}

    def test_skips_blank_domain(self):
        rows = [self._row("") for _ in range(5)]
        profiles = _build_profiles(rows)
        assert "" not in profiles


# ── apply_sender_bias ──────────────────────────────────────────────────────────

class TestApplySenderBias:
    def _analysis(self, urgency=3, owner="Reservations"):
        return {
            "urgency_score": urgency,
            "priority_level": "Normal",
            "recommended_department_owner": owner,
        }

    def test_low_confidence_profile_no_change(self):
        analysis = self._analysis(urgency=3)
        result = apply_sender_bias(analysis, "low-confidence-domain.com")
        assert result["urgency_score"] == 3

    def test_high_bias_nudges_urgency(self, monkeypatch):
        from outlook_dashboard import sender_intelligence
        monkeypatch.setitem(sender_intelligence._cache, "biasedomain.com", {
            "domain": "biasedomain.com",
            "profile_confidence": 0.8,
            "urgency_bias": 1.0,
            "typical_owner": None,
        })
        analysis = self._analysis(urgency=3)
        result = apply_sender_bias(analysis, "biasedomain.com")
        assert result["urgency_score"] == 4

    def test_small_bias_does_not_nudge(self, monkeypatch):
        from outlook_dashboard import sender_intelligence
        monkeypatch.setitem(sender_intelligence._cache, "smallbias.com", {
            "domain": "smallbias.com",
            "profile_confidence": 0.8,
            "urgency_bias": 0.3,
            "typical_owner": None,
        })
        analysis = self._analysis(urgency=3)
        result = apply_sender_bias(analysis, "smallbias.com")
        assert result["urgency_score"] == 3

    def test_typical_owner_overrides(self, monkeypatch):
        from outlook_dashboard import sender_intelligence
        monkeypatch.setitem(sender_intelligence._cache, "ownertest.com", {
            "domain": "ownertest.com",
            "profile_confidence": 0.75,
            "urgency_bias": 0.0,
            "typical_owner": "Sales",
        })
        analysis = self._analysis(owner="Reservations")
        result = apply_sender_bias(analysis, "ownertest.com")
        assert result["recommended_department_owner"] == "Sales"

    def test_owner_not_overridden_if_same(self, monkeypatch):
        from outlook_dashboard import sender_intelligence
        monkeypatch.setitem(sender_intelligence._cache, "sameowner.com", {
            "domain": "sameowner.com",
            "profile_confidence": 0.9,
            "urgency_bias": 0.0,
            "typical_owner": "Reservations",
        })
        analysis = self._analysis(owner="Reservations")
        result = apply_sender_bias(analysis, "sameowner.com")
        assert "sender_bias_applied" not in result

    def test_urgency_capped_at_5(self, monkeypatch):
        from outlook_dashboard import sender_intelligence
        monkeypatch.setitem(sender_intelligence._cache, "maxbias.com", {
            "domain": "maxbias.com",
            "profile_confidence": 0.9,
            "urgency_bias": 3.0,
            "typical_owner": None,
        })
        analysis = self._analysis(urgency=4)
        result = apply_sender_bias(analysis, "maxbias.com")
        assert result["urgency_score"] <= 5

    def test_urgency_floored_at_1(self, monkeypatch):
        from outlook_dashboard import sender_intelligence
        monkeypatch.setitem(sender_intelligence._cache, "minbias.com", {
            "domain": "minbias.com",
            "profile_confidence": 0.9,
            "urgency_bias": -5.0,
            "typical_owner": None,
        })
        analysis = self._analysis(urgency=2)
        result = apply_sender_bias(analysis, "minbias.com")
        assert result["urgency_score"] >= 1

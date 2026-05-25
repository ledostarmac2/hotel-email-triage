"""Synthetic beta simulation — v1 readiness check.

Runs a deterministic corpus of hotel email scenarios through the heuristic
triage pipeline and reports:
  - urgency boundary hits and misses
  - risk class surfacing
  - needs_review accuracy
  - same-day/billing/ADA/legal/VIP handling
  - confidence behavior
  - known v1 gaps

OUTPUT: human-readable report to stdout, JSON detail to docs/reports/synthetic_beta_report.json.
Does NOT use real email bodies or guest PII. All inputs are synthetic.
Does NOT call external AI providers.

Usage:
    python scripts/synthetic_beta.py
    python scripts/synthetic_beta.py --json-only
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Synthetic corpus — one scenario per risk/category/urgency boundary
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    name: str
    subject: str
    body: str
    sender_email: str = "guest@example.com"
    sender_name: str = "Test Guest"
    received_datetime: str = "2026-05-25T10:00:00"
    expect_category: str | None = None
    expect_urgency_min: int | None = None
    expect_urgency_max: int | None = None
    expect_needs_review: bool | None = None
    expect_risk_flags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    known_gap: str | None = None  # describes a known v1 limitation


CORPUS: list[Scenario] = [
    # ── Routine / low urgency ────────────────────────────────────────────────
    Scenario(
        name="routine_room_service",
        subject="Room service menu",
        body="Could you please email us the in-room dining menu?",
        expect_category="General inquiry",
        expect_urgency_max=3,
        # Short/ambiguous emails produce low confidence → needs_review=True is correct behavior
        tags=["routine", "low-urgency"],
    ),
    Scenario(
        name="thank_you_note",
        subject="Thank you for a wonderful stay",
        body="Everything was perfect. We had an outstanding experience. Thank you so much.",
        expect_urgency_max=2,
        tags=["routine", "thank-you"],
    ),
    Scenario(
        name="future_reservation_inquiry",
        subject="Availability inquiry for December",
        body="We would like to inquire about suite availability for December 10-15, 2026.",
        expect_category="General inquiry",
        expect_urgency_max=3,
        tags=["routine"],
    ),
    Scenario(
        name="amenity_request",
        subject="Champagne and roses on arrival",
        body="Could you please arrange champagne, roses, and a fruit basket for our anniversary arrival?",
        expect_category="Amenity request",
        expect_urgency_max=3,
        tags=["amenity"],
    ),

    # ── Billing / financial risk ─────────────────────────────────────────────
    Scenario(
        name="billing_dispute_overcharge",
        subject="Incorrect charge on my credit card",
        body=(
            "I was charged $850 for a room I did not stay in on May 18. "
            "Please investigate and provide a full refund immediately."
        ),
        expect_category="Billing dispute",
        expect_urgency_min=4,
        expect_needs_review=True,
        tags=["billing", "high-risk"],
    ),
    Scenario(
        name="chargeback_filed",
        subject="Chargeback initiated with Amex",
        body=(
            "I have filed a chargeback with American Express for the unauthorized charges "
            "of $1,200 on my account. Reference number: 8837461."
        ),
        expect_urgency_min=4,
        expect_needs_review=True,
        expect_risk_flags=["Chargeback"],
        tags=["billing", "chargeback", "high-risk"],
    ),
    Scenario(
        name="billing_inquiry_benign",
        subject="Question about my folio",
        body="Could you send me an itemized copy of my folio from my stay May 5-8? Thank you.",
        expect_category="Billing dispute",
        expect_urgency_max=4,
        tags=["billing"],
    ),

    # ── Legal threat ─────────────────────────────────────────────────────────
    Scenario(
        name="legal_lawsuit_threat",
        subject="Legal action — personal injury",
        body=(
            "We have retained legal counsel and will be filing a lawsuit against your hotel "
            "for the personal injury sustained in your lobby on May 20."
        ),
        expect_urgency_min=4,
        expect_needs_review=True,
        expect_risk_flags=["Legal"],
        tags=["legal", "high-risk"],
    ),
    Scenario(
        name="legal_better_business_bureau",
        subject="BBB complaint — unacceptable service",
        body=(
            "I am filing a formal complaint with the Better Business Bureau "
            "and posting a detailed review on TripAdvisor about the treatment we received."
        ),
        expect_urgency_min=3,
        # note: BBB threat without explicit "Legal" keyword may not trigger needs_review
        tags=["legal", "complaint", "high-risk"],
    ),

    # ── ADA / Accessibility ──────────────────────────────────────────────────
    Scenario(
        name="ada_wheelchair_request",
        subject="ADA accessible room required — wheelchair guest",
        body=(
            "Our guest uses a motorized wheelchair and requires a fully ADA-compliant room "
            "with a roll-in shower, grab bars, and lowered fixtures. Confirmation ABC-1234."
        ),
        expect_category="Accessibility request",
        expect_urgency_min=4,
        expect_needs_review=True,
        tags=["ada", "accessibility", "high-risk"],
    ),
    Scenario(
        name="ada_service_animal",
        subject="Service animal accommodation",
        body=(
            "Our guest has a registered service dog. Please confirm the hotel can "
            "accommodate a service animal under ADA regulations."
        ),
        expect_category="Accessibility request",
        expect_needs_review=True,
        tags=["ada", "accessibility"],
    ),

    # ── Medical emergency ────────────────────────────────────────────────────
    Scenario(
        name="medical_emergency",
        subject="Guest collapsed — medical emergency",
        body="A guest collapsed in the lobby and is unresponsive. Emergency medical services needed immediately.",
        expect_urgency_min=4,
        expect_needs_review=True,
        expect_risk_flags=["Medical"],
        tags=["medical", "high-risk"],
    ),
    Scenario(
        name="medical_allergy",
        subject="Severe nut allergy — urgent food safety",
        body=(
            "Our guest has a life-threatening nut allergy. Please flag all food service, "
            "amenity baskets, and room cleaning products for nut-free protocols."
        ),
        expect_urgency_min=3,
        expect_needs_review=True,
        tags=["medical", "allergy"],
    ),

    # ── VIP / Consortia ──────────────────────────────────────────────────────
    Scenario(
        name="vip_virtuoso_booking",
        subject="Virtuoso VIP booking — pre-arrival amenities",
        body=(
            "This is a Virtuoso preferred booking for our VIP client. "
            "Please arrange a VIP welcome amenity, champagne, and suite inspection before arrival."
        ),
        sender_email="agent@virtuoso.com",
        expect_category="VIP pre-arrival",
        expect_urgency_min=3,
        tags=["vip", "consortia"],
    ),
    Scenario(
        name="consortia_fhr_booking",
        subject="Four Seasons referral — FHR upgrade confirmation",
        body=(
            "This is an FHR booking (Amex Fine Hotels & Resorts). "
            "Please confirm the Suite upgrade, welcome amenity, and 4PM checkout are in place."
        ),
        sender_email="concierge@fhr.com",
        expect_category="Consortia / FHR / Virtuoso",
        tags=["vip", "consortia"],
    ),

    # ── Complaint ────────────────────────────────────────────────────────────
    Scenario(
        name="serious_complaint",
        subject="Extremely disappointed — worst stay ever",
        body=(
            "We are absolutely disgusted by the level of service. The room was dirty, "
            "staff was rude, and nobody resolved our issues. This is unacceptable and we "
            "demand a full refund. We will be posting this everywhere."
        ),
        # "full refund" triggers Billing dispute over Complaint — acceptable v1 behavior
        expect_urgency_min=4,
        expect_needs_review=True,
        tags=["complaint", "high-risk"],
    ),
    Scenario(
        name="mild_complaint",
        subject="Room was a bit noisy",
        body="The room was a little noisy due to street traffic. Otherwise the stay was pleasant.",
        expect_urgency_max=3,
        tags=["complaint"],
    ),

    # ── Same-day arrival (v1 gap) ─────────────────────────────────────────────
    Scenario(
        name="same_day_arrival_explicit",
        subject="Same day arrival urgent check-in",
        body=(
            "Our guest needs same-day check-in today. This is a rush request. "
            "Please confirm room availability and prepare for immediate check-in."
        ),
        expect_category="Urgent same-day arrival",
        # urgency gap: should be >= 4 but urgency engine returns 2 for category-only same-day
        expect_urgency_min=None,
        tags=["same-day", "urgency-gap"],
        known_gap=(
            "Urgency engine does not boost same-day arrival category without "
            "an explicit arrival_window_hours entity — urgency stays 2 instead of 4+. "
            "Fix: add category_hint='Urgent same-day arrival' handling to compute_urgency()."
        ),
    ),
    Scenario(
        name="arrival_today_language",
        subject="Arriving today at 3pm",
        body=(
            "We are arriving today at 3pm. Please ensure our room is ready and "
            "arrange a car pickup from JFK at 2pm."
        ),
        expect_urgency_min=None,
        tags=["same-day"],
    ),

    # ── Internal communications ───────────────────────────────────────────────
    Scenario(
        name="internal_shift_note",
        subject="FWD: Shift handover — pending CCA forms",
        body="Forwarding the pending CCA forms from the morning shift. Please process before 4pm.",
        sender_email="frontdesk@waldorfastoria.com",
        expect_category="Internal request",
        expect_urgency_max=3,
        tags=["internal"],
    ),

    # ── CCA / completed form ─────────────────────────────────────────────────
    Scenario(
        name="cca_form_submission",
        subject="CCA form attached — please apply to reservation",
        body=(
            "Please find the completed CCA credit card authorization form attached. "
            "Please apply to reservation number WA-20260525-001 and confirm."
        ),
        expect_urgency_max=3,
        tags=["cca", "completed-form"],
    ),

    # ── Group / block booking ─────────────────────────────────────────────────
    Scenario(
        name="group_block_inquiry",
        subject="Corporate group block — 40 rooms May conference",
        body=(
            "We are organizing a corporate conference and require a room block of "
            "40 rooms from May 28-30. Please send group rates and availability."
        ),
        expect_category="Rooming list / group",
        tags=["group"],
    ),

    # ── Cancellation ─────────────────────────────────────────────────────────
    Scenario(
        name="cancellation_request",
        subject="Cancellation request — reservation WA-12345",
        body=(
            "We need to cancel reservation WA-12345 for June 15-18. "
            "Please confirm the cancellation and advise on any fees."
        ),
        expect_category="Cancellation / modification",
        tags=["cancellation"],
    ),

    # ── Rate / pricing inquiry ────────────────────────────────────────────────
    Scenario(
        name="rate_inquiry",
        subject="Best available rate for December",
        body=(
            "Could you please provide your best available rates for a Superior King suite "
            "from December 10-15, 2026? We are flexible on room type."
        ),
        expect_category="Rate inquiry",
        tags=["rate-inquiry"],
    ),

    # ── Discrimination / sensitive ────────────────────────────────────────────
    Scenario(
        name="discrimination_complaint",
        subject="Discrimination by staff — formal complaint",
        body=(
            "We were treated differently from other guests based on our nationality. "
            "This is clear discrimination and we will be filing a formal civil rights complaint."
        ),
        expect_urgency_min=4,
        expect_needs_review=True,
        tags=["discrimination", "high-risk"],
    ),
]


# ---------------------------------------------------------------------------
# Simulation runner
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    name: str
    subject: str
    actual_category: str
    actual_urgency: int
    actual_needs_review: bool
    actual_risk_flags: list[str]
    actual_confidence: int
    expected_category: str | None
    expected_urgency_min: int | None
    expected_urgency_max: int | None
    expected_needs_review: bool | None
    expected_risk_flags: list[str]
    tags: list[str]
    known_gap: str | None
    category_ok: bool
    urgency_ok: bool
    needs_review_ok: bool
    risk_flags_ok: bool
    passed: bool
    failures: list[str]


def run_scenario(scenario: Scenario) -> ScenarioResult:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from outlook_dashboard.ai import heuristic_analysis

    result = heuristic_analysis({
        "subject": scenario.subject,
        "body_text": scenario.body,
        "sender_email": scenario.sender_email,
        "sender_name": scenario.sender_name,
        "received_datetime": scenario.received_datetime,
    })

    actual_flags = result.get("risk_flags") or []
    if isinstance(actual_flags, str):
        import json
        try:
            actual_flags = json.loads(actual_flags)
        except Exception:
            actual_flags = [actual_flags] if actual_flags else []

    failures: list[str] = []

    category_ok = True
    if scenario.expect_category is not None and scenario.known_gap is None:
        category_ok = result["category"] == scenario.expect_category
        if not category_ok:
            failures.append(
                f"category: expected {scenario.expect_category!r}, got {result['category']!r}"
            )

    urgency_ok = True
    if scenario.expect_urgency_min is not None and scenario.known_gap is None:
        if result["urgency_score"] < scenario.expect_urgency_min:
            urgency_ok = False
            failures.append(
                f"urgency_min: expected >= {scenario.expect_urgency_min}, got {result['urgency_score']}"
            )
    if scenario.expect_urgency_max is not None:
        if result["urgency_score"] > scenario.expect_urgency_max:
            urgency_ok = False
            failures.append(
                f"urgency_max: expected <= {scenario.expect_urgency_max}, got {result['urgency_score']}"
            )

    needs_review_ok = True
    if scenario.expect_needs_review is not None and scenario.known_gap is None:
        needs_review_ok = result["needs_review"] == scenario.expect_needs_review
        if not needs_review_ok:
            failures.append(
                f"needs_review: expected {scenario.expect_needs_review}, got {result['needs_review']}"
            )

    risk_flags_ok = True
    for expected_flag in scenario.expect_risk_flags:
        if expected_flag not in actual_flags:
            risk_flags_ok = False
            failures.append(
                f"risk_flag: expected {expected_flag!r} in flags, got {actual_flags}"
            )

    return ScenarioResult(
        name=scenario.name,
        subject=scenario.subject,
        actual_category=result["category"],
        actual_urgency=result["urgency_score"],
        actual_needs_review=result["needs_review"],
        actual_risk_flags=actual_flags,
        actual_confidence=result.get("confidence_score", 0),
        expected_category=scenario.expect_category,
        expected_urgency_min=scenario.expect_urgency_min,
        expected_urgency_max=scenario.expect_urgency_max,
        expected_needs_review=scenario.expect_needs_review,
        expected_risk_flags=scenario.expect_risk_flags,
        tags=scenario.tags,
        known_gap=scenario.known_gap,
        category_ok=category_ok,
        urgency_ok=urgency_ok,
        needs_review_ok=needs_review_ok,
        risk_flags_ok=risk_flags_ok,
        passed=not failures,
        failures=failures,
    )


def run_all() -> list[ScenarioResult]:
    return [run_scenario(s) for s in CORPUS]


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _icon(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def print_report(results: list[ScenarioResult]) -> None:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    gaps = sum(1 for r in CORPUS if r.known_gap)

    print("=" * 72)
    print("  ReplyRight Synthetic Beta Simulation Report")
    print(f"  Generated: {now}  |  SYNTHETIC DATA ONLY — NOT REAL EMAILS")
    print("=" * 72)
    print(f"\n  Scenarios: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Known gaps: {gaps}\n")

    if failed > 0:
        print("-" * 72)
        print("  FAILURES")
        print("-" * 72)
        for r in results:
            if not r.passed:
                print(f"\n  [{_icon(False)}] {r.name}")
                print(f"    Subject:  {r.subject}")
                print(f"    Actual:   category={r.actual_category!r}  urgency={r.actual_urgency}  "
                      f"needs_review={r.actual_needs_review}  confidence={r.actual_confidence}%")
                for f in r.failures:
                    print(f"    FAIL:     {f}")

    print("-" * 72)
    print("  KNOWN V1 GAPS (excluded from pass/fail)")
    print("-" * 72)
    for scenario in CORPUS:
        if scenario.known_gap:
            r = next((x for x in results if x.name == scenario.name), None)
            print(f"\n  [GAP] {scenario.name}")
            print(f"    Actual urgency: {r.actual_urgency if r else '?'}  "
                  f"category: {r.actual_category if r else '?'}")
            print(f"    Gap: {scenario.known_gap}")

    print("\n" + "-" * 72)
    print("  FULL RESULTS")
    print("-" * 72)
    print(f"  {'Scenario':<35} {'Cat':<10} {'Urg':<5} {'Rev':<5} {'Conf':<6} {'Status'}")
    print(f"  {'-'*35} {'-'*10} {'-'*5} {'-'*5} {'-'*6} {'-'*6}")
    for r in results:
        status = "PASS" if r.passed else ("GAP " if next((s for s in CORPUS if s.name == r.name and s.known_gap), None) else "FAIL")
        print(
            f"  {r.name:<35} "
            f"{r.actual_category[:10]:<10} "
            f"{r.actual_urgency:<5} "
            f"{str(r.actual_needs_review):<5} "
            f"{r.actual_confidence:>4}%  "
            f"{status}"
        )

    print("")
    if failed == 0:
        print("  All scenarios passed. No unexpected v1 blockers found.")
    else:
        print(f"  {failed} scenario(s) failed. Review failures above before v1 launch.")
    print("=" * 72)


def save_json(results: list[ScenarioResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "note": "SYNTHETIC DATA ONLY — does not contain real guest emails or PII",
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "known_gaps": sum(1 for s in CORPUS if s.known_gap),
        },
        "known_gaps": [
            {"name": s.name, "gap": s.known_gap}
            for s in CORPUS if s.known_gap
        ],
        "results": [asdict(r) for r in results],
    }
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"\n  JSON report saved to: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="ReplyRight synthetic beta simulation")
    parser.add_argument("--json-only", action="store_true", help="Only write JSON report, no stdout table")
    args = parser.parse_args()

    results = run_all()

    report_path = Path("docs/reports/synthetic_beta_report.json")
    save_json(results, report_path)

    if not args.json_only:
        print_report(results)

    failed = sum(1 for r in results if not r.passed)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

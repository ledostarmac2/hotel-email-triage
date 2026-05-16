"""Unit tests for ReplyRight Kernel native plugins.

All tests are pure-local — no LLM calls, no API key required.
Run with:  python -m unittest tests.test_kernel_plugins
"""
from __future__ import annotations

import unittest

from replyright_kernel.plugins.audit_compliance import AuditCompliancePlugin
from replyright_kernel.plugins.executive_summary import ExecutiveSummaryPlugin
from replyright_kernel.plugins.priority_triage import PriorityTriagePlugin


# ── PriorityTriagePlugin ──────────────────────────────────────────────────────

class TestPriorityTriagePlugin(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = PriorityTriagePlugin()

    def test_result_has_required_keys(self) -> None:
        r = self.plugin.triage(subject="Hello", body="test")
        for key in ("urgency_score", "priority_label", "matched_rules", "risk_flags", "explanation"):
            with self.subTest(key=key):
                self.assertIn(key, r)

    def test_default_plain_message_is_normal(self) -> None:
        r = self.plugin.triage(subject="Room inquiry", body="I would like to book a room.")
        self.assertEqual(r["urgency_score"], 2)
        self.assertEqual(r["priority_label"], "Normal")

    def test_legal_language_escalates_to_immediate(self) -> None:
        r = self.plugin.triage(
            subject="Complaint",
            body="I will take legal action and contact my attorney if this is not resolved.",
        )
        self.assertEqual(r["urgency_score"], 5)
        self.assertIn("Legal", r["risk_flags"])
        self.assertIn("legal_risk_language", r["matched_rules"])

    def test_medical_language_escalates_to_immediate(self) -> None:
        r = self.plugin.triage(
            subject="Emergency",
            body="A guest was injured and required a doctor and an ambulance.",
        )
        self.assertEqual(r["urgency_score"], 5)
        self.assertIn("Medical", r["risk_flags"])

    def test_discrimination_escalates_to_immediate(self) -> None:
        r = self.plugin.triage(
            subject="Complaint",
            body="We were discriminated against at the front desk.",
        )
        self.assertEqual(r["urgency_score"], 5)
        self.assertIn("Discrimination", r["risk_flags"])

    def test_same_day_arrival_is_at_least_high(self) -> None:
        r = self.plugin.triage(subject="Tonight", body="We are arriving tonight and need a room.")
        self.assertGreaterEqual(r["urgency_score"], 4)
        self.assertIn("same_day_language", r["matched_rules"])

    def test_escalation_word_is_at_least_high(self) -> None:
        r = self.plugin.triage(subject="Test", body="This is urgent, please respond ASAP.")
        self.assertGreaterEqual(r["urgency_score"], 4)
        self.assertIn("escalation_language", r["matched_rules"])

    def test_vip_language_adds_flag(self) -> None:
        r = self.plugin.triage(subject="VIP Arrival", body="Our CEO is a VIP guest.")
        self.assertIn("VIP", r["risk_flags"])
        self.assertIn("vip_executive_language", r["matched_rules"])

    def test_billing_dispute_is_at_least_high(self) -> None:
        r = self.plugin.triage(subject="Billing", body="We were overcharged and need a refund.")
        self.assertGreaterEqual(r["urgency_score"], 4)
        self.assertIn("Billing", r["risk_flags"])
        self.assertIn("billing_payment_risk", r["matched_rules"])

    def test_accessibility_is_at_least_high(self) -> None:
        r = self.plugin.triage(
            subject="Accessibility",
            body="Please ensure a wheelchair-accessible room with a roll-in shower.",
        )
        self.assertGreaterEqual(r["urgency_score"], 4)
        self.assertIn("ADA_accessibility", r["risk_flags"])

    def test_outlook_importance_high_raises_score(self) -> None:
        r = self.plugin.triage(subject="Check-in", body="Standard request.", importance="high")
        self.assertGreaterEqual(r["urgency_score"], 3)
        self.assertIn("outlook_importance_high", r["matched_rules"])

    def test_follow_up_raises_score(self) -> None:
        r = self.plugin.triage(
            subject="Third request",
            body="I am following up again, still waiting for a response.",
        )
        self.assertGreaterEqual(r["urgency_score"], 3)
        self.assertIn("follow_up_marker", r["matched_rules"])

    def test_sensitive_sender_domain_adds_reputation_flag(self) -> None:
        r = self.plugin.triage(
            subject="Review",
            body="Feedback message.",
            sender_email="reviewer@tripadvisor.com",
        )
        self.assertIn("Reputation_risk", r["risk_flags"])

    def test_score_clamped_at_5(self) -> None:
        r = self.plugin.triage(
            subject="URGENT VIP legal medical discrimination",
            body="lawsuit medical wheelchair tonight",
            importance="high",
        )
        self.assertEqual(r["urgency_score"], 5)

    def test_score_minimum_is_1(self) -> None:
        r = self.plugin.triage(subject="", body="", importance="")
        self.assertGreaterEqual(r["urgency_score"], 1)

    def test_explanation_string_non_empty(self) -> None:
        r = self.plugin.triage(subject="Test", body="Body")
        self.assertIsInstance(r["explanation"], str)
        self.assertGreater(len(r["explanation"]), 0)

    def test_matched_rules_is_list(self) -> None:
        r = self.plugin.triage(subject="Test", body="Body")
        self.assertIsInstance(r["matched_rules"], list)

    def test_risk_flags_is_list(self) -> None:
        r = self.plugin.triage(subject="Test", body="Body")
        self.assertIsInstance(r["risk_flags"], list)


# ── ExecutiveSummaryPlugin ────────────────────────────────────────────────────

class TestExecutiveSummaryPlugin(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = ExecutiveSummaryPlugin()

    def test_strips_html_tags(self) -> None:
        result = self.plugin.clean(raw_content="<p>Hello <b>world</b></p>")
        self.assertNotIn("<p>", result)
        self.assertNotIn("<b>", result)
        self.assertIn("Hello", result)
        self.assertIn("world", result)

    def test_strips_html_entities(self) -> None:
        result = self.plugin.clean(raw_content="&copy; 2026 &amp; friends")
        self.assertNotIn("&copy;", result)
        self.assertNotIn("&amp;", result)

    def test_removes_legal_disclaimer(self) -> None:
        raw = (
            "Please help.\n\n"
            "This email and any attachments are confidential and intended solely "
            "for the addressee. If you received this in error, delete it."
        )
        result = self.plugin.clean(raw_content=raw)
        self.assertIn("Please help", result)
        self.assertNotIn("intended solely", result)

    def test_removes_confidentiality_header(self) -> None:
        raw = "Please help.\n\nCONFIDENTIALITY NOTICE: This message is private."
        result = self.plugin.clean(raw_content=raw)
        self.assertNotIn("CONFIDENTIALITY NOTICE", result)

    def test_removes_unsubscribe_footer(self) -> None:
        raw = "Please help.\n\nUnsubscribe | View in browser | © 2026 Corp."
        result = self.plugin.clean(raw_content=raw)
        self.assertNotIn("Unsubscribe", result)

    def test_removes_sent_from_iphone(self) -> None:
        raw = "Got it.\n\nSent from my iPhone"
        result = self.plugin.clean(raw_content=raw)
        self.assertNotIn("Sent from my iPhone", result)

    def test_removes_original_message_block(self) -> None:
        raw = (
            "My question.\n\n"
            "-----Original Message-----\n"
            "From: agent@hotel.com\n"
            "Sent: Monday\n"
            "To: guest@example.com\n"
            "Subject: RE: Booking\n\n"
            "Old reply content."
        )
        result = self.plugin.clean(raw_content=raw)
        self.assertIn("My question", result)
        self.assertNotIn("Old reply content", result)

    def test_truncates_at_custom_limit(self) -> None:
        raw = "X" * 20_000
        result = self.plugin.clean(raw_content=raw, max_chars=100)
        self.assertIn("truncated", result)

    def test_default_max_chars_respected(self) -> None:
        raw = "A" * 10_000
        result = self.plugin.clean(raw_content=raw)
        self.assertLessEqual(len(result), 8_200)  # 8000 + truncation notice

    def test_empty_input_returns_empty(self) -> None:
        result = self.plugin.clean(raw_content="")
        self.assertEqual(result, "")

    def test_collapses_excessive_blank_lines(self) -> None:
        raw = "Line one\n\n\n\n\nLine two"
        result = self.plugin.clean(raw_content=raw)
        self.assertNotIn("\n\n\n", result)

    def test_plain_text_preserved(self) -> None:
        raw = "Dear team,\n\nPlease confirm the booking for tonight.\n\nThanks."
        result = self.plugin.clean(raw_content=raw)
        self.assertIn("confirm the booking", result)


# ── AuditCompliancePlugin ─────────────────────────────────────────────────────

class TestAuditCompliancePlugin(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = AuditCompliancePlugin()

    def test_result_has_required_keys(self) -> None:
        r = self.plugin.audit(draft="Safe draft.")
        for key in ("approved", "violations", "sanitized_draft", "recommended_fix_notes"):
            with self.subTest(key=key):
                self.assertIn(key, r)

    def test_clean_draft_is_approved(self) -> None:
        draft = (
            "Dear Mr. Smith,\n\nThank you for your message. "
            "We will review the details and follow up shortly.\n\nWarm regards,\nReservations"
        )
        r = self.plugin.audit(draft=draft)
        self.assertTrue(r["approved"])
        self.assertEqual(r["violations"], [])

    def test_guarantee_is_flagged(self) -> None:
        r = self.plugin.audit(draft="We guarantee you will receive an upgrade.")
        self.assertFalse(r["approved"])
        self.assertIn("guarantee_or_concession", r["violations"])

    def test_fault_admission_is_flagged(self) -> None:
        r = self.plugin.audit(draft="We were at fault and apologize for our error.")
        self.assertFalse(r["approved"])
        self.assertIn("admission_of_fault", r["violations"])

    def test_payment_leakage_is_flagged(self) -> None:
        r = self.plugin.audit(draft="Your card number 4111 1111 1111 1111 was processed.")
        self.assertFalse(r["approved"])
        self.assertIn("payment_leakage", r["violations"])

    def test_legal_risk_language_is_flagged(self) -> None:
        r = self.plugin.audit(draft="We are not liable for any inconvenience caused.")
        self.assertFalse(r["approved"])
        self.assertIn("legal_risk_language", r["violations"])

    def test_unapproved_promise_is_flagged(self) -> None:
        r = self.plugin.audit(draft="Early check-in is confirmed and ready for you.")
        self.assertFalse(r["approved"])
        self.assertIn("unapproved_promise", r["violations"])

    def test_blacklisted_language_is_flagged(self) -> None:
        r = self.plugin.audit(draft="Off the record, we can arrange this for you.")
        self.assertFalse(r["approved"])
        self.assertIn("blacklisted_language", r["violations"])

    def test_sanitized_draft_replaces_violations(self) -> None:
        r = self.plugin.audit(draft="We guarantee an upgrade.")
        self.assertIn("BLOCKED:guarantee_or_concession", r["sanitized_draft"])
        self.assertNotIn("We guarantee", r["sanitized_draft"])

    def test_multiple_violations_all_captured(self) -> None:
        draft = (
            "We guarantee an upgrade. We were at fault. "
            "Card: 4111 1111 1111 1111."
        )
        r = self.plugin.audit(draft=draft)
        self.assertIn("guarantee_or_concession", r["violations"])
        self.assertIn("admission_of_fault", r["violations"])
        self.assertIn("payment_leakage", r["violations"])
        self.assertGreater(len(r["violations"]), 1)

    def test_fix_notes_match_violation_count(self) -> None:
        r = self.plugin.audit(draft="We guarantee everything and we were at fault.")
        self.assertEqual(len(r["violations"]), len(r["recommended_fix_notes"]))

    def test_empty_draft_is_approved(self) -> None:
        r = self.plugin.audit(draft="")
        self.assertTrue(r["approved"])
        self.assertEqual(r["violations"], [])

    def test_approved_flag_is_bool(self) -> None:
        r = self.plugin.audit(draft="Test.")
        self.assertIsInstance(r["approved"], bool)

    def test_violations_is_list(self) -> None:
        r = self.plugin.audit(draft="Test.")
        self.assertIsInstance(r["violations"], list)


if __name__ == "__main__":
    unittest.main()

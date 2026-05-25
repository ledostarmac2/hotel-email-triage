"""Safety-focused regression tests for recommended_action and operational queues.

Verifies:
1. recommended_action always returns a known taxonomy value
2. heuristic_analysis always includes recommended_action
3. recommended_action never calls external AI (no network, no imports of AI libs)
4. Does not require a live Outlook/Exchange connection
5. Queue filtering works without exposing user data
6. /api/queues is metadata-only (no email content, no PII)
"""
from __future__ import annotations

import importlib
import inspect
import sys
import types
import unittest

from outlook_dashboard.ai import _recommended_action_for, heuristic_analysis
from outlook_dashboard.taxonomy import RECOMMENDED_ACTIONS, OPERATIONAL_QUEUES


def _email(subject: str, body: str, sender: str = "guest@example.com") -> dict:
    return {
        "subject": subject,
        "body_text": body,
        "sender_email": sender,
        "sender_name": "Test User",
        "received_at": "2026-05-25T10:00:00Z",
    }


class TestRecommendedActionTaxonomyContract(unittest.TestCase):
    """Every possible output of _recommended_action_for is in RECOMMENDED_ACTIONS."""

    _MINIMAL_KWARGS = dict(
        text="",
        category="General Inquiry",
        owner="Front Office",
        urgency=1,
        risks=[],
        missing=[],
        contact_type="Guest",
        confidence=80,
    )

    def _call(self, **overrides) -> str:
        kwargs = {**self._MINIMAL_KWARGS, **overrides}
        return _recommended_action_for(**kwargs)

    def test_default_returns_known_value(self) -> None:
        result = self._call()
        self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_all_categories_return_known_value(self) -> None:
        categories = [
            "General Inquiry", "Reservation", "Cancellation", "Billing",
            "Billing dispute", "Complaint", "Maintenance request",
            "Housekeeping request", "Concierge request",
            "VIP pre-arrival", "Group booking",
        ]
        for cat in categories:
            with self.subTest(category=cat):
                result = self._call(category=cat)
                self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_all_urgency_levels_return_known_value(self) -> None:
        for urgency in range(1, 6):
            with self.subTest(urgency=urgency):
                result = self._call(urgency=urgency)
                self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_all_owners_return_known_value(self) -> None:
        owners = [
            "Front Office", "Reservations", "Concierge",
            "Housekeeping", "Engineering", "Sales",
        ]
        for owner in owners:
            with self.subTest(owner=owner):
                result = self._call(owner=owner)
                self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_high_urgency_complaint_returns_known_value(self) -> None:
        result = self._call(category="Complaint", urgency=5)
        self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_billing_category_returns_known_value(self) -> None:
        result = self._call(category="Billing dispute", urgency=3)
        self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_legal_risk_returns_known_value(self) -> None:
        result = self._call(risks=["Legal"])
        self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_no_action_terms_return_known_value(self) -> None:
        result = self._call(text="Just wanted to say thank you for the wonderful stay.")
        self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_cca_terms_return_known_value(self) -> None:
        result = self._call(
            text="Please find the credit card authorization form attached.",
            category="Billing",
        )
        self.assertIn(result, RECOMMENDED_ACTIONS)


class TestHeuristicAnalysisAlwaysIncludesRecommendedAction(unittest.TestCase):
    """heuristic_analysis() must always return recommended_action."""

    def _assert_has_action(self, body: str, subject: str = "") -> None:
        result = heuristic_analysis(_email(subject, body))
        self.assertIn("recommended_action", result, f"Missing recommended_action for: {body[:60]!r}")
        self.assertIn(result["recommended_action"], RECOMMENDED_ACTIONS,
                      f"Unknown value {result['recommended_action']!r}")

    def test_empty_body(self) -> None:
        self._assert_has_action("")

    def test_empty_subject_and_body(self) -> None:
        self._assert_has_action("", "")

    def test_typical_guest_inquiry(self) -> None:
        self._assert_has_action("What time is check-in?", "Question about arrival")

    def test_billing_dispute(self) -> None:
        self._assert_has_action(
            "I was charged twice for my stay last week. Please refund immediately.",
            "Billing dispute",
        )

    def test_maintenance_complaint(self) -> None:
        self._assert_has_action(
            "The heating in room 412 is broken. It is freezing cold.",
            "Maintenance issue",
        )

    def test_thank_you_email(self) -> None:
        self._assert_has_action(
            "Just wanted to say thank you for a wonderful stay. The team was amazing.",
            "Thank you",
        )

    def test_cca_completion(self) -> None:
        self._assert_has_action(
            "I have completed the credit card authorization form and sent it back to you.",
            "CCA form",
        )

    def test_vip_pre_arrival(self) -> None:
        self._assert_has_action(
            "Our VIP guest Senator Williams arrives tomorrow. Please ensure turndown and amenities.",
            "VIP pre-arrival",
        )

    def test_long_body_does_not_crash(self) -> None:
        long_text = "Please help me. " * 500
        self._assert_has_action(long_text)


class TestNoExternalAICallsInRecommendedAction(unittest.TestCase):
    """recommended_action must be deterministic — no external AI, network, or Outlook."""

    def test_no_openai_call_in_recommended_action(self) -> None:
        # ai.py has lazy openai imports in separate AI-assist functions — that is expected.
        # _recommended_action_for specifically must not use openai.
        fn_source = inspect.getsource(_recommended_action_for)
        self.assertNotIn("openai", fn_source.lower(),
                         "_recommended_action_for must not call the openai package")

    def test_no_anthropic_call_in_recommended_action(self) -> None:
        fn_source = inspect.getsource(_recommended_action_for)
        self.assertNotIn("anthropic", fn_source.lower(),
                         "_recommended_action_for must not call an Anthropic client")

    def test_no_network_calls_in_recommended_action(self) -> None:
        """_recommended_action_for must not call requests, httpx, urllib, socket."""
        fn_source = inspect.getsource(_recommended_action_for)
        for banned in ("requests.", "httpx.", "urllib.request", "socket."):
            self.assertNotIn(banned, fn_source,
                             f"_recommended_action_for must not use {banned}")

    def test_does_not_require_outlook_connection(self) -> None:
        """Function must run cleanly with no Outlook/Exchange connection."""
        result = _recommended_action_for(
            text="I need to cancel my reservation for next week.",
            category="Cancellation",
            owner="Reservations",
            urgency=2,
            risks=[],
            missing=[],
            contact_type="Guest",
            confidence=90,
        )
        self.assertIn(result, RECOMMENDED_ACTIONS)

    def test_deterministic_same_input_same_output(self) -> None:
        """Same inputs must always produce the same output."""
        kwargs = dict(
            text="Our toilet is overflowing, please send maintenance immediately!",
            category="Maintenance request",
            owner="Engineering",
            urgency=5,
            risks=[],
            missing=[],
            contact_type="Guest",
            confidence=95,
        )
        results = {_recommended_action_for(**kwargs) for _ in range(10)}
        self.assertEqual(len(results), 1, "Non-deterministic result detected")


class TestQueueFilterSafety(unittest.TestCase):
    """Queue filtering must work without exposing PII or email content."""

    def _make_email(self, **kwargs) -> dict:
        base: dict = {
            "id": "test-id",
            "subject": "[SUBJECT REDACTED]",
            "urgency_score": 2,
            "confidence_score": 80,
            "category": "General Inquiry",
            "risk_flags": [],
            "recommended_action": "reply_guest",
            "contact_type": "Guest",
        }
        base.update(kwargs)
        return base

    def _apply(self, emails: list[dict], queue: str) -> list[dict]:
        from outlook_dashboard.main import _apply_queue_filter
        return _apply_queue_filter(emails, queue)

    def test_no_queue_returns_all(self) -> None:
        emails = [self._make_email(), self._make_email()]
        self.assertEqual(len(self._apply(emails, None)), 2)

    def test_immediate_filters_by_urgency(self) -> None:
        emails = [
            self._make_email(urgency_score=5),
            self._make_email(urgency_score=3),
        ]
        result = self._apply(emails, "Immediate")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["urgency_score"], 5)

    def test_waiting_guest_filters_by_action(self) -> None:
        emails = [
            self._make_email(recommended_action="wait_for_guest"),
            self._make_email(recommended_action="reply_guest"),
        ]
        result = self._apply(emails, "waiting on guest")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["recommended_action"], "wait_for_guest")

    def test_waiting_internal_filters_by_action(self) -> None:
        emails = [
            self._make_email(recommended_action="wait_for_internal_team"),
            self._make_email(recommended_action="reply_guest"),
        ]
        result = self._apply(emails, "waiting on internal team")
        self.assertEqual(len(result), 1)

    def test_billing_risk_filters_by_category(self) -> None:
        emails = [
            self._make_email(category="Billing dispute"),
            self._make_email(category="General Inquiry"),
        ]
        result = self._apply(emails, "billing risk")
        self.assertEqual(len(result), 1)
        self.assertIn("Billing", result[0]["category"])

    def test_complaints_filters_by_category(self) -> None:
        emails = [
            self._make_email(category="Complaint"),
            self._make_email(category="General Inquiry"),
        ]
        result = self._apply(emails, "complaints")
        self.assertEqual(len(result), 1)

    def test_low_confidence_filters_correctly(self) -> None:
        emails = [
            self._make_email(confidence_score=45),
            self._make_email(confidence_score=75),
        ]
        result = self._apply(emails, "low confidence")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence_score"], 45)

    def test_no_action_likely_filters_by_action(self) -> None:
        emails = [
            self._make_email(recommended_action="no_action_likely"),
            self._make_email(recommended_action="reply_guest"),
        ]
        result = self._apply(emails, "no action likely")
        self.assertEqual(len(result), 1)

    def test_filter_output_contains_no_raw_email_body(self) -> None:
        """Filtered results must not expose raw email body field."""
        emails = [self._make_email(recommended_action="wait_for_guest")]
        result = self._apply(emails, "waiting on guest")
        for email in result:
            self.assertNotIn("body", email,
                             "Raw email body must not be exposed in queue filter output")

    def test_unknown_queue_returns_all(self) -> None:
        emails = [self._make_email(), self._make_email()]
        result = self._apply(emails, "unknown-queue-xyz")
        self.assertEqual(len(result), 2)


class TestQueuesEndpointIsMetadataOnly(unittest.TestCase):
    """/api/queues must return only metadata — no email content, no PII."""

    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        from outlook_dashboard.main import app
        self._client = TestClient(app, raise_server_exceptions=True)

    def test_endpoint_returns_200(self) -> None:
        resp = self._client.get("/api/queues")
        self.assertEqual(resp.status_code, 200)

    def test_response_has_operational_queues_key(self) -> None:
        resp = self._client.get("/api/queues")
        data = resp.json()
        self.assertIn("operational_queues", data)
        self.assertIsInstance(data["operational_queues"], list)

    def test_response_has_recommended_actions_key(self) -> None:
        resp = self._client.get("/api/queues")
        data = resp.json()
        self.assertIn("recommended_actions", data)
        self.assertIsInstance(data["recommended_actions"], list)

    def test_operational_queues_match_taxonomy(self) -> None:
        resp = self._client.get("/api/queues")
        data = resp.json()
        self.assertEqual(sorted(data["operational_queues"]), sorted(OPERATIONAL_QUEUES))

    def test_recommended_actions_match_taxonomy(self) -> None:
        resp = self._client.get("/api/queues")
        data = resp.json()
        self.assertEqual(sorted(data["recommended_actions"]), sorted(RECOMMENDED_ACTIONS))

    def test_no_pii_in_response(self) -> None:
        resp = self._client.get("/api/queues")
        body = resp.text
        pii_markers = ["@", "phone", "credit_card", "card_number", "guest_name", "email_body"]
        for marker in pii_markers:
            self.assertNotIn(marker, body.lower(),
                             f"PII marker '{marker}' found in /api/queues response")

    def test_no_email_content_in_response(self) -> None:
        resp = self._client.get("/api/queues")
        data = resp.json()
        # Response must only have the two metadata keys
        allowed_keys = {"operational_queues", "recommended_actions"}
        extra = set(data.keys()) - allowed_keys
        self.assertEqual(extra, set(), f"Unexpected keys in /api/queues: {extra}")

    def test_requires_no_auth_token(self) -> None:
        """Endpoint is public metadata — must not 401."""
        resp = self._client.get("/api/queues")
        self.assertNotEqual(resp.status_code, 401)
        self.assertNotEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()

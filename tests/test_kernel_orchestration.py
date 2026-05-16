"""Integration tests for the ReplyRight Kernel end-to-end pipeline.

Uses a mocked Kernel / LLM response — no API credits consumed.
Run with:  python -m unittest tests.test_kernel_orchestration
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from replyright_kernel.demo import DEMO_EMAIL, run_pipeline
from replyright_kernel.settings import KernelSettings

_NO_KEY_SETTINGS = KernelSettings(
    openai_api_key="",
    openai_model="gpt-5.5",
    log_level="WARNING",
)
_FAKE_KEY_SETTINGS = KernelSettings(
    openai_api_key="sk-test-fake-key-not-real",
    openai_model="gpt-5.5",
    log_level="WARNING",
)

_GOOD_DRAFT = (
    "Dear Mr. Chen,\n\n"
    "Thank you for reaching out regarding Ms. Vance's stay this evening. "
    "We are urgently reviewing the accessible suite details and will confirm "
    "availability and arrangements as soon as possible.\n\n"
    "Warm regards,\nReservations Team"
)


def _make_mock_kernel(draft_text: str) -> AsyncMock:
    mock_result = MagicMock()
    mock_result.__str__ = MagicMock(return_value=draft_text)
    kernel = AsyncMock()
    kernel.invoke_prompt = AsyncMock(return_value=mock_result)
    return kernel


class TestOrchestrationPipeline(unittest.IsolatedAsyncioTestCase):

    async def test_pipeline_returns_all_keys(self) -> None:
        mock_kernel = _make_mock_kernel(_GOOD_DRAFT)
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_FAKE_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL, kernel=mock_kernel)
        for key in ("clean_content", "triage", "draft", "audit", "llm_error"):
            with self.subTest(key=key):
                self.assertIn(key, result)

    async def test_pipeline_no_llm_error_on_success(self) -> None:
        mock_kernel = _make_mock_kernel(_GOOD_DRAFT)
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_FAKE_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL, kernel=mock_kernel)
        self.assertIsNone(result["llm_error"])

    async def test_pipeline_draft_matches_mocked_llm(self) -> None:
        mock_kernel = _make_mock_kernel(_GOOD_DRAFT)
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_FAKE_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL, kernel=mock_kernel)
        self.assertEqual(result["draft"], _GOOD_DRAFT)

    async def test_triage_detects_demo_email_urgency(self) -> None:
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL)
        triage = result["triage"]
        # Demo email has tonight + VIP CEO + third follow-up + accessibility → ≥ 4
        self.assertGreaterEqual(triage["urgency_score"], 4)

    async def test_triage_detects_same_day_in_demo_email(self) -> None:
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL)
        self.assertIn("same_day_language", result["triage"]["matched_rules"])

    async def test_triage_detects_follow_up_in_demo_email(self) -> None:
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL)
        self.assertIn("follow_up_marker", result["triage"]["matched_rules"])

    async def test_clean_content_has_no_html(self) -> None:
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL)
        self.assertNotIn("<html>", result["clean_content"])
        self.assertNotIn("<p>", result["clean_content"])

    async def test_clean_content_removes_legal_footer(self) -> None:
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL)
        self.assertNotIn("intended solely for the use of", result["clean_content"])

    async def test_clean_content_removes_unsubscribe(self) -> None:
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL)
        self.assertNotIn("Unsubscribe", result["clean_content"])

    async def test_audit_result_has_required_keys(self) -> None:
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL)
        for key in ("approved", "violations", "sanitized_draft", "recommended_fix_notes"):
            with self.subTest(key=key):
                self.assertIn(key, result["audit"])

    async def test_no_key_produces_placeholder_draft(self) -> None:
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL)
        self.assertIsInstance(result["draft"], str)
        self.assertGreater(len(result["draft"]), 0)
        self.assertIsNone(result["llm_error"])

    async def test_audit_catches_bad_llm_draft(self) -> None:
        bad_draft = (
            "We guarantee you will get an upgrade. "
            "We were at fault. Card: 4111 1111 1111 1111."
        )
        mock_kernel = _make_mock_kernel(bad_draft)
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_FAKE_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL, kernel=mock_kernel)
        audit = result["audit"]
        self.assertFalse(audit["approved"])
        self.assertIn("guarantee_or_concession", audit["violations"])
        self.assertIn("admission_of_fault", audit["violations"])
        self.assertIn("payment_leakage", audit["violations"])

    async def test_audit_passes_good_draft(self) -> None:
        mock_kernel = _make_mock_kernel(_GOOD_DRAFT)
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_FAKE_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL, kernel=mock_kernel)
        self.assertTrue(result["audit"]["approved"])
        self.assertEqual(result["audit"]["violations"], [])

    async def test_llm_error_captured_on_exception(self) -> None:
        kernel = AsyncMock()
        kernel.invoke_prompt = AsyncMock(side_effect=RuntimeError("Simulated API error"))
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_FAKE_KEY_SETTINGS):
            result = await run_pipeline(DEMO_EMAIL, kernel=kernel)
        self.assertIsNotNone(result["llm_error"])
        self.assertIn("Simulated API error", result["llm_error"])

    async def test_minimal_email_runs_without_error(self) -> None:
        minimal = {"subject": "Hi", "sender_name": "Alice", "sender_email": "", "importance": "", "raw_content": ""}
        with patch("replyright_kernel.demo.get_kernel_settings", return_value=_NO_KEY_SETTINGS):
            result = await run_pipeline(minimal)
        self.assertIn("triage", result)
        self.assertIn("audit", result)


if __name__ == "__main__":
    unittest.main()

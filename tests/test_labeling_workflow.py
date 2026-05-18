"""Tests for the human-in-the-loop dual-labeling workflow.

Covers: export formatting, import agreement logic (full/partial/low),
critic-format normalization, flexible file discovery, idempotency,
skip-reviewed filtering, run-log writing.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_rows(n: int, reviewed: bool = False) -> list[dict]:
    return [
        {
            "id": f"id-{i:04d}",
            "sender_domain": f"domain{i}.com",
            "subject_tokens": f"reservation checkin suite {i}",
            "body_redacted": f"Guest arriving on May 25. Confirmation [REDACTED]. Body {i}.",
            "created_at": f"2026-05-{10 + i:02d}T10:00:00Z",
            "human_reviewed": reviewed,
        }
        for i in range(1, n + 1)
    ]


def _claude_label(tid: str, **overrides) -> dict:
    base = {
        "training_example_id": tid,
        "category": "VIP pre-arrival",
        "priority_level": "High",
        "owner": "Reservations",
        "contact_type": "Direct guest",
        "guest_sentiment": "Positive",
        "missing_information": None,
        "confidence": 90,
        "notes": "",
    }
    base.update(overrides)
    return base


def _chatgpt_label(tid: str, **overrides) -> dict:
    base = _claude_label(tid)
    base.update(overrides)
    return base


def _chatgpt_critic(tid: str, agrees: dict | None = None, corrected: dict | None = None) -> dict:
    """Build a ChatGPT critic-format row (all fields agree by default)."""
    default_agrees = {
        "category": True,
        "priority_level": True,
        "owner": True,
        "contact_type": True,
        "guest_sentiment": True,
        "missing_information": True,
    }
    if agrees:
        default_agrees.update(agrees)
    return {
        "training_example_id": tid,
        "agrees_with_claude": default_agrees,
        "corrected_labels": corrected or {},
        "critic_confidence": 90,
        "reasoning": "test",
    }


# ── module loaders ─────────────────────────────────────────────────────────────

def _load_import_module():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "import_labels",
        Path(__file__).parent.parent / "scripts" / "import_labels.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["import_labels"] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_export_module():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "export_for_labeling",
        Path(__file__).parent.parent / "scripts" / "export_for_labeling.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["export_for_labeling"] = mod
    spec.loader.exec_module(mod)
    return mod


# ── export tests ──────────────────────────────────────────────────────────────

class TestExportFormatting:
    def test_markdown_header(self):
        mod = _load_export_module()
        rows = _make_rows(3)
        md = mod._format_markdown(rows, "2026-05-18")
        assert "# ReplyRight Labeling Batch" in md
        assert "2026-05-18" in md
        assert "**Total emails:** 3" in md

    def test_each_email_block(self):
        mod = _load_export_module()
        rows = _make_rows(5)
        md = mod._format_markdown(rows, "2026-05-18")
        for i in range(1, 6):
            assert f"## Email {i}" in md
        assert "[ID: id-0001]" in md
        assert "domain1.com" in md

    def test_reminder_footer(self):
        mod = _load_export_module()
        rows = _make_rows(2)
        md = mod._format_markdown(rows, "2026-05-18")
        assert "OUTPUT SCHEMA" in md
        assert "training_example_id" in md
        assert "TAXONOMY" in md

    def test_empty_rows(self):
        mod = _load_export_module()
        md = mod._format_markdown([], "2026-05-18")
        assert "**Total emails:** 0" in md

    def test_body_included(self):
        mod = _load_export_module()
        rows = _make_rows(1)
        rows[0]["body_redacted"] = "Unique body content XYZ"
        md = mod._format_markdown(rows, "2026-05-18")
        assert "Unique body content XYZ" in md

    def test_skip_reviewed_query_param(self):
        mod = _load_export_module()
        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = []
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

            with patch.dict("os.environ", {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "key"}):
                mod._fetch_examples(count=5, skip_reviewed=True)

            call_kwargs = mock_client_cls.return_value.__enter__.return_value.get.call_args
            params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
            assert params.get("human_reviewed") == "eq.false"

    def test_no_skip_reviewed_omits_filter(self):
        mod = _load_export_module()
        with patch("httpx.Client") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = []
            mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

            with patch.dict("os.environ", {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "key"}):
                mod._fetch_examples(count=5, skip_reviewed=False)

            call_kwargs = mock_client_cls.return_value.__enter__.return_value.get.call_args
            params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
            assert "human_reviewed" not in params


# ── critic-format normalization tests ─────────────────────────────────────────

class TestCriticFormatNormalization:
    def test_is_critic_format_detects_key(self):
        mod = _load_import_module()
        assert mod._is_critic_format({"agrees_with_claude": {}}) is True
        assert mod._is_critic_format({"category": "VIP pre-arrival"}) is False

    def test_full_agreement_critic_adopts_claude_values(self):
        mod = _load_import_module()
        tid = "norm-001"
        c = _claude_label(tid)
        critic = _chatgpt_critic(tid)  # all agrees=True, no corrections
        normalized = mod._normalize_critic_to_labels(critic, c)
        assert normalized["category"] == c["category"]
        assert normalized["priority_level"] == c["priority_level"]
        assert normalized["owner"] == c["owner"]

    def test_disagreement_critic_uses_corrected_value(self):
        mod = _load_import_module()
        tid = "norm-002"
        c = _claude_label(tid, category="VIP pre-arrival")
        critic = _chatgpt_critic(
            tid,
            agrees={"category": False},
            corrected={"category": "Rooming list / group"},
        )
        normalized = mod._normalize_critic_to_labels(critic, c)
        assert normalized["category"] == "Rooming list / group"
        # other fields adopted from Claude
        assert normalized["owner"] == c["owner"]

    def test_critic_partial_disagreement_count(self):
        mod = _load_import_module()
        tid = "norm-003"
        c = _claude_label(tid)
        critic = _chatgpt_critic(
            tid,
            agrees={"category": False, "owner": False},
            corrected={"category": "Billing dispute", "owner": "Front Desk"},
        )
        normalized = mod._normalize_critic_to_labels(critic, c)
        # Only 2 fields differ from Claude's original
        match_count, _, disagreed = mod._count_agreements(c, normalized)
        assert match_count == 4
        assert "category" in disagreed
        assert "owner" in disagreed


# ── file discovery tests ──────────────────────────────────────────────────────

class TestFileFindByDate:
    def test_finds_hyphen_date_file(self, tmp_path):
        mod = _load_import_module()
        folder = tmp_path / "Claude"
        folder.mkdir()
        f = folder / "2026-05-18-labels.json"
        f.write_text("[]")
        result = mod._find_date_file(folder, "2026-05-18")
        assert result == f

    def test_finds_underscore_date_file(self, tmp_path):
        mod = _load_import_module()
        folder = tmp_path / "ChatGPT"
        folder.mkdir()
        f = folder / "replyright_critic_results_2026_05_18_json.json"
        f.write_text("[]")
        result = mod._find_date_file(folder, "2026-05-18")
        assert result == f

    def test_returns_none_for_missing_date(self, tmp_path):
        mod = _load_import_module()
        folder = tmp_path / "Claude"
        folder.mkdir()
        (folder / "2026-05-17-labels.json").write_text("[]")
        result = mod._find_date_file(folder, "2026-05-18")
        assert result is None

    def test_returns_none_for_missing_folder(self, tmp_path):
        mod = _load_import_module()
        result = mod._find_date_file(tmp_path / "DoesNotExist", "2026-05-18")
        assert result is None


# ── import / agreement tests ──────────────────────────────────────────────────

class TestImportFullAgreement:
    def test_dual_labeled_outcome(self):
        mod = _load_import_module()
        tid = "aaaa-bbbb"
        claude = [_claude_label(tid)]
        chatgpt = [_chatgpt_label(tid)]
        match_count, agreed, disagreed = mod._count_agreements(claude[0], chatgpt[0])
        assert match_count == 6
        assert disagreed == []

    def test_full_agreement_sets_human_reviewed(self):
        mod = _load_import_module()
        tid = "full-agree-001"
        c = _claude_label(tid)
        g = _chatgpt_label(tid)
        match_count, agreed, _ = mod._count_agreements(c, g)
        assert match_count == 6
        update = mod._build_update(c, agreed)
        update["human_reviewed"] = True
        update["labeling_engine"] = "dual_labeled"
        assert update["human_reviewed"] is True
        assert update["labeling_engine"] == "dual_labeled"
        assert update.get("label_category") == "VIP pre-arrival"
        assert update.get("label_owner") == "Reservations"
        assert update.get("label_urgency") == 4  # High -> 4

    def test_critic_full_agreement_is_dual_labeled(self):
        mod = _load_import_module()
        tid = "critic-full-001"
        c = _claude_label(tid)
        critic = _chatgpt_critic(tid)
        normalized = mod._normalize_critic_to_labels(critic, c)
        match_count, agreed, _ = mod._count_agreements(c, normalized)
        assert match_count == 6


class TestImportPartialAgreement:
    def test_4_of_6_is_partial(self):
        mod = _load_import_module()
        tid = "partial-001"
        c = _claude_label(tid, category="Rate inquiry", priority_level="Normal")
        g = _chatgpt_label(tid)  # different category and priority
        match_count, agreed, disagreed = mod._count_agreements(c, g)
        assert match_count == 4
        assert "category" in disagreed
        assert "priority_level" in disagreed

    def test_partial_only_writes_agreed_fields(self):
        mod = _load_import_module()
        tid = "partial-002"
        c = _claude_label(tid, category="Rate inquiry")
        g = _chatgpt_label(tid)  # agrees on 5 fields, disagrees on category
        _, agreed, disagreed = mod._count_agreements(c, g)
        assert "category" in disagreed
        update = mod._build_update(c, agreed)
        assert "label_category" not in update
        assert "label_owner" in update


class TestImportLowAgreement:
    def test_2_of_6_is_needs_review(self):
        mod = _load_import_module()
        tid = "low-001"
        c = _claude_label(tid,
            category="Billing dispute",
            priority_level="Immediate",
            owner="Front Desk",
            contact_type="Travel agency",
        )
        g = _chatgpt_label(tid)  # disagrees on 4 fields
        match_count, _, _ = mod._count_agreements(c, g)
        assert match_count <= 3


class TestImportIdempotency:
    def test_same_date_twice_is_safe(self):
        mod = _load_import_module()
        tid = "idem-001"
        claude_row = _claude_label(tid)
        chatgpt_row = _chatgpt_label(tid)
        # Calling count_agreements twice produces the same result — no side effects
        r1 = mod._count_agreements(claude_row, chatgpt_row)
        r2 = mod._count_agreements(claude_row, chatgpt_row)
        assert r1 == r2


class TestRunLogWritten:
    def test_run_log_file_created(self, tmp_path):
        mod = _load_import_module()
        tid = "log-001"
        claude_data = [_claude_label(tid)]
        chatgpt_data = [_chatgpt_label(tid)]

        claude_dir = tmp_path / "labeling" / "Claude"
        claude_dir.mkdir(parents=True)
        chatgpt_dir = tmp_path / "labeling" / "ChatGPT"
        chatgpt_dir.mkdir(parents=True)
        runs_dir = tmp_path / "labeling" / "runs"
        runs_dir.mkdir(parents=True)

        (claude_dir / "2026-05-18-labels.json").write_text(json.dumps(claude_data))
        (chatgpt_dir / "2026-05-18-chatgpt.json").write_text(json.dumps(chatgpt_data))

        patch_log: list = []

        def fake_patch(tid_, update):
            patch_log.append(tid_)
            return True, ""

        with patch.object(mod, "_patch_example", side_effect=fake_patch), \
             patch.object(mod, "ROOT", tmp_path), \
             patch("sys.argv", ["import_labels.py", "--date", "2026-05-18"]):
            mod.main()

        run_files = list(runs_dir.glob("*.json"))
        assert len(run_files) == 1
        log_data = json.loads(run_files[0].read_text())
        assert log_data["date"] == "2026-05-18"
        assert log_data["stats"]["processed"] == 1
        assert log_data["stats"]["dual_labeled"] == 1

    def test_run_log_with_critic_format(self, tmp_path):
        mod = _load_import_module()
        tid = "log-critic-001"
        claude_data = [_claude_label(tid)]
        chatgpt_data = [_chatgpt_critic(tid)]  # critic format — full agreement

        claude_dir = tmp_path / "labeling" / "Claude"
        claude_dir.mkdir(parents=True)
        chatgpt_dir = tmp_path / "labeling" / "ChatGPT"
        chatgpt_dir.mkdir(parents=True)
        runs_dir = tmp_path / "labeling" / "runs"
        runs_dir.mkdir(parents=True)

        (claude_dir / "2026-05-18-labels.json").write_text(json.dumps(claude_data))
        (chatgpt_dir / "replyright_critic_results_2026_05_18_json.json").write_text(json.dumps(chatgpt_data))

        patch_log: list = []

        def fake_patch(tid_, update):
            patch_log.append(tid_)
            return True, ""

        with patch.object(mod, "_patch_example", side_effect=fake_patch), \
             patch.object(mod, "ROOT", tmp_path), \
             patch("sys.argv", ["import_labels.py", "--date", "2026-05-18"]):
            mod.main()

        run_files = list(runs_dir.glob("*.json"))
        assert len(run_files) == 1
        log_data = json.loads(run_files[0].read_text())
        assert log_data["stats"]["dual_labeled"] == 1

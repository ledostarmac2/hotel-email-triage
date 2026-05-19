from __future__ import annotations

from pathlib import Path


_REQUIRED_FILES = [
    "docs/coordination/README.md",
    "docs/coordination/CURRENT_SITREP.md",
    "docs/coordination/TASK_BOARD.md",
    "docs/coordination/DECISIONS.md",
    "docs/coordination/BLOCKERS.md",
    "docs/coordination/HANDOFF_CLAUDE.md",
    "docs/coordination/HANDOFF_CODEX.md",
    "docs/coordination/HANDOFF_GEMINI.md",
    "docs/coordination/RELEASE_GATES.md",
    "docs/coordination/SECURITY_GATES.md",
    "docs/coordination/PYSIDE6_MIGRATION.md",
    "docs/coordination/DAILY_LOG.md",
]


def test_all_agent_hub_files_exist() -> None:
    missing = [f for f in _REQUIRED_FILES if not Path(f).exists()]
    assert not missing, f"Missing coordination files: {missing}"


def test_blockers_mentions_gemini_verdict() -> None:
    text = Path("docs/coordination/BLOCKERS.md").read_text(encoding="utf-8")
    assert "Gemini" in text
    assert "BLOCKER-001" in text


def test_handoff_gemini_has_verdict_section() -> None:
    text = Path("docs/coordination/HANDOFF_GEMINI.md").read_text(encoding="utf-8")
    assert "§Verdict" in text


def test_handoff_codex_says_check_verdict_first() -> None:
    text = Path("docs/coordination/HANDOFF_CODEX.md").read_text(encoding="utf-8")
    assert "Gemini" in text
    assert "verdict" in text.lower()


def test_security_gates_cannot_be_empty() -> None:
    text = Path("docs/coordination/SECURITY_GATES.md").read_text(encoding="utf-8")
    assert "GATE-S01" in text
    assert "GATE-S02" in text
    assert "SUPABASE_SERVICE_ROLE_KEY" in text


def test_release_gates_lists_gemini_verdict() -> None:
    text = Path("docs/coordination/RELEASE_GATES.md").read_text(encoding="utf-8")
    assert "Gemini" in text
    assert "verdict" in text.lower()


def test_current_sitrep_is_not_empty() -> None:
    text = Path("docs/coordination/CURRENT_SITREP.md").read_text(encoding="utf-8")
    assert len(text) > 200


def test_decisions_file_contains_no_browser_engine_rule() -> None:
    text = Path("docs/coordination/DECISIONS.md").read_text(encoding="utf-8")
    assert "QWebEngineView" in text
    assert "DEC-005" in text


def test_daily_log_has_entries() -> None:
    text = Path("docs/coordination/DAILY_LOG.md").read_text(encoding="utf-8")
    assert "2026-05-18" in text

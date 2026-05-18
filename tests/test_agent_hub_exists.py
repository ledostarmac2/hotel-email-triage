from __future__ import annotations

from pathlib import Path


_REQUIRED_FILES = [
    "agent_hub/README.md",
    "agent_hub/CURRENT_SITREP.md",
    "agent_hub/TASK_BOARD.md",
    "agent_hub/DECISIONS.md",
    "agent_hub/BLOCKERS.md",
    "agent_hub/HANDOFF_CLAUDE.md",
    "agent_hub/HANDOFF_CODEX.md",
    "agent_hub/HANDOFF_GEMINI.md",
    "agent_hub/RELEASE_GATES.md",
    "agent_hub/SECURITY_GATES.md",
    "agent_hub/PYSIDE6_MIGRATION.md",
    "agent_hub/DAILY_LOG.md",
]


def test_all_agent_hub_files_exist() -> None:
    missing = [f for f in _REQUIRED_FILES if not Path(f).exists()]
    assert not missing, f"Missing agent_hub files: {missing}"


def test_blockers_mentions_gemini_verdict() -> None:
    text = Path("agent_hub/BLOCKERS.md").read_text(encoding="utf-8")
    assert "Gemini" in text
    assert "BLOCKER-001" in text


def test_handoff_gemini_has_verdict_section() -> None:
    text = Path("agent_hub/HANDOFF_GEMINI.md").read_text(encoding="utf-8")
    assert "§Verdict" in text


def test_handoff_codex_says_check_verdict_first() -> None:
    text = Path("agent_hub/HANDOFF_CODEX.md").read_text(encoding="utf-8")
    assert "Gemini" in text
    assert "verdict" in text.lower()


def test_security_gates_cannot_be_empty() -> None:
    text = Path("agent_hub/SECURITY_GATES.md").read_text(encoding="utf-8")
    assert "GATE-S01" in text
    assert "GATE-S02" in text
    assert "SUPABASE_SERVICE_ROLE_KEY" in text


def test_release_gates_lists_gemini_verdict() -> None:
    text = Path("agent_hub/RELEASE_GATES.md").read_text(encoding="utf-8")
    assert "Gemini" in text
    assert "verdict" in text.lower()


def test_current_sitrep_is_not_empty() -> None:
    text = Path("agent_hub/CURRENT_SITREP.md").read_text(encoding="utf-8")
    assert len(text) > 200


def test_decisions_file_contains_no_browser_engine_rule() -> None:
    text = Path("agent_hub/DECISIONS.md").read_text(encoding="utf-8")
    assert "QWebEngineView" in text
    assert "DEC-005" in text


def test_daily_log_has_entries() -> None:
    text = Path("agent_hub/DAILY_LOG.md").read_text(encoding="utf-8")
    assert "2026-05-18" in text

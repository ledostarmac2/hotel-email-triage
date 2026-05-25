from __future__ import annotations

from pathlib import Path


WORKSPACE = Path("agent-workspace")


def test_agent_messages_file_exists_with_template() -> None:
    messages = WORKSPACE / "AGENT_MESSAGES.md"
    assert messages.exists()
    text = messages.read_text(encoding="utf-8")
    for expected in [
        "## Message",
        "Date/Time:",
        "From:",
        "To:",
        "Related Task:",
        "Status: Question / Handoff / Review Request / Blocker / FYI / Approved / Needs Changes",
        "Required Response:",
    ]:
        assert expected in text


def test_root_agent_guides_require_agent_messages() -> None:
    assert "AGENT_MESSAGES.md" in Path("AGENTS.md").read_text(encoding="utf-8")
    assert "AGENT_MESSAGES.md" in Path("CLAUDE.md").read_text(encoding="utf-8")


def test_agent_rules_require_message_before_session_completion() -> None:
    rules = (WORKSPACE / "AGENT_RULES.md").read_text(encoding="utf-8")
    assert (
        "If you complete a session without writing to AGENT_MESSAGES.md, "
        "the session is incomplete."
    ) in rules


def test_task_board_defines_required_review_statuses_and_done_gate() -> None:
    task_board = (WORKSPACE / "TASK_BOARD.md").read_text(encoding="utf-8")
    for status in [
        "Not Started",
        "Assigned to Claude",
        "Waiting for Codex Review",
        "Needs Claude Changes",
        "Approved by Codex",
        "Done",
        "Blocked",
    ]:
        assert status in task_board
    assert "Claude has left a handoff or review request" in task_board
    assert "Codex has left `Approved` or `Needs Changes`" in task_board


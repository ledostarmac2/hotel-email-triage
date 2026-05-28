from __future__ import annotations

from pathlib import Path


def test_agent_training_runbook_requires_agent_labels_not_heuristics() -> None:
    text = Path("docs/TRAINING_WORKFLOW.md").read_text(encoding="utf-8")

    assert "outside agent labels sanitized examples using its own model judgment" in text
    assert "run_completed_pipeline()" in text
    assert "does not satisfy Brian's outside-agent request" in text
    assert "heuristic_analysis()" in text
    assert "not the final labeler" in text


def test_agent_guides_warn_against_pipeline_only_training() -> None:
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    claude = Path("CLAUDE.md").read_text(encoding="utf-8")

    for text in (agents, claude):
        assert "In-app training endpoints" in text
        assert "zero-credit" in text
        assert "run_completed_pipeline()" in text
        assert "heuristic_analysis()" in text

    assert "not, by itself, Brian's requested agent-assisted training workflow" in agents
    assert "Do not claim training is complete by only running" in claude


def test_agent_label_helper_uses_active_taxonomy_and_agent_judgment() -> None:
    from outlook_dashboard.taxonomy import CATEGORIES, CONTACT_TYPES, DEPARTMENT_OWNERS
    from scripts import agent_label_completed_requests as helper

    instructions = helper.LABELING_INSTRUCTIONS

    assert "outside-agent model judgment" in instructions
    assert "The app heuristic labels are reference only" in instructions

    for value in ("Credit card authorization", "  Guest\n"):
        assert value not in instructions

    for value in ("Billing authorization", "Direct guest"):
        assert value in instructions

    for category in CATEGORIES:
        assert category in instructions
    for owner in DEPARTMENT_OWNERS:
        assert owner in instructions
    for contact_type in CONTACT_TYPES:
        assert contact_type in instructions


def test_agent_label_helper_prints_current_train_result_shape(capsys) -> None:
    from scripts.agent_label_completed_requests import _print_train_result

    _print_train_result(
        {
            "trained": True,
            "examples": 3,
            "targets": ["urgency", "owner"],
            "accuracy": {"urgency": 0.5, "owner": 1.0},
            "label_distributions": {
                "urgency": {"2": 2, "4": 1},
                "owner": {"Reservations": 3},
            },
        }
    )

    out = capsys.readouterr().out
    assert "Trained on 3 examples." in out
    assert "urgency: 50.0% CV accuracy (3 rows)" in out
    assert "owner: 100.0% CV accuracy (3 rows)" in out


def test_agent_label_helper_prints_unavailable_negative_accuracy(capsys) -> None:
    from scripts.agent_label_completed_requests import _print_train_result

    _print_train_result(
        {
            "trained": True,
            "examples": 3,
            "targets": ["category"],
            "accuracy": {"category": -1.0},
            "label_distributions": {"category": {"General inquiry": 3}},
        }
    )

    out = capsys.readouterr().out
    assert "category: 3 rows (accuracy unavailable)" in out
    assert "-100.0%" not in out

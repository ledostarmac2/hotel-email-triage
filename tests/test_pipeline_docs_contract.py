from __future__ import annotations

from pathlib import Path


def test_training_workflow_doc_exists_and_references_canonical_sources() -> None:
    """docs/TRAINING_WORKFLOW.md is the agent-facing training runbook."""
    text = Path("docs/TRAINING_WORKFLOW.md").read_text(encoding="utf-8")
    assert "run_completed_pipeline" in text
    assert "docs/TRAINING_PIPELINE.md" in text
    assert "never calls external AI" in text.lower() or "never call" in text.lower()
    # The training/ folder has been removed; confirm it's gone
    assert not Path("training").exists(), "training/ folder should be deleted"


def test_v1_release_plan_names_canonical_docs_and_gates() -> None:
    text = Path("docs/V1_RELEASE_PLAN.md").read_text(encoding="utf-8")
    for path in (
        "docs/CURRENT_STATE.md",
        "docs/ARCHITECTURE.md",
        "docs/TRAINING_PIPELINE.md",
        "docs/CLASSIFIER.md",
        "docs/SECURITY_AND_PRIVACY.md",
        "docs/DEPLOYMENT.md",
    ):
        assert path in text
    assert "v1.0.0 Gates" in text
    assert "In-app training endpoints are zero-credit" in text


def test_agent_guide_points_v1_work_to_release_plan() -> None:
    text = Path("AGENTS.md").read_text(encoding="utf-8")
    assert "docs/V1_RELEASE_PLAN.md" in text
    assert "Do not call Claude during bulk inbox refresh or in-app training endpoints." in text


def test_coordination_docs_are_marked_historical() -> None:
    text = Path("docs/coordination/README.md").read_text(encoding="utf-8")
    assert "Historical coordination archive" in text
    assert "docs/V1_RELEASE_PLAN.md" in text


def test_archive_docs_are_marked_historical() -> None:
    archive_docs = list(Path("docs/archive").rglob("*.md"))
    assert archive_docs, "expected archived planning/migration docs to exist"
    for path in archive_docs:
        text = path.read_text(encoding="utf-8").lstrip("\ufeff")
        assert text.startswith("> Historical archive."), f"{path} lacks historical archive banner"

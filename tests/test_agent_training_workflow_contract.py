from __future__ import annotations

import json
from pathlib import Path

from outlook_dashboard.database import initialize_database, managed_connect


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


def test_agent_requeue_stale_pending_recovers_lost_batch(tmp_path: Path) -> None:
    from scripts.agent_label_completed_requests import requeue_stale_pending

    db_path = tmp_path / "agent_requeue.sqlite3"
    initialize_database(db_path)
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT INTO completed_requests_log
                (outlook_entry_id, import_key, result, processed_at)
            VALUES
                ('entry-stale', 'import-stale', 'agent_pending', '2026-05-28T00:00:00+00:00'),
                ('entry-uploaded', 'import-uploaded', 'uploaded', '2026-05-28T00:00:00+00:00')
            """
        )

    count = requeue_stale_pending(stale_minutes=60, db_path=db_path)

    with managed_connect(db_path) as db:
        rows = {
            row["import_key"]: row["result"]
            for row in db.execute("SELECT import_key, result FROM completed_requests_log")
        }
    assert count == 1
    assert rows["import-stale"] == "failed"
    assert rows["import-uploaded"] == "uploaded"


def test_agent_upload_marks_reviewed_and_skips_duplicate_labels(tmp_path: Path, monkeypatch) -> None:
    from scripts.agent_label_completed_requests import phase_upload

    db_path = tmp_path / "agent_upload.sqlite3"
    initialize_database(db_path)
    with managed_connect(db_path) as db:
        db.execute(
            """
            INSERT INTO completed_requests_log
                (outlook_entry_id, import_key, result, processed_at)
            VALUES ('entry-1', 'import-1', 'agent_pending', '2026-05-28T00:00:00+00:00')
            """
        )

    pending_path = tmp_path / "batch_pending.json"
    labels_path = tmp_path / "batch_labeled.json"
    pending_path.write_text(
        json.dumps(
            {
                "examples": [
                    {
                        "fingerprint": "f" * 64,
                        "import_key": "import-1",
                        "sender_domain": "example.com",
                        "subject_tokens": "payment authorization",
                        "body_excerpt": "Completed payment authorization form.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    label = {
        "fingerprint": "f" * 64,
        "category": "Billing authorization",
        "priority_level": "Normal",
        "owner": "Reservations",
        "contact_type": "Travel agency",
        "guest_sentiment": "Neutral",
        "label_missing_info": False,
        "label_reply_required": False,
        "label_escalation_required": False,
        "recommended_action": "verify_payment_authorization",
    }
    labels_path.write_text(json.dumps([label, label]), encoding="utf-8")

    uploaded: list[dict] = []

    def _fake_upload(record: dict) -> tuple[bool, str]:
        uploaded.append(record)
        return True, ""

    monkeypatch.setattr("outlook_dashboard.training_pipeline._upload_example", _fake_upload)

    result = phase_upload(
        pending_path=pending_path,
        labels_path=labels_path,
        db_path=db_path,
        skip_train=True,
        skip_purge=True,
    )

    assert result["uploaded"] == 1
    assert result["skipped"] == 1
    assert uploaded[0]["labeling_engine"] == "claude-agent"
    assert uploaded[0]["human_reviewed"] is True
    assert uploaded[0]["label_recommended_action"] == "verify_payment_authorization"
    with managed_connect(db_path) as db:
        status = db.execute(
            "SELECT result FROM completed_requests_log WHERE import_key = 'import-1'"
        ).fetchone()["result"]
    assert status == "uploaded"

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from outlook_dashboard.completed_training_pipeline import (
    completed_pipeline_status,
    run_completed_pipeline,
)
from outlook_dashboard.database import initialize_database, managed_connect


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "completed_training.sqlite3"
    initialize_database(db_path)
    return db_path


def _completed_message() -> dict:
    return {
        "outlook_entry_id": "entry-1",
        "graph_message_id": "entry-1",
        "subject": "Payment link request for arrival tomorrow",
        "sender_name": "Agency User",
        "sender_email": "agent@travelco.example",
        "from_name": "Agency User",
        "from_email": "agent@travelco.example",
        "received_datetime": "2026-05-17T10:00:00",
        "body_preview": "Please send a secure payment link for the guest arriving tomorrow.",
        "body_content_type": "text",
        "body_content": "Please send a secure payment link for the guest arriving tomorrow.",
        "body_text": "Please send a secure payment link for the guest arriving tomorrow.",
        "conversation_id": "conversation-1",
        "importance": "Normal",
        "has_attachments": False,
        "source": "completed_requests",
        "mailbox_mode": "shared",
    }


def test_completed_pipeline_uses_heuristics_without_external_ai(db: Path) -> None:
    with patch(
        "outlook_dashboard.completed_training_pipeline.read_completed_requests",
        return_value={"messages": [_completed_message()]},
    ), patch(
        "outlook_dashboard.completed_training_pipeline._upload_example",
        return_value=(True, ""),
    ) as upload:
        result = run_completed_pipeline("NYCWA_Reservations", db_path=db)

    assert result["imported"] == 1
    assert result["labeled"] == 1
    assert result["uploaded"] == 1
    assert result["external_ai_used"] is False
    assert result["labeling_mode"] == "heuristic"

    example = upload.call_args.args[0]
    assert example["labeling_engine"] == "heuristic"
    assert example["sender_domain"] == "travelco.example"
    assert "agent@travelco.example" not in example["body_redacted"]


def test_completed_pipeline_does_not_call_property_knowledge_claude(db: Path) -> None:
    with patch(
        "outlook_dashboard.completed_training_pipeline.read_completed_requests",
        return_value={"messages": [_completed_message()]},
    ), patch(
        "outlook_dashboard.completed_training_pipeline._upload_example",
        return_value=(True, ""),
    ), patch(
        "outlook_dashboard.property_knowledge.extract_with_claude",
        side_effect=AssertionError("Claude API must not be called"),
    ):
        result = run_completed_pipeline("NYCWA_Reservations", db_path=db)

    assert result["external_ai_used"] is False
    status = completed_pipeline_status(db_path=db)
    assert status["labeled"] == 1
    assert status["external_ai_used"] is False

    with managed_connect(db) as conn:
        row = conn.execute("SELECT result FROM completed_requests_log").fetchone()
    assert row["result"] == "heuristic"

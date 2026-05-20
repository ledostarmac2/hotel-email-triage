"""Tests for the training data pipeline module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from outlook_dashboard.database import (
    get_training_pipeline_status,
    initialize_database,
    list_unprocessed_completed_emails,
    log_training_example,
    managed_connect,
)
from outlook_dashboard.training_pipeline import (
    _build_example,
    _fingerprint,
    _subject_tokens,
    pipeline_status,
    run_pipeline,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path: Path):
    db_path = tmp_path / "training_test.sqlite3"
    initialize_database(db_path)
    return db_path


def _insert_completed_email(db_path: Path, *, email_id: int = 1, body: str = "Please send a payment link for our upcoming stay. The guest arrives tomorrow.") -> None:
    from outlook_dashboard.text_utils import utc_now_iso
    with managed_connect(db_path) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO emails
               (id, graph_message_id, subject, sender_name, sender_email,
                body_text, received_datetime, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'Completed', ?, ?)""",
            (email_id, f"msg-{email_id}", "Payment link request",
             "Agency User", f"agent{email_id}@travelco.example",
             body, "2026-05-17T10:00:00", utc_now_iso(), utc_now_iso()),
        )
        conn.execute(
            """INSERT OR IGNORE INTO email_analysis
               (email_id, recommended_department_owner, category, guest_sentiment,
                priority_level, analysis_engine, created_at, updated_at)
               VALUES (?, 'Reservations', 'General inquiry', 'Neutral', 'Normal', 'heuristic', ?, ?)""",
            (email_id, utc_now_iso(), utc_now_iso()),
        )


# ── unit: helper functions ─────────────────────────────────────────────────────

def test_subject_tokens_strips_stop_words():
    tokens = _subject_tokens("Please send a payment link request")
    assert "please" not in tokens
    assert "payment" in tokens
    assert "request" in tokens


def test_subject_tokens_length_capped():
    long_subject = "word" * 100
    assert len(_subject_tokens(long_subject)) <= 200


def test_fingerprint_is_deterministic():
    fp1 = _fingerprint("agent@travelco.example", "Payment link request")
    fp2 = _fingerprint("agent@travelco.example", "Payment link request")
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_differs_by_domain():
    fp1 = _fingerprint("agent@travelco.example", "Payment link request")
    fp2 = _fingerprint("agent@otheragency.example", "Payment link request")
    assert fp1 != fp2


def test_build_example_redacts_body():
    row = {
        "sender_email": "guest@hotel.example",
        "subject": "Payment request",
        "body_text": "Please charge card 4111111111111111 exp 12/26.",
        "analysis_engine": "heuristic",
    }
    example = _build_example(row, row, "heuristic")
    assert "4111111111111111" not in example["body_redacted"]
    assert "[REDACTED_CARD]" in example["body_redacted"]


def test_build_example_normalizes_invalid_urgency():
    row = {"sender_email": "a@b.com", "subject": "Test", "body_text": "Some content here for testing purposes ok.",
           "analysis_engine": "heuristic"}
    labels = {**row, "urgency": 99}
    example = _build_example(row, labels, "heuristic")
    assert example["label_urgency"] is None


def test_build_example_maps_priority_level_to_urgency():
    row = {"sender_email": "a@b.com", "subject": "Test",
           "body_text": "Requesting upgrade for VIP guest arrival.",
           "priority_level": "High", "analysis_engine": "heuristic"}
    example = _build_example(row, row, "heuristic")
    assert example["label_urgency"] == 4


def test_build_example_filters_invalid_owner():
    row = {"sender_email": "a@b.com", "subject": "Test", "body_text": "Some content here for testing.",
           "recommended_department_owner": "Unknown Dept", "analysis_engine": "heuristic"}
    example = _build_example(row, row, "heuristic")
    assert example["label_owner"] is None


def test_build_example_valid_owner_passes_through():
    row = {"sender_email": "a@b.com", "subject": "Test",
           "body_text": "Requesting upgrade for VIP guest arrival.",
           "recommended_department_owner": "Reservations", "analysis_engine": "heuristic"}
    example = _build_example(row, row, "heuristic")
    assert example["label_owner"] == "Reservations"


def test_build_example_email_not_stored():
    row = {"sender_email": "secret@guest.com", "subject": "Room request",
           "body_text": "Please contact me at secret@guest.com about my stay.",
           "analysis_engine": "heuristic"}
    example = _build_example(row, row, "heuristic")
    assert "secret@guest.com" not in example["body_redacted"]
    assert "secret@guest.com" not in (example.get("sender_domain") or "")


# ── unit: DB helpers ──────────────────────────────────────────────────────────

def test_log_and_status(db: Path):
    _insert_completed_email(db, email_id=1)
    log_training_example(1, "fp1", "uploaded", db_path=db)
    status = get_training_pipeline_status(db_path=db)
    assert status["uploaded"] == 1
    assert status["pending"] == 0


def test_list_unprocessed_skips_logged(db: Path):
    _insert_completed_email(db, email_id=1)
    _insert_completed_email(db, email_id=2)
    log_training_example(1, "fp1", "uploaded", db_path=db)
    rows = list_unprocessed_completed_emails(batch_size=10, db_path=db)
    ids = [r["id"] for r in rows]
    assert 1 not in ids
    assert 2 in ids


def test_log_training_upsert(db: Path):
    _insert_completed_email(db, email_id=1)
    log_training_example(1, "fp1", "failed", "timeout", db_path=db)
    log_training_example(1, "fp1", "uploaded", db_path=db)
    status = get_training_pipeline_status(db_path=db)
    assert status["uploaded"] == 1
    assert status["failed"] == 0


# ── integration: run_pipeline ─────────────────────────────────────────────────

def test_run_pipeline_skips_short_bodies(db: Path):
    _insert_completed_email(db, email_id=1, body="Hi.")
    result = run_pipeline(batch_size=5, refine=False, db_path=db)
    assert result["skipped"] == 1
    assert result["uploaded"] == 0


def test_run_pipeline_uploads_on_success(db: Path):
    _insert_completed_email(db, email_id=1)
    with patch("outlook_dashboard.training_pipeline._upload_example", return_value=(True, "")) as mock_upload:
        result = run_pipeline(batch_size=5, refine=False, db_path=db)
    assert result["uploaded"] == 1
    assert result["failed"] == 0
    assert mock_upload.call_count == 1
    example = mock_upload.call_args[0][0]
    assert example["labeling_engine"] == "heuristic"
    assert example["human_reviewed"] is False


def test_run_pipeline_logs_failure(db: Path):
    _insert_completed_email(db, email_id=1)
    with patch("outlook_dashboard.training_pipeline._upload_example", return_value=(False, "network error")):
        result = run_pipeline(batch_size=5, refine=False, db_path=db)
    assert result["failed"] == 1
    assert result["uploaded"] == 0


def test_run_pipeline_does_not_reprocess(db: Path):
    _insert_completed_email(db, email_id=1)
    with patch("outlook_dashboard.training_pipeline._upload_example", return_value=(True, "")):
        run_pipeline(batch_size=5, refine=False, db_path=db)
        result2 = run_pipeline(batch_size=5, refine=False, db_path=db)
    assert result2["processed"] == 0


def test_run_pipeline_refine_true_still_skips_claude(db: Path):
    _insert_completed_email(db, email_id=1)
    with patch("outlook_dashboard.training_pipeline._upload_example", return_value=(True, "")):
        with patch("outlook_dashboard.training_pipeline._label_with_claude") as mock_claude:
            result = run_pipeline(batch_size=5, refine=True, db_path=db)
    mock_claude.assert_not_called()
    assert result["uploaded"] == 1
    assert result["external_ai_used"] is False


def test_run_pipeline_refine_false_skips_claude(db: Path):
    _insert_completed_email(db, email_id=1)
    with patch("outlook_dashboard.training_pipeline._upload_example", return_value=(True, "")):
        with patch("outlook_dashboard.training_pipeline._label_with_claude") as mock_claude:
            run_pipeline(batch_size=5, refine=False, db_path=db)
    mock_claude.assert_not_called()


def test_pipeline_status_helper(db: Path):
    _insert_completed_email(db, email_id=1)
    log_training_example(1, "fp1", "uploaded", db_path=db)
    status = pipeline_status(db_path=db)
    assert status["uploaded"] == 1

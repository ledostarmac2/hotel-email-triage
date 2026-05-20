"""Completed Requests training pipeline.

Imports emails from the Outlook "Completed Requests" folder, classifies them
with local heuristics, stores compact sanitized training examples, and uploads
them to Supabase for review/classifier training.

PRIVACY CONTRACT - same as training_pipeline.py:
- Raw body_text is never sent to external AI by this pipeline.
- Full sender_email is never stored. Only sender_domain.
- Full subject is never stored. Only subject_tokens.

CREDIT USAGE
- Zero API credits. Agent-assisted grading should happen outside ReplyRight and
  be imported/reviewed through Supabase, not through the Anthropic API.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .ai import heuristic_analysis, latest_message_text
from .completed_requests_importer import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_FOLDER,
    mark_processed,
    read_completed_requests,
)
from .database import (
    log_training_example,
    save_analysis,
    upsert_email,
)
from .runtime_log import get_logger
from .training_pipeline import _build_example, _fingerprint, _subject_tokens, _upload_example

_log = get_logger("completed_training_pipeline")


def run_completed_pipeline(
    mailbox_name: str,
    folder_name: str = DEFAULT_FOLDER,
    batch_size: int = DEFAULT_BATCH_SIZE,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Run one zero-credit batch of the Completed Requests training pipeline."""
    result: dict[str, Any] = {
        "imported": 0,
        "labeled": 0,
        "uploaded": 0,
        "knowledge_items": 0,
        "skipped": 0,
        "failed": 0,
        "folder": folder_name,
        "mailbox": mailbox_name,
        "external_ai_used": False,
        "labeling_mode": "heuristic",
    }

    try:
        import_result = read_completed_requests(
            mailbox_name=mailbox_name,
            folder_name=folder_name,
            batch_size=batch_size,
            db_path=db_path,
        )
    except Exception as exc:
        result["error"] = str(exc)[:300]
        _log.error("completed_training_pipeline: import failed: %s", exc)
        return result

    messages = import_result.get("messages") or []
    result["imported"] = len(messages)
    _log.info("completed_training_pipeline: imported %d messages from %r", len(messages), folder_name)

    for msg in messages:
        entry_id = str(msg.get("outlook_entry_id") or msg.get("graph_message_id") or "")
        sender_email = str(msg.get("sender_email") or "")
        subject = str(msg.get("subject") or "")
        fp = _fingerprint(sender_email, subject)
        domain = (sender_email.split("@")[-1] if "@" in sender_email else "").lower() or None
        tokens = _subject_tokens(subject)

        try:
            email_id, _inserted = upsert_email(
                {**msg, "status": "Completed"},
                db_path=db_path,
            )
        except Exception as exc:
            _log.warning("completed_training_pipeline: upsert failed entry=%s: %s", entry_id[:16], exc)
            mark_processed(entry_id, "failed", tokens, domain, db_path=db_path)
            result["failed"] += 1
            continue

        body_raw = str(msg.get("body_text") or "")
        body_latest = latest_message_text(body_raw, max_chars=4000)
        if len(body_latest.strip()) < 40:
            _log.info("completed_training_pipeline: body too short, skipping email_id=%d", email_id)
            log_training_example(email_id, fp, "skipped", "body too short", db_path=db_path)
            mark_processed(entry_id, "skipped", tokens, domain, db_path=db_path)
            result["skipped"] += 1
            continue

        heuristic = heuristic_analysis(msg)
        save_analysis(email_id, heuristic, db_path=db_path)
        result["labeled"] += 1

        try:
            example = _build_example(msg, dict(heuristic), "heuristic")
        except Exception as exc:
            _log.warning("completed_training_pipeline: build_example failed email_id=%d: %s", email_id, exc)
            log_training_example(email_id, fp, "failed", str(exc)[:200], db_path=db_path)
            mark_processed(entry_id, "failed", tokens, domain, db_path=db_path)
            result["failed"] += 1
            continue

        ok, error = _upload_example(example)
        if ok:
            log_training_example(email_id, fp, "uploaded", db_path=db_path)
            result["uploaded"] += 1
            _log.info("completed_training_pipeline: uploaded fp=%.12s engine=heuristic", fp)
        else:
            log_training_example(email_id, fp, "failed", error, db_path=db_path)
            result["failed"] += 1
            _log.warning("completed_training_pipeline: upload failed email_id=%d: %s", email_id, error)

        mark_processed(entry_id, "heuristic", tokens, domain, db_path=db_path)

    return result


def completed_pipeline_status(db_path: Path | None = None) -> dict[str, Any]:
    """Return counts from completed_requests_log and property_knowledge_items."""
    from .database import managed_connect

    try:
        with managed_connect(db_path) as db:
            result_rows = db.execute(
                "SELECT result, COUNT(*) AS n FROM completed_requests_log GROUP BY result"
            ).fetchall()
            counts = {str(r["result"]): int(r["n"]) for r in result_rows}

            knowledge_rows = db.execute(
                "SELECT item_type, COUNT(*) AS n FROM property_knowledge_items GROUP BY item_type"
            ).fetchall()
            knowledge = {str(r["item_type"]): int(r["n"]) for r in knowledge_rows}

            total_processed = db.execute(
                "SELECT COUNT(*) FROM completed_requests_log"
            ).fetchone()[0]
    except Exception:
        return {"processed": 0, "knowledge": {}, "external_ai_used": False}

    return {
        "processed": int(total_processed),
        "labeled": counts.get("heuristic", 0),
        "failed": counts.get("failed", 0),
        "skipped": counts.get("skipped", 0),
        "knowledge": knowledge,
        "total_knowledge_items": sum(knowledge.values()),
        "external_ai_used": False,
        "labeling_mode": "heuristic",
    }

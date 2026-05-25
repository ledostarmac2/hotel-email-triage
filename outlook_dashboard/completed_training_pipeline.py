"""Completed Request training pipeline.

Imports emails from the Outlook 'Completed Request' folder, runs heuristic
labels, and uploads sanitized examples for human/agent review.

PRIVACY CONTRACT - same as training_pipeline.py:
- Raw body_text is never uploaded. Only body_redacted is stored.
- Full sender_email is never stored. Only sender_domain is stored.
- Full subject is never stored. Only subject_tokens are stored.
- This module never calls external AI providers.
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
from .config import get_settings
from .database import (
    log_training_example,
    managed_connect,
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
    """Run one batch of the Completed Requests training pipeline.

    The pipeline is zero-credit: it imports read-only Outlook messages, labels
    them with deterministic heuristics, builds redacted training examples, and
    uploads those sanitized records for review.
    """
    result: dict[str, Any] = {
        "imported": 0,
        "labeled": 0,
        "uploaded": 0,
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
            example = _build_example(msg, heuristic, "heuristic")
        except Exception as exc:
            _log.warning("completed_training_pipeline: build failed email_id=%d: %s", email_id, exc)
            log_training_example(email_id, fp, "failed", str(exc)[:200], db_path=db_path)
            mark_processed(entry_id, "failed", tokens, domain, db_path=db_path)
            result["failed"] += 1
            continue

        ok, error = _upload_example(example)
        if not ok:
            _log.warning("completed_training_pipeline: upload failed email_id=%d: %s", email_id, error)
            log_training_example(email_id, fp, "failed", error[:200], db_path=db_path)
            mark_processed(entry_id, "failed", tokens, domain, db_path=db_path)
            result["failed"] += 1
            continue

        result["uploaded"] += 1
        log_training_example(email_id, fp, "uploaded", db_path=db_path)
        mark_processed(entry_id, "heuristic", tokens, domain, db_path=db_path)

    purge = purge_processed_training_emails(db_path=db_path)
    result["purged_email_rows"] = purge["deleted_rows"]
    result["purged_export_files"] = purge["deleted_files"]

    return result


def purge_processed_training_emails(db_path: Path | None = None) -> dict[str, int]:
    """Delete raw imported training emails that have been processed.

    Removes rows from the `emails` table (and cascades to `email_analysis`) where
    source='completed_requests'.  The sanitized training examples in Supabase and
    the completed_requests_log audit trail are left intact.

    Also deletes any exported .msg files from data/outlook_exports/.

    Returns {deleted_rows, deleted_files}.
    """
    deleted_rows = 0
    deleted_files = 0

    try:
        with managed_connect(db_path) as db:
            cur = db.execute(
                "DELETE FROM emails WHERE source = 'completed_requests'"
            )
            deleted_rows = cur.rowcount
        if deleted_rows:
            _log.info("purge: deleted %d raw training emails from SQLite", deleted_rows)
    except Exception as exc:
        _log.warning("purge: SQLite delete failed: %s", exc)

    exports_dir = get_settings().database_path.parent / "outlook_exports"
    if exports_dir.exists():
        for f in exports_dir.rglob("*"):
            if f.is_file():
                try:
                    f.unlink()
                    deleted_files += 1
                except Exception as exc:
                    _log.warning("purge: could not delete %s: %s", f, exc)
        try:
            import shutil
            shutil.rmtree(exports_dir, ignore_errors=True)
        except Exception:
            pass
        if deleted_files:
            _log.info("purge: deleted %d exported .msg files", deleted_files)

    return {"deleted_rows": deleted_rows, "deleted_files": deleted_files}


def completed_pipeline_status(db_path: Path | None = None) -> dict[str, Any]:
    """Return Completed Requests training counts."""
    from .database import managed_connect

    try:
        with managed_connect(db_path) as db:
            result_rows = db.execute(
                "SELECT result, COUNT(*) AS n FROM completed_requests_log GROUP BY result"
            ).fetchall()
            counts = {str(r["result"]): int(r["n"]) for r in result_rows}
            total_processed = db.execute(
                "SELECT COUNT(*) FROM completed_requests_log"
            ).fetchone()[0]

            try:
                knowledge_rows = db.execute(
                    "SELECT item_type, COUNT(*) AS n FROM property_knowledge_items GROUP BY item_type"
                ).fetchall()
                knowledge = {str(r["item_type"]): int(r["n"]) for r in knowledge_rows}
            except Exception:
                knowledge = {}
    except Exception:
        return {
            "processed": 0,
            "uploaded": 0,
            "labeled": 0,
            "failed": 0,
            "skipped": 0,
            "knowledge": {},
            "total_knowledge_items": 0,
            "external_ai_used": False,
            "labeling_mode": "heuristic",
        }

    labeled = counts.get("heuristic", 0)
    return {
        "processed": int(total_processed),
        "uploaded": labeled,
        "labeled": labeled,
        "dumped": counts.get("dumped", 0),
        "failed": counts.get("failed", 0),
        "skipped": counts.get("skipped", 0),
        "knowledge": knowledge,
        "total_knowledge_items": sum(knowledge.values()),
        "external_ai_used": False,
        "labeling_mode": "heuristic",
    }

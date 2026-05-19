"""Completed Requests training pipeline.

Imports emails from the Outlook 'Completed Requests' folder, labels them
with Claude Sonnet, extracts property-specific knowledge, stores sanitized
training examples, and rebuilds training/PROPERTY_KNOWLEDGE.md.

PRIVACY CONTRACT — same as training_pipeline.py:
- Raw body_text is NEVER passed to Claude. Only body_redacted.
- Full sender_email is NEVER stored. Only sender_domain.
- Full subject is NEVER stored. Only subject_tokens (stop-word-filtered keywords).

CREDIT USAGE
- One Claude Sonnet call per unprocessed email in the batch.
"""
from __future__ import annotations

import json
import re
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
from .property_knowledge import (
    extract_with_claude,
    rebuild_knowledge_file,
    store_knowledge_items,
)
from .redaction import redact_sensitive_text
from .runtime_log import get_logger
from .taxonomy import CATEGORIES, DEPARTMENT_OWNERS, STATUSES
from .training_pipeline import _build_example, _fingerprint, _subject_tokens, _upload_example

_log = get_logger("completed_training_pipeline")


def run_completed_pipeline(
    mailbox_name: str,
    folder_name: str = DEFAULT_FOLDER,
    batch_size: int = DEFAULT_BATCH_SIZE,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Run one batch of the Completed Requests training pipeline.

    Steps per email:
    1. Import from Outlook (read-only COM).
    2. Upsert into local emails table with status='Completed'.
    3. Run heuristic_analysis for base labels.
    4. Call Claude Sonnet for enhanced labels + property knowledge.
    5. Store training example (compatible with existing Supabase schema).
    6. Store property knowledge items.
    7. Mark as processed in completed_requests_log.

    Args:
        mailbox_name: Outlook mailbox display name (e.g. shared inbox name).
        folder_name: Sub-folder to read from.
        batch_size: Max emails to process per call.
        db_path: Override SQLite path (tests/dev).

    Returns:
        Summary dict with counts and property knowledge stats.
    """
    from .config import get_settings

    settings = get_settings()

    result: dict[str, Any] = {
        "imported": 0,
        "labeled": 0,
        "uploaded": 0,
        "knowledge_items": 0,
        "skipped": 0,
        "failed": 0,
        "folder": folder_name,
        "mailbox": mailbox_name,
    }

    # ── 1. Import from Outlook ────────────────────────────────────────────────
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

    if not messages:
        return result

    # ── 2-7. Process each message ─────────────────────────────────────────────
    for msg in messages:
        entry_id = str(msg.get("outlook_entry_id") or msg.get("graph_message_id") or "")
        sender_email = str(msg.get("sender_email") or "")
        subject = str(msg.get("subject") or "")
        fp = _fingerprint(sender_email, subject)
        domain = (sender_email.split("@")[-1] if "@" in sender_email else "").lower() or None
        tokens = _subject_tokens(subject)

        # 2. Upsert into emails table with status=Completed
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

        # 3. Heuristic analysis for base labels
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

        # 4. Claude Sonnet — enhanced labels + property knowledge
        body_redacted, _ = redact_sensitive_text(body_latest)
        claude_result = None
        if settings.anthropic_configured:
            claude_result = extract_with_claude(body_redacted, tokens, settings)
            if claude_result:
                result["labeled"] += 1
            else:
                _log.warning("completed_training_pipeline: Claude failed for email_id=%d, using heuristic", email_id)

        # 5. Build and upload training example
        labels = claude_result if claude_result else dict(heuristic)
        labeling_engine = "claude" if claude_result else "heuristic"
        try:
            example = _build_example(msg, labels, labeling_engine)
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
            _log.info("completed_training_pipeline: uploaded fp=%.12s engine=%s", fp, labeling_engine)
        else:
            log_training_example(email_id, fp, "failed", error, db_path=db_path)
            result["failed"] += 1
            _log.warning("completed_training_pipeline: upload failed email_id=%d: %s", email_id, error)

        # 6. Store property knowledge
        if claude_result:
            n = store_knowledge_items(claude_result, source_email_id=email_id, db_path=db_path)
            result["knowledge_items"] += n

        # 7. Mark as processed
        mark_processed(entry_id, labeling_engine, tokens, domain, db_path=db_path)

    # ── Rebuild PROPERTY_KNOWLEDGE.md ─────────────────────────────────────────
    if result["knowledge_items"] > 0:
        try:
            rebuild_knowledge_file(db_path=db_path)
        except Exception as exc:
            _log.warning("completed_training_pipeline: knowledge file rebuild failed: %s", exc)

    return result


def completed_pipeline_status(db_path: Path | None = None) -> dict[str, Any]:
    """Return counts from the completed_requests_log and property_knowledge_items."""
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
        return {"processed": 0, "knowledge": {}}

    return {
        "processed": int(total_processed),
        "labeled": counts.get("claude", 0) + counts.get("heuristic", 0),
        "failed": counts.get("failed", 0),
        "skipped": counts.get("skipped", 0),
        "knowledge": knowledge,
        "total_knowledge_items": sum(knowledge.values()),
    }

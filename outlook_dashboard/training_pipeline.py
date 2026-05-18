"""Training data pipeline.

Pulls locally-completed emails, redacts PII, labels them using existing
analysis or Claude (for heuristic-only emails when refine=True), then
uploads sanitized training examples to Supabase training_examples table.

PRIVACY CONTRACT
- body_redacted stored in Supabase is always the output of redact_sensitive_text(),
  never the raw body_text.
- sender_email and full subject are never stored; only sender_domain and
  sanitized subject_tokens (stop-word-filtered keywords ≥4 chars).
- Claude labeling is only triggered for emails where analysis_engine='heuristic'
  and only when the caller passes refine=True.

CREDIT USAGE
- Default run (refine=False): zero AI credits. Uses existing email_analysis labels.
- refine=True: one Claude call per heuristic-only email in the batch.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from . import __version__
from .ai import latest_message_text
from .config import get_settings
from .database import (
    get_training_pipeline_status,
    list_unprocessed_completed_emails,
    log_training_example,
)
from .redaction import redact_sensitive_text
from .runtime_log import get_logger
from .taxonomy import CATEGORIES, CONTACT_TYPES, DEPARTMENT_OWNERS, STATUSES

_log = get_logger("training_pipeline")

_STOP_WORDS = {
    "about", "after", "also", "before", "could", "email", "from", "have",
    "just", "make", "message", "need", "needs", "only", "please", "really",
    "should", "that", "their", "there", "this", "what", "when", "with", "would",
}

_LABEL_SYSTEM = (
    "You are a hotel email classifier for the Waldorf Astoria New York Reservations team. "
    "The email body has already been anonymized (PII redacted). "
    "Return ONLY a single valid JSON object — no prose, no markdown."
)

_LABEL_PROMPT = """Classify this anonymized hotel email body for training data.

Return JSON with exactly these keys:
{
  "urgency": <integer 1-5: 1=routine, 3=same-week action needed, 5=same-day critical>,
  "owner": <one of: "Front Desk","Reservations","Concierge","Sales","Housekeeping","Engineering","All Departments">,
  "category": <one of: CATEGORIES>,
  "status": <one of: "New","Reviewed","Drafted","Completed","Escalated">,
  "sentiment": <one of: "Positive","Neutral","Concerned","Upset","Furious">,
  "missing_info": <true or false>,
  "reply_required": <true or false>,
  "escalation_required": <true or false>
}

Email body (anonymized):
"""


def _subject_tokens(subject: str) -> str:
    words = re.findall(r"[a-zA-Z]{4,}", subject or "")
    return " ".join(w.lower() for w in words if w.lower() not in _STOP_WORDS)[:200]


def _fingerprint(sender_email: str, subject: str) -> str:
    domain = (sender_email.split("@")[-1] if "@" in sender_email else sender_email).lower()
    tokens = _subject_tokens(subject)
    return hashlib.sha256(f"{domain}:{tokens}".encode()).hexdigest()


def _label_with_claude(body_redacted: str, settings: Any) -> dict | None:
    """Call Claude with a compact labeling prompt. Returns parsed dict or None."""
    try:
        from anthropic import Anthropic
    except ImportError:
        return None
    prompt = _LABEL_PROMPT.replace("CATEGORIES", ", ".join(f'"{c}"' for c in CATEGORIES))
    client = Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=400,
        system=_LABEL_SYSTEM,
        messages=[{"role": "user", "content": prompt + body_redacted[:3000]}],
    )
    raw = (message.content[0].text or "").strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _upload_example(example: dict) -> tuple[bool, str]:
    """POST example to Supabase training_examples using the service role key."""
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return False, "Supabase not configured"
    try:
        import httpx
    except ImportError:
        return False, "httpx unavailable"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    try:
        with httpx.Client(timeout=10) as client:
            r = client.post(
                f"{url}/rest/v1/training_examples?on_conflict=email_fingerprint",
                json=example,
                headers=headers,
            )
        if r.status_code in (200, 201, 204):
            return True, ""
        return False, f"status={r.status_code} body={r.text[:200]}"
    except Exception as exc:
        return False, str(exc)[:300]


def _build_example(row: dict, labels: dict, labeling_engine: str) -> dict:
    sender_email = str(row.get("sender_email") or "")
    subject = str(row.get("subject") or "")
    domain = (sender_email.split("@")[-1] if "@" in sender_email else "").lower() or None
    tokens = _subject_tokens(subject)
    body_raw = str(row.get("body_text") or "")
    body_latest = latest_message_text(body_raw, max_chars=4000)
    body_redacted, _ = redact_sensitive_text(body_latest)

    _PRIORITY_TO_SCORE = {"Low": 1, "Normal": 2, "High": 4, "Immediate": 5}
    urgency = labels.get("urgency")
    if urgency is None:
        priority_level = labels.get("priority_level") or labels.get("urgency_score")
        if isinstance(priority_level, str) and priority_level in _PRIORITY_TO_SCORE:
            urgency = _PRIORITY_TO_SCORE[priority_level]
        elif isinstance(priority_level, (int, float)):
            urgency = int(priority_level)
    if isinstance(urgency, str):
        try:
            urgency = int(urgency)
        except ValueError:
            urgency = None
    if urgency is not None and not (1 <= urgency <= 5):
        urgency = None
    owner = labels.get("owner") or labels.get("recommended_department_owner")
    category = labels.get("category")
    status = labels.get("status")
    sentiment = labels.get("sentiment") or labels.get("guest_sentiment")
    if owner not in DEPARTMENT_OWNERS:
        owner = None
    if category not in CATEGORIES:
        category = None
    if status not in STATUSES:
        status = None

    return {
        "email_fingerprint": _fingerprint(sender_email, subject),
        "sender_domain": domain,
        "subject_tokens": tokens or None,
        "body_redacted": body_redacted[:4000],
        "label_urgency": urgency,
        "label_owner": owner,
        "label_category": category,
        "label_status": status,
        "label_sentiment": sentiment,
        "label_missing_info": bool(labels.get("missing_info") or labels.get("missing_information")),
        "label_reply_required": bool(labels.get("reply_required")),
        "label_escalation_required": bool(labels.get("escalation_required")),
        "labeling_engine": labeling_engine,
        "human_reviewed": False,
        "app_version": __version__,
    }


def run_pipeline(
    batch_size: int = 10,
    refine: bool = False,
    db_path: Path | None = None,
) -> dict:
    """Run one batch of the training data pipeline.

    Args:
        batch_size: Max emails to process per call (default 10).
        refine: If True, re-label heuristic-only emails with Claude.
                If False (default), use existing email_analysis labels — zero AI cost.
        db_path: Override SQLite path (tests).

    Returns:
        Summary dict: {processed, uploaded, skipped, failed, batch_size, refine}.
    """
    settings = get_settings()
    rows = list_unprocessed_completed_emails(batch_size=batch_size, db_path=db_path)
    result = {"processed": 0, "uploaded": 0, "skipped": 0, "failed": 0,
              "batch_size": batch_size, "refine": refine}

    for row in rows:
        email_id = int(row["id"])
        sender_email = str(row.get("sender_email") or "")
        subject = str(row.get("subject") or "")
        fp = _fingerprint(sender_email, subject)

        body_raw = str(row.get("body_text") or "")
        body_latest = latest_message_text(body_raw, max_chars=4000)
        if len(body_latest.strip()) < 40:
            log_training_example(email_id, fp, "skipped", "body too short", db_path=db_path)
            result["skipped"] += 1
            result["processed"] += 1
            continue

        analysis_engine = str(row.get("analysis_engine") or "heuristic")
        use_claude = refine and analysis_engine == "heuristic" and settings.anthropic_configured

        if use_claude:
            body_redacted, _ = redact_sensitive_text(body_latest)
            claude_labels = _label_with_claude(body_redacted, settings)
            if claude_labels:
                labels = claude_labels
                labeling_engine = "claude"
            else:
                labels = dict(row)
                labeling_engine = analysis_engine
                _log.warning("training_pipeline: Claude labeling failed for email_id=%s, using existing labels", email_id)
        else:
            labels = dict(row)
            labeling_engine = analysis_engine

        try:
            example = _build_example(row, labels, labeling_engine)
        except Exception as exc:
            log_training_example(email_id, fp, "failed", str(exc)[:300], db_path=db_path)
            result["failed"] += 1
            result["processed"] += 1
            _log.warning("training_pipeline: build failed email_id=%s: %s", email_id, exc)
            continue

        ok, error = _upload_example(example)
        if ok:
            log_training_example(email_id, fp, "uploaded", db_path=db_path)
            result["uploaded"] += 1
            _log.info("training_pipeline: uploaded fingerprint=%.12s engine=%s", fp, labeling_engine)
        else:
            log_training_example(email_id, fp, "failed", error, db_path=db_path)
            result["failed"] += 1
            _log.warning("training_pipeline: upload failed email_id=%s: %s", email_id, error)
        result["processed"] += 1

    return result


def pipeline_status(db_path: Path | None = None) -> dict:
    return get_training_pipeline_status(db_path=db_path)

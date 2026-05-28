"""Agent-assisted labeling for Completed Request training emails.

NOT part of the app runtime. Called explicitly by an AI agent (Claude)
when Brian asks to train the classifier. The app's own training endpoints
remain zero-credit and never call external AI. Only this script uses
agent judgment for labeling.

Three phases, run in sequence:

  PHASE 1 — import (run by the agent, requires Outlook open on Windows):
    python scripts/agent_label_completed_requests.py --import
    python scripts/agent_label_completed_requests.py --import --batch-size 200

    Reads unimported Completed Request emails from Outlook. Sanitizes in
    memory (redact PII, keep only safe fields). Writes a sanitized batch
    to labeling/agent_batches/<timestamp>_pending.json. Marks entries in
    the import ledger (completed_requests_log) so they are never re-imported.

    Safe output fields (no raw bodies, no full emails, no message IDs):
      fingerprint   — sha256(domain:subject_tokens), stable dedup key
      sender_domain — e.g. "gmail.com"
      subject_tokens — keyword fragments, not full subject
      body_excerpt   — redacted body, max 800 chars
      received_date  — YYYY-MM-DD date only

  PHASE 2 — label (done by the Claude agent reading the file in-session):
    Read labeling/agent_batches/<timestamp>_pending.json.
    For each entry output a JSON array to labeling/agent_batches/<timestamp>_labeled.json.

    Label schema per entry:
      fingerprint           — copy from pending (required for matching)
      category              — from CATEGORIES taxonomy
      priority_level        — Low | Normal | High | Immediate
      owner                 — from DEPARTMENT_OWNERS taxonomy
      contact_type          — Internal | Group contact | Travel agency | Direct guest
      guest_sentiment       — Positive | Neutral | Concerned | Upset | Furious
      missing_information   — null or short phrase of what is missing
      label_missing_info    — bool
      label_reply_required  — bool
      label_escalation_required — bool
      recommended_action    — from RECOMMENDED_ACTIONS (optional, set null if unsure)
      confidence            — int 0-100 (not written to Supabase, for logging only)
      notes                 — short reasoning string (not written to Supabase)

  PHASE 3 — upload + train + purge (run by the agent after labeling):
    python scripts/agent_label_completed_requests.py \\
        --upload labeling/agent_batches/<timestamp>_pending.json \\
        --labels labeling/agent_batches/<timestamp>_labeled.json

    Reads the sanitized batch and the Claude labels. Builds training examples.
    Uploads to Supabase (labeling_engine="claude-agent", human_reviewed=True).
    Trains the local classifier. Purges raw imported email bodies from SQLite.
    Keeps completed_requests_log intact (deduplication ledger).

Usage examples:
    python scripts/agent_label_completed_requests.py --import --batch-size 500
    python scripts/agent_label_completed_requests.py --upload labeling/agent_batches/20260528T120000Z_pending.json
    python scripts/agent_label_completed_requests.py --status
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from outlook_dashboard.config import _load_env
from outlook_dashboard.taxonomy import (
    CATEGORIES,
    CONTACT_TYPES,
    DEPARTMENT_OWNERS,
    RECOMMENDED_ACTIONS,
)

_load_env()

AGENT_BATCHES_DIR = ROOT / "labeling" / "agent_batches"

_PRIORITY_TO_URGENCY: dict[str, int] = {
    "Low": 1,
    "Normal": 2,
    "High": 4,
    "Immediate": 5,
}

LABELING_INSTRUCTIONS = """\
You are a hotel email classifier for the Waldorf Astoria New York Reservations team.
Each email body has been anonymized (PII redacted). Label each example using your
own judgment. Return ONLY a valid JSON array — no prose, no markdown.

TAXONOMY

Categories (use exactly):
  VIP pre-arrival, Rate inquiry, Billing dispute, Consortia / FHR / Virtuoso,
  Complaint, Amenity request, Accessibility request, Rooming list / group,
  Internal request, Cancellation / modification, Urgent same-day arrival,
  Duplicate follow-up, General inquiry, Credit card authorization

Priority levels:
  Low      — routine, no time pressure, future arrival
  Normal   — standard action needed this week
  High     — action needed within 1-2 days or arrival within a week
  Immediate — same-day arrival, urgent guest issue, legal/medical flag

Department owners:
  Front Office, Reservations, Concierge, Housekeeping, Engineering, Sales

Contact types:
  Internal, Group contact, Travel agency, Guest

Sentiments:
  Positive, Neutral, Concerned, Upset, Furious

Recommended actions (optional — set null if not confident):
  reply_guest, loop_reservations, loop_front_office, loop_concierge,
  loop_housekeeping, loop_engineering, escalate_manager,
  verify_payment_authorization, review_folio, check_reservation,
  request_missing_information, wait_for_guest, wait_for_internal_team,
  no_action_likely

OUTPUT SCHEMA (one object per email in a JSON array):
[
  {
    "fingerprint": "<copy from input>",
    "category": "<from list>",
    "priority_level": "<Low|Normal|High|Immediate>",
    "owner": "<from list>",
    "contact_type": "<from list>",
    "guest_sentiment": "<from list>",
    "missing_information": "<short phrase or null>",
    "label_missing_info": <true|false>,
    "label_reply_required": <true|false>,
    "label_escalation_required": <true|false>,
    "recommended_action": "<from list or null>",
    "confidence": <0-100>,
    "notes": "<optional reasoning, max 200 chars>"
  }
]

RULES
1. Base labels on body_excerpt only — PII has been removed.
2. subject_tokens are keyword fragments, not a full subject line.
3. missing_information: only if genuinely absent and required to act.
4. For Waldorf/Hilton internal senders, set contact_type="Internal".
5. For travel agencies (Virtuoso, FHR, Amex), contact_type="Travel agency".
6. Rooming lists / group blocks -> "Rooming list / group" + owner=Sales.
7. confidence and notes are for quality tracking — not written to Supabase.
"""


# ── Phase 1: Import ───────────────────────────────────────────────────────────

def _fmt_list(values: list[str]) -> str:
    return "\n".join(f"  {value}" for value in values)


# Keep the label prompt tied to the active app taxonomy. The earlier draft
# string is overridden here so new pending batches cannot drift from taxonomy.py.
LABELING_INSTRUCTIONS = f"""\
You are a hotel email classifier for the Waldorf Astoria New York Reservations team.
Each email body has been anonymized. Label each example using your own outside-agent model judgment.
Return ONLY a valid JSON array; no prose, no markdown.

TAXONOMY

Categories (use exactly):
{_fmt_list(CATEGORIES)}

Priority levels:
  Low - routine, no time pressure, future arrival
  Normal - standard action needed this week
  High - action needed within 1-2 days or arrival within a week
  Immediate - same-day arrival, urgent guest issue, legal/medical flag

Department owners:
{_fmt_list(DEPARTMENT_OWNERS)}

Contact types:
{_fmt_list(CONTACT_TYPES)}

Sentiments:
  Positive, Neutral, Concerned, Upset, Furious

Recommended actions (optional; set null if not confident):
{_fmt_list(RECOMMENDED_ACTIONS)}

OUTPUT SCHEMA (one object per email in a JSON array):
[
  {{
    "fingerprint": "<copy from input>",
    "category": "<from category list>",
    "priority_level": "<Low|Normal|High|Immediate>",
    "owner": "<from department owner list>",
    "contact_type": "<from contact type list>",
    "guest_sentiment": "<from sentiment list>",
    "missing_information": "<short phrase or null>",
    "label_missing_info": <true|false>,
    "label_reply_required": <true|false>,
    "label_escalation_required": <true|false>,
    "recommended_action": "<from list or null>",
    "confidence": <0-100>,
    "notes": "<optional reasoning, max 200 chars>"
  }}
]

RULES
1. Base labels on body_excerpt only; PII has been removed.
2. subject_tokens are keyword fragments, not a full subject line.
3. missing_information is only for information genuinely absent and required to act.
4. For Waldorf/Hilton internal senders, set contact_type="Internal".
5. For travel agencies (Virtuoso, FHR, Amex), set contact_type="Travel agency".
6. Rooming lists / group blocks usually map to "Rooming list / group" and owner="Sales".
7. The app heuristic labels are reference only; you are the final labeler.
8. confidence and notes are for quality tracking; they are not written to Supabase.
"""


def phase_import(
    mailbox_name: str,
    folder_name: str,
    batch_size: int,
    db_path: Path | None,
) -> Path | None:
    """Import unimported Completed Request emails and write sanitized batch."""
    from outlook_dashboard.ai import latest_message_text
    from outlook_dashboard.completed_requests_importer import (
        mark_processed,
        read_completed_requests,
    )
    from outlook_dashboard.redaction import redact_sensitive_text
    from outlook_dashboard.training_pipeline import _fingerprint, _subject_tokens

    print(f"Importing from mailbox={mailbox_name!r} folder={folder_name!r} batch_size={batch_size}")
    try:
        result = read_completed_requests(
            mailbox_name=mailbox_name,
            folder_name=folder_name,
            batch_size=batch_size,
            db_path=db_path,
        )
    except Exception as exc:
        print(f"ERROR: Import failed: {exc}", file=sys.stderr)
        return None

    messages = result.get("messages") or []
    checked = result.get("checked_count", 0)
    print(f"Checked {checked} emails in folder, found {len(messages)} not yet imported.")

    if not messages:
        print("Nothing to label. Exiting.")
        return None

    examples: list[dict[str, Any]] = []
    for msg in messages:
        entry_id = str(msg.get("outlook_entry_id") or msg.get("graph_message_id") or "")
        sender_email = str(msg.get("sender_email") or "")
        subject = str(msg.get("subject") or "")

        domain = (sender_email.split("@")[-1] if "@" in sender_email else "").lower() or None
        tokens = _subject_tokens(subject)
        fingerprint = _fingerprint(sender_email, subject)

        body_raw = str(msg.get("body_text") or msg.get("body_content") or "")
        body_latest = latest_message_text(body_raw, max_chars=4000)
        body_redacted, _ = redact_sensitive_text(body_latest)

        received_raw = str(msg.get("received_at") or "")
        received_date = received_raw[:10] if received_raw else ""

        examples.append({
            "fingerprint": fingerprint,
            "sender_domain": domain,
            "subject_tokens": tokens or None,
            "body_excerpt": body_redacted[:800],
            "received_date": received_date,
        })

        # Mark in ledger immediately — prevents re-import on any subsequent run
        if entry_id:
            mark_processed(entry_id, "agent_pending", tokens, domain, db_path=db_path)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    AGENT_BATCHES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AGENT_BATCHES_DIR / f"{ts}_pending.json"

    batch = {
        "schema_version": 1,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "mailbox": mailbox_name,
        "folder": folder_name,
        "count": len(examples),
        "labeling_instructions": LABELING_INSTRUCTIONS,
        "examples": examples,
    }
    out_path.write_text(json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8")

    labels_path = AGENT_BATCHES_DIR / f"{ts}_labeled.json"

    print(f"\nWrote {len(examples)} sanitized examples -> {out_path.relative_to(ROOT)}")
    print()
    print("NEXT STEPS:")
    print("  1. Read the pending batch file above.")
    print("  2. Assign labels for each entry (see labeling_instructions inside the file).")
    print(f"  3. Write your labeled JSON array to: {labels_path.relative_to(ROOT)}")
    print("  4. Run:")
    print(f"     python scripts/agent_label_completed_requests.py \\")
    print(f"         --upload {out_path} \\")
    print(f"         --labels {labels_path}")

    return out_path


# ── Phase 3: Upload + Train + Purge ──────────────────────────────────────────

def phase_upload(
    pending_path: Path,
    labels_path: Path,
    db_path: Path | None,
    skip_train: bool = False,
    skip_purge: bool = False,
) -> dict[str, Any]:
    """Upload Claude-labeled examples to Supabase, train classifier, purge raw bodies."""
    from outlook_dashboard import __version__
    from outlook_dashboard.completed_training_pipeline import purge_processed_training_emails
    from outlook_dashboard.local_classifier import train as train_classifier
    from outlook_dashboard.training_pipeline import _upload_example

    # Load inputs
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    labels_raw = json.loads(labels_path.read_text(encoding="utf-8"))

    if not isinstance(labels_raw, list):
        print("ERROR: Labels file must be a JSON array.", file=sys.stderr)
        sys.exit(1)

    examples_by_fp: dict[str, dict] = {
        e["fingerprint"]: e for e in pending.get("examples", [])
    }

    stats: dict[str, int] = {"uploaded": 0, "skipped": 0, "failed": 0}
    run_log: list[dict] = []

    print(f"Uploading {len(labels_raw)} labeled examples to Supabase...")

    for label in labels_raw:
        fp = str(label.get("fingerprint") or label.get("email_fingerprint") or "")
        if not fp:
            print("  WARNING: entry missing fingerprint — skipping.", file=sys.stderr)
            stats["skipped"] += 1
            continue

        meta = examples_by_fp.get(fp, {})
        priority = str(label.get("priority_level") or "Normal")
        urgency = _PRIORITY_TO_URGENCY.get(priority, 2)
        category = str(label.get("category") or "")
        owner = str(label.get("owner") or "")
        contact_type = label.get("contact_type")
        recommended_action = label.get("recommended_action")

        if category not in CATEGORIES:
            print(f"  WARNING: invalid category for {fp[:12]} - skipping.", file=sys.stderr)
            stats["skipped"] += 1
            continue
        if owner not in DEPARTMENT_OWNERS:
            print(f"  WARNING: invalid owner for {fp[:12]} - skipping.", file=sys.stderr)
            stats["skipped"] += 1
            continue
        if contact_type and str(contact_type) not in CONTACT_TYPES:
            print(f"  WARNING: invalid contact_type for {fp[:12]} - skipping.", file=sys.stderr)
            stats["skipped"] += 1
            continue
        if recommended_action and str(recommended_action) not in RECOMMENDED_ACTIONS:
            print(f"  WARNING: invalid recommended_action for {fp[:12]} - skipping.", file=sys.stderr)
            stats["skipped"] += 1
            continue

        missing_info_val = label.get("missing_information")
        label_missing = bool(
            label.get("label_missing_info")
            or (missing_info_val and str(missing_info_val).strip() not in ("", "null", "None"))
        )

        record: dict[str, Any] = {
            "email_fingerprint": fp,
            "sender_domain": meta.get("sender_domain"),
            "subject_tokens": meta.get("subject_tokens"),
            "body_redacted": (meta.get("body_excerpt") or "")[:4000],
            "label_urgency": urgency,
            "label_owner": owner,
            "label_category": category,
            "label_status": label.get("status") or "Completed",
            "label_sentiment": label.get("guest_sentiment") or None,
            "label_missing_info": label_missing,
            "label_reply_required": bool(label.get("label_reply_required")),
            "label_escalation_required": bool(label.get("label_escalation_required")),
            "labeling_engine": "claude-agent",
            "human_reviewed": True,
            "app_version": __version__,
        }

        ok, error = _upload_example(record)
        if ok:
            stats["uploaded"] += 1
            run_log.append({"fingerprint": fp[:12], "status": "ok"})
        else:
            stats["failed"] += 1
            run_log.append({"fingerprint": fp[:12], "status": "failed", "error": error})
            print(f"  FAILED {fp[:12]}: {error}", file=sys.stderr)

    print(f"\nUpload complete: {stats['uploaded']} uploaded, {stats['failed']} failed, {stats['skipped']} skipped.")

    # Write run log
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs_dir = ROOT / "labeling" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    log_path = runs_dir / f"agent_{ts}.json"
    log_path.write_text(
        json.dumps({"pending_batch": str(pending_path), "labels_file": str(labels_path),
                    "stats": stats, "rows": run_log}, indent=2),
        encoding="utf-8",
    )
    print(f"Run log: {log_path.relative_to(ROOT)}")

    # Train
    if not skip_train and stats["uploaded"] > 0:
        print("\nTraining local classifier from Supabase examples...")
        train_result = train_classifier(db_path=db_path)
        _print_train_result(train_result)
    elif stats["uploaded"] == 0:
        print("\nNo examples uploaded — skipping classifier training.")

    # Purge
    if not skip_purge:
        print("\nPurging raw imported email bodies from SQLite...")
        purge = purge_processed_training_emails(db_path=db_path)
        print(f"Purged: {purge['deleted_rows']} email rows, {purge['deleted_files']} export files.")
        print("Import ledger (completed_requests_log) preserved for deduplication.")

    return {**stats, "log": str(log_path)}


# ── Status ────────────────────────────────────────────────────────────────────

def phase_status(db_path: Path | None) -> None:
    """Print import ledger counts and classifier status."""
    from outlook_dashboard.completed_training_pipeline import completed_pipeline_status
    from outlook_dashboard.local_classifier import get_classifier_status

    pipeline = completed_pipeline_status(db_path=db_path)
    print("=== Import ledger (completed_requests_log) ===")
    for k, v in pipeline.items():
        if k != "knowledge":
            print(f"  {k}: {v}")

    print()
    print("=== Local classifier ===")
    try:
        clf = get_classifier_status(db_path=db_path)
        for k, v in clf.items():
            print(f"  {k}: {v}")
    except Exception as exc:
        print(f"  (classifier status unavailable: {exc})")

    print()
    print("=== Pending batch files ===")
    if AGENT_BATCHES_DIR.exists():
        batch_files = sorted(AGENT_BATCHES_DIR.glob("*_pending.json"))
        if batch_files:
            for f in batch_files:
                labeled = f.parent / f.name.replace("_pending.json", "_labeled.json")
                status = "LABELED" if labeled.exists() else "AWAITING LABELS"
                print(f"  {f.name} — {status}")
        else:
            print("  (none)")
    else:
        print("  (labeling/agent_batches/ does not exist yet)")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_train_result(result: dict) -> None:
    if not result.get("trained"):
        print(f"  Classifier not trained: {result.get('reason', 'unknown')}")
        return
    print(f"  Trained on {result.get('examples', '?')} examples.")
    accuracy = result.get("accuracy") or {}
    distributions = result.get("label_distributions") or {}
    for name in result.get("targets", []):
        acc = accuracy.get(name)
        n = sum((distributions.get(name) or {}).values()) or "?"
        if acc is not None and acc >= 0:
            print(f"    {name}: {acc:.1%} CV accuracy ({n} rows)")
        else:
            print(f"    {name}: {n} rows (accuracy unavailable)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent-assisted labeling for Completed Request training emails.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--import", dest="do_import", action="store_true",
                       help="Phase 1: import and sanitize emails from Outlook.")
    group.add_argument("--upload", type=Path, metavar="PENDING_BATCH",
                       help="Phase 3: upload Claude labels, train, purge.")
    group.add_argument("--status", action="store_true",
                       help="Print ledger and classifier status.")

    parser.add_argument("--labels", type=Path, metavar="LABELS_FILE",
                        help="Path to the labeled JSON file (required with --upload).")
    parser.add_argument("--mailbox", default=os.getenv("OUTLOOK_EXPORT_MAILBOX", "NYCWA_Reservations"),
                        help="Outlook mailbox name (default: $OUTLOOK_EXPORT_MAILBOX).")
    parser.add_argument("--folder", default="Completed Request",
                        help='Outlook folder name (default: "Completed Request").')
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Max emails to import per run (default: 500).")
    parser.add_argument("--skip-train", action="store_true",
                        help="Skip classifier training after upload.")
    parser.add_argument("--skip-purge", action="store_true",
                        help="Skip raw body purge after upload.")

    args = parser.parse_args()

    from outlook_dashboard.config import get_settings
    db_path = get_settings().database_path

    if args.do_import:
        phase_import(
            mailbox_name=args.mailbox,
            folder_name=args.folder,
            batch_size=args.batch_size,
            db_path=db_path,
        )

    elif args.upload:
        pending_path: Path = args.upload.resolve()
        if not pending_path.exists():
            print(f"ERROR: Pending batch file not found: {pending_path}", file=sys.stderr)
            sys.exit(1)

        # Auto-derive labels path from pending path if not given
        if args.labels:
            labels_path = args.labels.resolve()
        else:
            labels_path = pending_path.parent / pending_path.name.replace("_pending.json", "_labeled.json")

        if not labels_path.exists():
            print(f"ERROR: Labels file not found: {labels_path}", file=sys.stderr)
            print("  Label the pending batch file first, then re-run with --labels.", file=sys.stderr)
            sys.exit(1)

        phase_upload(
            pending_path=pending_path,
            labels_path=labels_path,
            db_path=db_path,
            skip_train=args.skip_train,
            skip_purge=args.skip_purge,
        )

    elif args.status:
        phase_status(db_path=db_path)


if __name__ == "__main__":
    main()

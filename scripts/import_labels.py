"""Import and reconcile Claude + ChatGPT label files.

Scans labeling/Claude/ for a file matching the target date and
labeling/ChatGPT/ for a file matching the target date, joins on
training_example_id, applies agreement logic, and updates Supabase.

Claude files: flat labeler format (category, priority_level, …)
ChatGPT files: critic format (agrees_with_claude, corrected_labels, …)
              OR flat labeler format — both are handled automatically.

Agreement logic (6 compared fields: category, priority_level, owner,
contact_type, guest_sentiment, missing_information):
  - 6/6 match  -> dual_labeled: write labels, set human_reviewed=true,
                  labeling_engine='dual_labeled'
  - 4-5/6 match -> partial: write agreed fields, push to human-review
                  queue (human_reviewed stays false),
                  labeling_engine='partial_agreement'
  - <=3/6 match -> human-review only: do not write labels,
                  labeling_engine='needs_full_review'

Writes a JSON run log to labeling/runs/{timestamp}.json.
Prints a summary: processed / dual_labeled / partial / to-review.

Usage:
    python scripts/import_labels.py
    python scripts/import_labels.py --date 2026-05-18
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from outlook_dashboard.config import _load_env

_load_env()

_COMPARE_FIELDS = [
    "category",
    "priority_level",
    "owner",
    "contact_type",
    "guest_sentiment",
    "missing_information",
]

_PRIORITY_TO_URGENCY = {"Low": 1, "Normal": 2, "High": 4, "Immediate": 5}


def _date_variants(date_str: str) -> list[str]:
    """Return common filename variants for a date string (hyphen and underscore)."""
    return [date_str, date_str.replace("-", "_")]


def _find_date_file(folder: Path, date_str: str) -> Path | None:
    """Return the first file in folder whose stem contains the date (any separator)."""
    if not folder.is_dir():
        return None
    variants = _date_variants(date_str)
    for f in sorted(folder.iterdir()):
        if not f.suffix.lower() == ".json":
            continue
        stem = f.stem.lower()
        for v in variants:
            if v.replace("-", "").replace("_", "") in stem.replace("-", "").replace("_", ""):
                return f
    return None


def _load_json_file(path: Path) -> list[dict]:
    if not path or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        print(f"WARNING: {path} is not a JSON array — skipping.", file=sys.stderr)
        return []
    except json.JSONDecodeError as exc:
        print(f"WARNING: Could not parse {path}: {exc}", file=sys.stderr)
        return []


def _is_critic_format(row: dict) -> bool:
    """Detect ChatGPT critic format (has agrees_with_claude key)."""
    return "agrees_with_claude" in row


def _normalize_critic_to_labels(critic_row: dict, claude_row: dict) -> dict:
    """Flatten ChatGPT critic format into a comparable label dict.

    For each field ChatGPT agrees on, adopts Claude's value.
    For each field ChatGPT disagrees on, uses the corrected value.
    """
    agrees = critic_row.get("agrees_with_claude") or {}
    corrected = critic_row.get("corrected_labels") or {}
    out: dict[str, Any] = {"training_example_id": critic_row.get("training_example_id", "")}
    for field in _COMPARE_FIELDS:
        if agrees.get(field, True):
            out[field] = claude_row.get(field)
        else:
            out[field] = corrected.get(field)
    return out


def _count_agreements(a: dict, b: dict) -> tuple[int, list[str], list[str]]:
    """Return (matched_count, agreed_fields, disagreed_fields)."""
    agreed: list[str] = []
    disagreed: list[str] = []
    for field in _COMPARE_FIELDS:
        va = a.get(field)
        vb = b.get(field)
        if isinstance(va, str):
            va = va.strip()
        if isinstance(vb, str):
            vb = vb.strip()
        if va == vb:
            agreed.append(field)
        else:
            disagreed.append(field)
    return len(agreed), agreed, disagreed


def _build_update(source: dict, agreed_fields: list[str]) -> dict:
    """Build the Supabase PATCH body from agreed label fields."""
    update: dict[str, Any] = {}
    for field in agreed_fields:
        val = source.get(field)
        if field == "category":
            update["label_category"] = val
        elif field == "priority_level":
            update["label_urgency"] = _PRIORITY_TO_URGENCY.get(str(val), None)
        elif field == "owner":
            update["label_owner"] = val
        elif field == "contact_type":
            update["label_contact_type"] = val
        elif field == "guest_sentiment":
            update["label_sentiment"] = val
        elif field == "missing_information":
            update["label_missing_info"] = val is not None and str(val).strip() != ""
    return update


def _patch_example(training_id: str, update: dict) -> tuple[bool, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return False, "Supabase not configured"
    try:
        import httpx
    except ImportError:
        return False, "httpx not installed"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    try:
        with httpx.Client(timeout=15) as client:
            r = client.patch(
                f"{url}/rest/v1/training_examples",
                params={"id": f"eq.{training_id}"},
                json=update,
                headers=headers,
            )
        if r.status_code in (200, 204):
            return True, ""
        return False, f"status={r.status_code} body={r.text[:200]}"
    except Exception as exc:
        return False, str(exc)[:300]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and reconcile labeling results.")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Date to import (YYYY-MM-DD, default today).",
    )
    args = parser.parse_args()

    claude_dir = ROOT / "labeling" / "Claude"
    chatgpt_dir = ROOT / "labeling" / "ChatGPT"

    claude_path = _find_date_file(claude_dir, args.date)
    chatgpt_path = _find_date_file(chatgpt_dir, args.date)

    if not claude_path and not chatgpt_path:
        print(f"No label files found for {args.date}.")
        print(f"  Searched: {claude_dir}/ and {chatgpt_dir}/")
        return

    if claude_path:
        print(f"Claude labels:  {claude_path.relative_to(ROOT)}")
    if chatgpt_path:
        print(f"ChatGPT labels: {chatgpt_path.relative_to(ROOT)}")

    claude_rows = _load_json_file(claude_path)
    chatgpt_rows_raw = _load_json_file(chatgpt_path)

    # Index Claude labels by ID
    claude_idx: dict[str, dict] = {r["training_example_id"]: r for r in claude_rows if r.get("training_example_id")}

    # Normalize ChatGPT rows — critic format or flat format
    chatgpt_idx: dict[str, dict] = {}
    for row in chatgpt_rows_raw:
        tid = row.get("training_example_id")
        if not tid:
            continue
        if _is_critic_format(row):
            claude_ref = claude_idx.get(tid, {})
            chatgpt_idx[tid] = _normalize_critic_to_labels(row, claude_ref)
        else:
            chatgpt_idx[tid] = row

    all_ids = set(claude_idx) | set(chatgpt_idx)

    if not all_ids:
        print("No valid training_example_id entries found in either file.")
        return

    stats = {"processed": 0, "dual_labeled": 0, "partial": 0, "needs_review": 0, "errors": 0}
    run_log: list[dict] = []

    for tid in sorted(all_ids):
        c_row = claude_idx.get(tid)
        g_row = chatgpt_idx.get(tid)

        if not c_row or not g_row:
            present = "claude" if c_row else "chatgpt"
            update = {"labeling_engine": "needs_full_review"}
            ok, err = _patch_example(tid, update)
            run_log.append({
                "training_example_id": tid,
                "outcome": "needs_review",
                "reason": f"only {present} label present",
                "supabase_ok": ok,
                "error": err or None,
            })
            stats["processed"] += 1
            stats["needs_review"] += 1
            if not ok:
                stats["errors"] += 1
            continue

        match_count, agreed_fields, disagreed_fields = _count_agreements(c_row, g_row)

        if match_count == 6:
            update = _build_update(c_row, agreed_fields)
            update["labeling_engine"] = "dual_labeled"
            update["human_reviewed"] = True
            ok, err = _patch_example(tid, update)
            run_log.append({
                "training_example_id": tid,
                "outcome": "dual_labeled",
                "agreed_fields": agreed_fields,
                "supabase_ok": ok,
                "error": err or None,
            })
            stats["processed"] += 1
            stats["dual_labeled"] += 1
            if not ok:
                stats["errors"] += 1

        elif match_count >= 4:
            update = _build_update(c_row, agreed_fields)
            update["labeling_engine"] = "partial_agreement"
            ok, err = _patch_example(tid, update)
            run_log.append({
                "training_example_id": tid,
                "outcome": "partial",
                "agreed_fields": agreed_fields,
                "disagreed_fields": disagreed_fields,
                "claude_labels": {f: c_row.get(f) for f in disagreed_fields},
                "chatgpt_labels": {f: g_row.get(f) for f in disagreed_fields},
                "supabase_ok": ok,
                "error": err or None,
            })
            stats["processed"] += 1
            stats["partial"] += 1
            if not ok:
                stats["errors"] += 1

        else:
            update = {"labeling_engine": "needs_full_review"}
            ok, err = _patch_example(tid, update)
            run_log.append({
                "training_example_id": tid,
                "outcome": "needs_review",
                "agreed_fields": agreed_fields,
                "disagreed_fields": disagreed_fields,
                "claude_labels": {f: c_row.get(f) for f in _COMPARE_FIELDS},
                "chatgpt_labels": {f: g_row.get(f) for f in _COMPARE_FIELDS},
                "supabase_ok": ok,
                "error": err or None,
            })
            stats["processed"] += 1
            stats["needs_review"] += 1
            if not ok:
                stats["errors"] += 1

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs_dir = ROOT / "labeling" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    log_path = runs_dir / f"{ts}.json"
    log_path.write_text(json.dumps({"date": args.date, "stats": stats, "rows": run_log}, indent=2), encoding="utf-8")

    print(f"\nImport complete — {args.date}")
    print(f"  Processed:    {stats['processed']}")
    print(f"  Dual-labeled: {stats['dual_labeled']}")
    print(f"  Partial:      {stats['partial']}")
    print(f"  To review:    {stats['needs_review']}")
    if stats["errors"]:
        print(f"  Supabase errors: {stats['errors']}")
    print(f"  Run log:      {log_path}")


if __name__ == "__main__":
    main()

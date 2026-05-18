"""Export unreviewed training examples for human labeling.

Pulls rows from Supabase training_examples WHERE human_reviewed=false,
formats them as a numbered Markdown batch, writes to labeling/exports/,
and copies to clipboard (if pyperclip is available).

Usage:
    python scripts/export_for_labeling.py
    python scripts/export_for_labeling.py --count 20 --no-skip-reviewed
    python scripts/export_for_labeling.py --output labeling/exports/custom.md
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from outlook_dashboard.config import _load_env

_load_env()


def _fetch_examples(count: int, skip_reviewed: bool) -> list[dict]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required.", file=sys.stderr)
        sys.exit(1)

    try:
        import httpx
    except ImportError:
        print("ERROR: httpx not installed.", file=sys.stderr)
        sys.exit(1)

    params: dict[str, str] = {
        "select": "id,sender_domain,subject_tokens,body_redacted,created_at",
        "order": "created_at.asc",
        "limit": str(count),
    }
    if skip_reviewed:
        params["human_reviewed"] = "eq.false"

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(f"{url}/rest/v1/training_examples", params=params, headers=headers)
        if r.status_code != 200:
            print(f"ERROR: Supabase returned {r.status_code}: {r.text[:300]}", file=sys.stderr)
            sys.exit(1)
        return r.json()
    except Exception as exc:
        print(f"ERROR fetching from Supabase: {exc}", file=sys.stderr)
        sys.exit(1)


def _format_markdown(rows: list[dict], today: str) -> str:
    count = len(rows)
    lines: list[str] = [
        f"# ReplyRight Labeling Batch — {today}",
        f"**Total emails:** {count}",
        "",
        "---",
        "",
    ]

    for i, row in enumerate(rows, start=1):
        training_id = row.get("id", "")
        domain = row.get("sender_domain") or "(unknown)"
        tokens = row.get("subject_tokens") or "(no subject)"
        created = (row.get("created_at") or "")[:10]
        body = (row.get("body_redacted") or "").strip()

        lines += [
            f"## Email {i}",
            f"[ID: {training_id}]",
            f"**Subject tokens:** {tokens}",
            f"**From domain:** {domain}",
            f"**Date:** {created}",
            "",
            "**Body (redacted):**",
            "",
            body,
            "",
            "---",
            "",
        ]

    lines += [
        "**Reply with a JSON array. One object per email.**",
        "Schema in LABELING_PROMPTS.md section 1.",
    ]

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export training examples for labeling.")
    parser.add_argument("--count", type=int, default=30, help="Number of emails to export (default 30).")
    parser.add_argument(
        "--skip-reviewed",
        dest="skip_reviewed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip already-reviewed examples (default: True).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: labeling/exports/YYYY-MM-DD.md).",
    )
    args = parser.parse_args()

    today = date.today().isoformat()
    out_path: Path = args.output or (ROOT / "labeling" / "exports" / f"{today}.md")

    rows = _fetch_examples(args.count, args.skip_reviewed)
    if not rows:
        print("No unreviewed training examples found in Supabase.")
        return

    md = _format_markdown(rows, today)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"Wrote {len(rows)} emails → {out_path}")

    try:
        import pyperclip  # type: ignore[import]
        pyperclip.copy(md)
        print("Copied to clipboard.")
    except Exception:
        print("(Clipboard unavailable — paste from the file above.)")


if __name__ == "__main__":
    main()

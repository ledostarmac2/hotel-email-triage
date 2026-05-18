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


_LABELING_INSTRUCTIONS = """\
---

## Labeling Instructions

You are a hotel email classifier for the Waldorf Astoria New York Reservations team. Label each email above with the fields below. \
Return ONLY a valid JSON array — no prose, no markdown fences, no explanation.

### TAXONOMY

**Categories:** VIP pre-arrival, Rate inquiry, Billing dispute, Consortia / FHR / Virtuoso, Complaint, Amenity request, \
Accessibility request, Rooming list / group, Internal request, Cancellation / modification, Urgent same-day arrival, \
Duplicate follow-up, General inquiry

**Priority levels:**
- Low — routine, no time pressure, future arrival
- Normal — standard action needed this week
- High — action needed within 1-2 days or arrival within a week
- Immediate — same-day arrival, urgent guest issue, legal/medical flag

**Department owners:** Front Desk, Reservations, Concierge, Sales, Housekeeping, Engineering, All Departments

**Contact types:** Internal, Group contact, Travel agency, Direct guest

**Guest sentiments:** Positive, Neutral, Concerned, Upset, Furious

### URGENCY RULES

- Arrival today or tomorrow -> Immediate
- Arrival within 2-7 days -> High
- Arrival same month (>7 days away) -> Normal
- Arrival same year, different month -> Low or Normal
- Arrival next year or beyond -> Low
- Any legal threat, medical emergency, ADA urgent need, or Furious sentiment -> Immediate regardless of arrival date
- Completion updates (CCA form signed, task confirmed done) may lower urgency one level

### OUTPUT SCHEMA

```json
[
  {
    "training_example_id": "<UUID from [ID: ...] in the email>",
    "category": "<from category list>",
    "priority_level": "<Low|Normal|High|Immediate>",
    "owner": "<from department owner list>",
    "contact_type": "<from contact type list>",
    "guest_sentiment": "<from sentiment list>",
    "missing_information": "<short phrase describing what is missing to act, or null>",
    "confidence": <integer 0-100>,
    "notes": "<optional reasoning max 200 chars, or empty string>"
  }
]
```

### LABELING RULES

1. Base labels on the **body (redacted)** only — PII has been removed, do not infer it.
2. Subject tokens are keyword fragments, not a full subject line.
3. `missing_information`: short phrase (e.g. "arrival date", "room type") only if genuinely absent and required to act. Set null if not missing.
4. For travel agencies (Virtuoso, FHR, Amex, consortia), default `contact_type` to "Travel agency".
5. For Waldorf/Hilton internal senders, set `contact_type` to "Internal" and `owner` to the best-match department.
6. Rooming lists and group block emails -> "Rooming list / group" + owner = Sales.
7. `confidence` and `notes` are for quality tracking only — not written to the database.
"""


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

    lines.append(_LABELING_INSTRUCTIONS)

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
    print(f"Wrote {len(rows)} emails -> {out_path}")

    try:
        import pyperclip  # type: ignore[import]
        pyperclip.copy(md)
        print("Copied to clipboard.")
    except Exception:
        print("(Clipboard unavailable — paste from the file above.)")


if __name__ == "__main__":
    main()

"""Property-specific knowledge extraction and persistence.

Uses Claude Sonnet to analyze anonymized completed hotel email requests and
extract both classification training labels AND Waldorf Astoria-specific
knowledge: room types, rate plans, packages, offers, department SOPs.

PRIVACY CONTRACT
- Only operates on body_redacted (never raw body_text).
- Only receives subject_tokens (never full subject).
- No sender name, email address, or reservation numbers passed to Claude.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .runtime_log import get_logger
from .taxonomy import CATEGORIES, DEPARTMENT_OWNERS

_log = get_logger("property_knowledge")

_TRAINING_DIR = Path(__file__).resolve().parent.parent / "training"
_KNOWLEDGE_FILE = _TRAINING_DIR / "PROPERTY_KNOWLEDGE.md"

_KNOWLEDGE_TYPES = ("room_type", "rate_plan", "package", "offer", "sop", "routing")

_CR_SYSTEM = (
    "You are a hotel intelligence extractor for the Waldorf Astoria New York Reservations team. "
    "Analyze completed email requests to extract training labels and property knowledge. "
    "The email body has been anonymized — no raw PII, just redacted text and subject keywords. "
    "Return ONLY a single valid JSON object. No prose, no markdown fences."
)

_CR_PROMPT = """Analyze this completed hotel reservation email. Return training labels AND property knowledge.

TRAINING LABELS:
  urgency: 1-5  (1=routine, 3=same-week action, 5=same-day critical)
  owner: one of {owners}
  category: one of {categories}
  sentiment: "Positive" | "Neutral" | "Concerned" | "Upset" | "Furious"
  missing_info: true | false
  reply_required: true | false
  escalation_required: true | false

PROPERTY KNOWLEDGE (extract what is mentioned — empty list if nothing relevant):
  room_types: room category names (e.g. "Presidential Suite", "Deluxe King", "Tower Suite")
  rate_plans: rate codes or plan names (e.g. "FHR", "Virtuoso", "AAA", "corporate rate", "group rate")
  packages: package or bundle names (e.g. "honeymoon package", "Towers Experience", "early check-in package")
  offers: special offers or promotions (e.g. "complimentary upgrade offer", "welcome amenity")
  department_routing_reason: one sentence — why this type of email routes to this department
  handling_pattern: null OR a brief property SOP note inferred from context (e.g. "VIP arrivals: alert concierge 24h prior and confirm suite setup")

Return this exact JSON schema:
{{
  "urgency": <int 1-5>,
  "owner": <str>,
  "category": <str>,
  "sentiment": <str>,
  "missing_info": <bool>,
  "reply_required": <bool>,
  "escalation_required": <bool>,
  "room_types": [<str>, ...],
  "rate_plans": [<str>, ...],
  "packages": [<str>, ...],
  "offers": [<str>, ...],
  "department_routing_reason": <str>,
  "handling_pattern": <str or null>
}}

Subject keywords: {subject_tokens}
Body (anonymized):
"""


def extract_with_claude(
    body_redacted: str,
    subject_tokens: str,
    settings: Any,
) -> dict[str, Any] | None:
    """Call Claude Sonnet to extract training labels + property knowledge.

    Returns parsed dict on success, None on failure.
    All inputs must be pre-sanitized (no raw PII).
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        _log.warning("property_knowledge: anthropic package not installed")
        return None

    prompt = _CR_PROMPT.format(
        owners=", ".join(f'"{o}"' for o in DEPARTMENT_OWNERS),
        categories=", ".join(f'"{c}"' for c in CATEGORIES),
        subject_tokens=subject_tokens or "(none)",
    )

    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=_CR_SYSTEM,
            messages=[{"role": "user", "content": prompt + body_redacted[:3500]}],
        )
    except Exception as exc:
        _log.warning("property_knowledge: Claude call failed: %s", exc)
        return None

    raw = (message.content[0].text or "").strip() if message.content else ""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        _log.warning("property_knowledge: no JSON in Claude response")
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        _log.warning("property_knowledge: JSON parse failed: %s", exc)
        return None


def store_knowledge_items(
    result: dict[str, Any],
    source_email_id: int | None = None,
    db_path: Path | None = None,
) -> int:
    """Persist extracted property knowledge items to the database.

    Returns the number of items upserted.
    """
    from .database import managed_connect

    items: list[tuple[str, str, str | None]] = []

    for room in result.get("room_types") or []:
        if room and len(room) < 120:
            items.append(("room_type", room, None))

    for plan in result.get("rate_plans") or []:
        if plan and len(plan) < 120:
            items.append(("rate_plan", plan, None))

    for pkg in result.get("packages") or []:
        if pkg and len(pkg) < 200:
            items.append(("package", pkg, None))

    for offer in result.get("offers") or []:
        if offer and len(offer) < 200:
            items.append(("offer", offer, None))

    reason = (result.get("department_routing_reason") or "").strip()
    if reason:
        owner = result.get("owner", "")
        items.append(("routing", f"{owner}: {reason}"[:300], None))

    pattern = (result.get("handling_pattern") or "").strip()
    if pattern and len(pattern) > 10:
        items.append(("sop", pattern[:500], None))

    if not items:
        return 0

    from .text_utils import utc_now_iso

    now = utc_now_iso()
    count = 0
    try:
        with managed_connect(db_path) as db:
            for item_type, item_value, item_context in items:
                db.execute(
                    """
                    INSERT INTO property_knowledge_items
                        (item_type, item_value, item_context, source_email_id,
                         occurrence_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(item_type, item_value)
                    DO UPDATE SET
                        occurrence_count = occurrence_count + 1,
                        updated_at = excluded.updated_at
                    """,
                    (item_type, item_value, item_context, source_email_id, now, now),
                )
                count += 1
    except Exception as exc:
        _log.warning("property_knowledge: db write failed: %s", exc)
    return count


def rebuild_knowledge_file(db_path: Path | None = None) -> None:
    """Rewrite training/PROPERTY_KNOWLEDGE.md from current DB contents."""
    from .database import managed_connect

    try:
        with managed_connect(db_path) as db:
            rows = db.execute(
                """
                SELECT item_type, item_value, occurrence_count
                FROM property_knowledge_items
                ORDER BY item_type, occurrence_count DESC, item_value
                """
            ).fetchall()
    except Exception as exc:
        _log.warning("property_knowledge: could not read items for file rebuild: %s", exc)
        return

    grouped: dict[str, list[tuple[str, int]]] = {}
    for row in rows:
        key = str(row["item_type"])
        grouped.setdefault(key, []).append((str(row["item_value"]), int(row["occurrence_count"])))

    _TRAINING_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Property Knowledge Base — Waldorf Astoria New York\n",
        "_Auto-generated by the Completed Requests training pipeline. Do not edit manually._\n",
        f"_Last updated by pipeline run. {len(rows)} total knowledge items._\n\n",
    ]

    section_titles = {
        "room_type": "## Room Types",
        "rate_plan": "## Rate Plans & Programs",
        "package": "## Packages",
        "offer": "## Special Offers & Amenities",
        "routing": "## Department Routing Patterns",
        "sop": "## Standard Operating Procedures (inferred)",
    }

    for key in ("room_type", "rate_plan", "package", "offer", "routing", "sop"):
        entries = grouped.get(key)
        if not entries:
            continue
        lines.append(section_titles.get(key, f"## {key}") + "\n\n")
        for value, count in entries:
            tag = f" _(×{count})_" if count > 1 else ""
            lines.append(f"- {value}{tag}\n")
        lines.append("\n")

    _KNOWLEDGE_FILE.write_text("".join(lines), encoding="utf-8")
    _log.info("property_knowledge: wrote %s (%d items)", _KNOWLEDGE_FILE, len(rows))

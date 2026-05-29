"""Agent-assisted labeling workflow: split -> label -> validate -> merge.

This script handles the Python-only parts of chunk-based labeling.
Claude (the agent) reads one chunk file at a time and labels those examples
by semantic judgment. No rule engines, no heuristic_analysis, no classifier.

Commands
--------
Split a pending batch into chunks for agent labeling:
  python scripts/agent_label_chunk_workflow.py \\
      --split labeling/agent_batches/<ts>_pending.json --chunk-size 50

Validate a single labeled chunk or final labeled file:
  python scripts/agent_label_chunk_workflow.py \\
      --validate labeling/agent_batches/<ts>_pending.json \\
                 labeling/agent_batches/<ts>_labeled.json

Merge labeled chunks back into a single labeled file:
  python scripts/agent_label_chunk_workflow.py \\
      --merge labeling/agent_batches/chunks/<batch_id>/ \\
      --output labeling/agent_batches/<ts>_labeled.json

Show labeling progress across all chunks:
  python scripts/agent_label_chunk_workflow.py \\
      --status labeling/agent_batches/<ts>_pending.json \\
               labeling/agent_batches/chunks/<batch_id>/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Taxonomy ──────────────────────────────────────────────────────────────────

from outlook_dashboard.taxonomy import CATEGORIES, DEPARTMENT_OWNERS, RECOMMENDED_ACTIONS

_VALID_CONTACT_TYPES = {"Internal", "Group contact", "Travel agency", "Guest"}
_VALID_PRIORITY_LEVELS = {"Low", "Normal", "High", "Immediate"}
_VALID_RECOMMENDED_ACTIONS = set(RECOMMENDED_ACTIONS) | {None}

# Safe normalisation aliases — only applied automatically when unambiguous
_CONTACT_TYPE_ALIASES: dict[str, str] = {
    "Direct guest": "Guest",
    "direct guest": "Guest",
    "guest": "Guest",
    "internal": "Internal",
    "travel agency": "Travel agency",
    "Travel Agent": "Travel agency",
    "travel agent": "Travel agency",
    "Group Contact": "Group contact",
    "group contact": "Group contact",
}
def _build_category_aliases() -> dict[str, str]:
    """Build aliases mapping en-dash variants to the canonical em-dash taxonomy values."""
    aliases: dict[str, str] = {
        "Credit card authorization": "Billing authorization",
        "credit card authorization": "Billing authorization",
    }
    for cat in CATEGORIES:
        if "—" in cat:  # em dash in canonical name
            aliases[cat.replace("—", "–")] = cat  # en-dash -> em-dash
    return aliases

_CATEGORY_ALIASES: dict[str, str] = _build_category_aliases()
_OWNER_ALIASES: dict[str, str] = {
    "Front Desk": "Front Office",
    "front desk": "Front Office",
    "front office": "Front Office",
    "reservations": "Reservations",
    "concierge": "Concierge",
    "housekeeping": "Housekeeping",
    "engineering": "Engineering",
    "sales": "Sales",
}

# Fields that must never appear in labeled output (raw PII)
_UNSAFE_FIELDS = {
    "body_text", "body_content", "body_raw", "sender_email",
    "from_email", "subject", "graph_message_id", "outlook_entry_id",
    "message_id", "phone", "credit_card",
}

_LABELING_INSTRUCTIONS = """\
You are a hotel email triage classifier for the Waldorf Astoria New York Reservations team.
Label each example using your own semantic judgment based on the redacted body excerpt.
Do NOT use keyword rules or heuristics as your decision logic.

TAXONOMY

contact_type (exactly one):
  Internal       — sender_domain is null (Waldorf/Hilton staff on internal Exchange)
                   or domain is h6.hilton.com, hilton.com, waldorfastorianewyork.com
  Travel agency  — professional travel agents, concierge services, travel management firms
                   (sertifi.net, htconcierge.co.uk, rsbtravel.com, traveljst.com, teresaperez.com.br,
                    mrtripper.com, llgevents.com when acting as agent, any *travel*/*concierge*/*journeys* domain)
  Group contact  — corporate event/group coordinators booking for a company or event
  Guest          — direct individual guests (gmail.com, personal email domains)

category (exactly one):
  VIP pre-arrival, Rate inquiry, Billing dispute, Consortia / FHR / Virtuoso,
  Complaint, Amenity request, Accessibility request, Rooming list / group,
  Internal request, Cancellation / modification, Urgent same-day arrival,
  Duplicate follow-up, General inquiry, Billing authorization, Internal notification,
  Internal report, Hilton Honors / loyalty, OTA pending messages, Guest communication,
  Billing – VIP extended stay, Billing – card update, Billing – extended stay,
  Billing – group master, Billing – high balance alert, Billing – no-show / PG

priority_level: Low | Normal | High | Immediate

owner (exactly one):
  Front Office, Reservations, Concierge, Housekeeping, Engineering, Sales,
  Finance, Pre-Arrival, Events, Group Reservations, Revenue Management,
  Sales, Marketing, Managing Director, All Departments

guest_sentiment: Positive | Neutral | Concerned | Upset | Furious

recommended_action (or null):
  reply_guest, loop_reservations, loop_front_office, loop_concierge,
  loop_housekeeping, loop_engineering, escalate_manager,
  verify_payment_authorization, review_folio, check_reservation,
  request_missing_information, wait_for_guest, wait_for_internal_team,
  no_action_likely

OUTPUT FORMAT — one JSON array, one object per example (same order as input):
[
  {
    "fingerprint": "<copy exactly from input>",
    "category": "<from taxonomy>",
    "priority_level": "<Low|Normal|High|Immediate>",
    "owner": "<from taxonomy>",
    "contact_type": "<Internal|Group contact|Travel agency|Guest>",
    "guest_sentiment": "<Positive|Neutral|Concerned|Upset|Furious>",
    "missing_information": "<short phrase describing what's missing, or null>",
    "label_missing_info": <true|false>,
    "label_reply_required": <true|false>,
    "label_escalation_required": <true|false>,
    "recommended_action": "<from taxonomy or null>",
    "confidence": <0-100>,
    "notes": "<optional reasoning, max 150 chars>"
  }
]

RULES
1. Base every decision on the body_excerpt content — PII has been redacted.
2. sender_domain=null almost always means Internal Waldorf/Hilton staff.
3. sertifi.net -> Billing authorization (e-signature/payment platform).
4. label_reply_required=true when an external party (not Internal) is asking a question or requesting action.
5. label_escalation_required=true only for: billing disputes, Immediate priority, complaints, or legal threats.
6. For duplicate fingerprints in a chunk, give them identical labels.
7. confidence reflects how certain you are (0–100). Low confidence is fine — be honest.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _batch_id_from_pending(pending_path: Path) -> str:
    """Extract batch timestamp ID from a pending filename."""
    return pending_path.stem.replace("_pending", "")


def _chunks_dir(pending_path: Path) -> Path:
    batch_id = _batch_id_from_pending(pending_path)
    return ROOT / "labeling" / "agent_batches" / "chunks" / batch_id


def _normalize_label(label: dict) -> dict:
    """Apply safe unambiguous aliases in-place. Returns the mutated dict."""
    ct = label.get("contact_type") or ""
    if ct in _CONTACT_TYPE_ALIASES:
        label["contact_type"] = _CONTACT_TYPE_ALIASES[ct]

    cat = label.get("category") or ""
    if cat in _CATEGORY_ALIASES:
        label["category"] = _CATEGORY_ALIASES[cat]

    owner = label.get("owner") or ""
    if owner in _OWNER_ALIASES:
        label["owner"] = _OWNER_ALIASES[owner]

    return label


def _validate_labels(
    pending_examples: list[dict],
    labeled: list[dict],
    *,
    strict: bool = True,
) -> tuple[bool, list[str]]:
    """Validate labeled output against pending examples.

    Returns (ok, list_of_errors).
    """
    errors: list[str] = []

    # Apply normalization first
    for label in labeled:
        _normalize_label(label)

    # Count check
    if len(labeled) != len(pending_examples):
        errors.append(
            f"Count mismatch: pending={len(pending_examples)}, labeled={len(labeled)}"
        )
        if strict:
            return False, errors

    pending_fps = [e["fingerprint"] for e in pending_examples]
    labeled_fps = [lbl.get("fingerprint", "") for lbl in labeled]

    # Fingerprint order check
    for i, (pf, lf) in enumerate(zip(pending_fps, labeled_fps)):
        if pf != lf:
            errors.append(f"Fingerprint mismatch at index {i}: expected {pf[:12]}… got {lf[:12]}…")

    required_fields = {
        "fingerprint", "category", "priority_level", "owner",
        "contact_type", "guest_sentiment", "label_missing_info",
        "label_reply_required", "label_escalation_required",
    }

    fp_label_map: dict[str, dict] = {}

    for i, lbl in enumerate(labeled):
        fp = lbl.get("fingerprint", f"<missing at {i}>")
        tag = f"[{i}] {fp[:12]}…"

        # Unsafe raw fields
        for bad in _UNSAFE_FIELDS:
            if bad in lbl:
                errors.append(f"{tag}: unsafe field present: {bad!r}")

        # Required fields
        for field in required_fields:
            if field not in lbl:
                errors.append(f"{tag}: missing required field {field!r}")

        # Taxonomy checks
        cat = lbl.get("category")
        if cat not in CATEGORIES:
            errors.append(f"{tag}: invalid category {cat!r}")

        owner = lbl.get("owner")
        if owner not in DEPARTMENT_OWNERS:
            errors.append(f"{tag}: invalid owner {owner!r}")

        ct = lbl.get("contact_type")
        if ct not in _VALID_CONTACT_TYPES:
            errors.append(f"{tag}: invalid contact_type {ct!r}")

        pri = lbl.get("priority_level")
        if pri not in _VALID_PRIORITY_LEVELS:
            errors.append(f"{tag}: invalid priority_level {pri!r}")

        action = lbl.get("recommended_action")
        if action is not None and action not in RECOMMENDED_ACTIONS:
            errors.append(f"{tag}: invalid recommended_action {action!r}")

        # Duplicate fingerprint consistency
        if fp in fp_label_map:
            prev = fp_label_map[fp]
            for field in ("category", "priority_level", "owner", "contact_type", "guest_sentiment"):
                if prev.get(field) != lbl.get(field):
                    errors.append(
                        f"{tag}: duplicate fingerprint has inconsistent {field!r} "
                        f"({prev.get(field)!r} vs {lbl.get(field)!r})"
                    )
        else:
            fp_label_map[fp] = lbl

    ok = len(errors) == 0
    return ok, errors


# ── Split ─────────────────────────────────────────────────────────────────────

def cmd_split(pending_path: Path, chunk_size: int, chunks_dir: Path | None = None) -> None:
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    examples = pending.get("examples", [])
    total = len(examples)

    # Group duplicates together: assign each unique fingerprint a slot number
    # based on first appearance, then sort by that slot
    fp_order: dict[str, int] = {}
    for e in examples:
        fp = e["fingerprint"]
        if fp not in fp_order:
            fp_order[fp] = len(fp_order)

    # Stable re-ordering: sort by (fp_order, original_index) groups duplicates
    indexed = sorted(enumerate(examples), key=lambda t: (fp_order[t[1]["fingerprint"]], t[0]))
    sorted_examples = [e for _, e in indexed]
    original_positions = [i for i, _ in indexed]

    if chunks_dir is None:
        chunks_dir = _chunks_dir(pending_path)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    batch_id = _batch_id_from_pending(pending_path)
    chunk_files: list[Path] = []

    for chunk_idx, start in enumerate(range(0, total, chunk_size)):
        chunk_examples = sorted_examples[start : start + chunk_size]
        chunk_positions = original_positions[start : start + chunk_size]
        chunk_num = chunk_idx + 1
        total_chunks = (total + chunk_size - 1) // chunk_size

        chunk_data = {
            "batch_id": batch_id,
            "chunk_index": chunk_idx,
            "chunk_number": chunk_num,
            "total_chunks": total_chunks,
            "chunk_size": len(chunk_examples),
            "original_positions": chunk_positions,
            "labeling_instructions": _LABELING_INSTRUCTIONS,
            "examples": chunk_examples,
        }
        chunk_file = chunks_dir / f"chunk_{chunk_num:03d}_of_{total_chunks:03d}.json"
        chunk_file.write_text(json.dumps(chunk_data, indent=2, ensure_ascii=False), encoding="utf-8")
        chunk_files.append(chunk_file)
        print(f"  chunk {chunk_num:3d}/{total_chunks}: {len(chunk_examples)} examples -> {chunk_file.name}")

    # Write position index so merge can reconstruct original order
    index_file = chunks_dir / "position_index.json"
    index_file.write_text(
        json.dumps({
            "batch_id": batch_id,
            "total": total,
            "chunk_size": chunk_size,
            "sorted_to_original": original_positions,
        }, indent=2),
        encoding="utf-8",
    )

    try:
        chunks_display = chunks_dir.relative_to(ROOT)
    except ValueError:
        chunks_display = chunks_dir
    print(f"\nSplit {total} examples into {len(chunk_files)} chunks -> {chunks_display}")
    print(f"Position index: {index_file.name}")
    print()
    print("NEXT STEP: Label each chunk file. For each chunk:")
    print("  1. Read the chunk file.")
    print("  2. Label every example by your own semantic judgment.")
    print(f"  3. Write labeled output to the same directory with suffix _labeled.json")
    print(f"     e.g. chunk_001_of_{len(chunk_files):03d}_labeled.json")
    print()
    print("After all chunks are labeled:")
    print(f"  python scripts/agent_label_chunk_workflow.py \\")
    print(f"      --merge {chunks_display} \\")
    print(f"      --output labeling/agent_batches/{batch_id}_labeled.json")


# ── Validate ──────────────────────────────────────────────────────────────────

def cmd_validate(pending_path: Path, labeled_path: Path) -> bool:
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    pending_examples = pending.get("examples", [])

    labeled_raw = json.loads(labeled_path.read_text(encoding="utf-8"))
    if isinstance(labeled_raw, list):
        labeled = labeled_raw
    else:
        labeled = labeled_raw.get("examples", labeled_raw.get("labels", []))

    ok, errors = _validate_labels(pending_examples, labeled)

    if ok:
        print(f"OK Validation passed: {len(labeled)} labels, all fields valid.")
        # Write back normalized labels
        labeled_path.write_text(json.dumps(labeled, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  (normalized aliases written back to {labeled_path.name})")
    else:
        print(f"FAIL Validation FAILED: {len(errors)} error(s):")
        for err in errors[:30]:
            print(f"  • {err}")
        if len(errors) > 30:
            print(f"  … and {len(errors) - 30} more.")

    return ok


# ── Merge ─────────────────────────────────────────────────────────────────────

def cmd_merge(chunks_dir: Path, output_path: Path, pending_path: Path | None = None) -> bool:
    # Load position index
    index_file = chunks_dir / "position_index.json"
    if not index_file.exists():
        print(f"ERROR: position_index.json not found in {chunks_dir}", file=sys.stderr)
        return False
    index = json.loads(index_file.read_text(encoding="utf-8"))
    total = index["total"]
    sorted_to_original = index["sorted_to_original"]

    # Collect all labeled chunk files
    labeled_chunk_files = sorted(chunks_dir.glob("chunk_*_labeled.json"))
    if not labeled_chunk_files:
        print("ERROR: no labeled chunk files found (chunk_*_labeled.json)", file=sys.stderr)
        return False

    # Merge all labeled chunks in order
    sorted_labels: list[dict | None] = [None] * total
    chunk_slot = 0
    errors: list[str] = []

    sorted_chunk_files = sorted(
        f for f in chunks_dir.glob("chunk_*_of_*.json") if "_labeled" not in f.name
    )
    for chunk_file in sorted_chunk_files:
        chunk_data = json.loads(chunk_file.read_text(encoding="utf-8"))
        chunk_idx = chunk_data["chunk_index"]
        chunk_examples = chunk_data["examples"]
        chunk_positions = chunk_data["original_positions"]

        labeled_name = chunk_file.name.replace(".json", "_labeled.json")
        labeled_file = chunks_dir / labeled_name
        if not labeled_file.exists():
            errors.append(f"Missing labeled file: {labeled_name}")
            continue

        chunk_labels_raw = json.loads(labeled_file.read_text(encoding="utf-8"))
        chunk_labels = chunk_labels_raw if isinstance(chunk_labels_raw, list) else []

        # Normalize
        for lbl in chunk_labels:
            _normalize_label(lbl)

        # Validate this chunk
        ok, verrs = _validate_labels(chunk_examples, chunk_labels)
        if not ok:
            errors.append(f"Chunk {chunk_file.name}: {len(verrs)} validation error(s)")
            for e in verrs[:5]:
                errors.append(f"  {e}")
            continue

        # Place each label back at its original position
        for label, orig_pos in zip(chunk_labels, chunk_positions):
            sorted_labels[orig_pos] = label

    if errors:
        print(f"MERGE FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"  • {e}")
        return False

    # Check all positions filled
    missing = [i for i, lbl in enumerate(sorted_labels) if lbl is None]
    if missing:
        print(f"MERGE FAILED: {len(missing)} positions unfilled: {missing[:10]}")
        return False

    # Enforce duplicate fingerprint consistency
    fp_label_map: dict[str, dict] = {}
    final: list[dict] = []
    for lbl in sorted_labels:
        assert lbl is not None
        fp = lbl["fingerprint"]
        if fp in fp_label_map:
            # Use first-seen label for all duplicates
            merged = dict(fp_label_map[fp])
            merged["fingerprint"] = fp
            final.append(merged)
        else:
            fp_label_map[fp] = lbl
            final.append(lbl)

    output_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK Merged {len(final)} labels -> {output_path}")

    # Final validation against pending if provided
    if pending_path and pending_path.exists():
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        pending_examples = pending.get("examples", [])
        ok, verrs = _validate_labels(pending_examples, final)
        if ok:
            print(f"OK Final validation passed against pending batch.")
        else:
            print(f"FAIL Final validation has {len(verrs)} issue(s):")
            for e in verrs[:10]:
                print(f"  • {e}")
            return False

    return True


# ── Status ────────────────────────────────────────────────────────────────────

def cmd_status(pending_path: Path, chunks_dir: Path) -> None:
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    total = len(pending.get("examples", []))

    chunk_files = sorted(chunks_dir.glob("chunk_*_of_*.json"))
    if not chunk_files:
        print(f"No chunks found in {chunks_dir}")
        return

    total_chunks = len(chunk_files)
    labeled_count = 0
    unlabeled: list[str] = []

    for chunk_file in chunk_files:
        labeled_file = chunks_dir / chunk_file.name.replace(".json", "_labeled.json")
        if labeled_file.exists():
            labeled_count += 1
            # Quick validate
            chunk_data = json.loads(chunk_file.read_text(encoding="utf-8"))
            labels = json.loads(labeled_file.read_text(encoding="utf-8"))
            ok, _ = _validate_labels(chunk_data["examples"], labels if isinstance(labels, list) else [])
            status = "OK valid" if ok else "FAIL invalid"
            print(f"  {chunk_file.name}: {status}")
        else:
            unlabeled.append(chunk_file.name)
            print(f"  {chunk_file.name}: AWAITING LABELS")

    print()
    print(f"Progress: {labeled_count}/{total_chunks} chunks labeled ({total} total examples)")
    if unlabeled:
        print(f"Remaining: {len(unlabeled)} chunk(s) to label")
        print(f"  Next: {unlabeled[0]}")
    else:
        batch_id = _batch_id_from_pending(pending_path)
        output = ROOT / "labeling" / "agent_batches" / f"{batch_id}_labeled.json"
        if output.exists():
            print(f"Merged file: {output} ({'exists' if output.exists() else 'not yet merged'})")
        else:
            try:
                chunks_display = chunks_dir.relative_to(ROOT)
            except ValueError:
                chunks_display = chunks_dir
            print(f"All chunks labeled — ready to merge:")
            print(f"  python scripts/agent_label_chunk_workflow.py \\")
            print(f"      --merge {chunks_display} \\")
            print(f"      --output labeling/agent_batches/{batch_id}_labeled.json \\")
            print(f"      --pending {pending_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent-assisted chunk labeling workflow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--split", type=Path, metavar="PENDING_JSON",
                       help="Split pending batch into chunks for agent labeling.")
    group.add_argument("--validate", type=Path, nargs=2, metavar=("PENDING_JSON", "LABELED_JSON"),
                       help="Validate a labeled file against its pending batch.")
    group.add_argument("--merge", type=Path, metavar="CHUNK_DIR",
                       help="Merge labeled chunks into final labeled file.")
    group.add_argument("--status", type=Path, nargs=2, metavar=("PENDING_JSON", "CHUNK_DIR"),
                       help="Show labeling progress.")

    parser.add_argument("--chunk-size", type=int, default=50,
                        help="Examples per chunk (default: 50).")
    parser.add_argument("--output", type=Path, metavar="LABELED_JSON",
                        help="Output path for --merge.")
    parser.add_argument("--pending", type=Path, metavar="PENDING_JSON",
                        help="Pending batch for final validation after --merge.")

    args = parser.parse_args()

    if args.split:
        pending = args.split.resolve()
        if not pending.exists():
            print(f"ERROR: {pending} not found", file=sys.stderr)
            sys.exit(1)
        cmd_split(pending, args.chunk_size)

    elif args.validate:
        pending, labeled = [p.resolve() for p in args.validate]
        ok = cmd_validate(pending, labeled)
        sys.exit(0 if ok else 1)

    elif args.merge:
        chunks_dir = args.merge.resolve()
        if not args.output:
            print("ERROR: --merge requires --output", file=sys.stderr)
            sys.exit(1)
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        pending = args.pending.resolve() if args.pending else None
        ok = cmd_merge(chunks_dir, output, pending)
        sys.exit(0 if ok else 1)

    elif args.status:
        pending, chunks_dir = [p.resolve() for p in args.status]
        cmd_status(pending, chunks_dir)


if __name__ == "__main__":
    main()

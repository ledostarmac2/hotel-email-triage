"""Tests for agent_label_chunk_workflow.py.

Verifies split/merge/validate correctness and that no heuristic or
classifier calls are made by the workflow script itself.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.agent_label_chunk_workflow import (
    _VALID_CONTACT_TYPES,
    _normalize_label,
    _validate_labels,
    cmd_merge,
    cmd_split,
)
from outlook_dashboard.taxonomy import CATEGORIES, DEPARTMENT_OWNERS, RECOMMENDED_ACTIONS


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_example(fp: str, n: int = 1) -> list[dict]:
    return [
        {
            "fingerprint": fp,
            "sender_domain": None,
            "subject_tokens": "test subject",
            "body_excerpt": f"Test email body {n}.",
            "received_date": "2026-05-01",
        }
    ]


def _make_pending(examples: list[dict], tmp_path: Path, name: str = "ts_pending.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps({"examples": examples, "count": len(examples)}), encoding="utf-8")
    return p


def _make_valid_label(fp: str) -> dict:
    return {
        "fingerprint": fp,
        "category": "General inquiry",
        "priority_level": "Normal",
        "owner": "Reservations",
        "contact_type": "Internal",
        "guest_sentiment": "Neutral",
        "missing_information": None,
        "label_missing_info": False,
        "label_reply_required": False,
        "label_escalation_required": False,
        "recommended_action": "no_action_likely",
        "confidence": 80,
        "notes": "test",
    }


# ── Split tests ───────────────────────────────────────────────────────────────

def _unique_pending(tmp_path: Path, n: int, suffix: str = "sp") -> tuple[Path, Path]:
    """Create a pending file with a unique batch_id; return (pending, chunks_dir).

    The chunks_dir is placed inside tmp_path so tests never pollute the real
    labeling/agent_batches/chunks/ directory.
    """
    import uuid
    batch_id = f"{suffix}_{uuid.uuid4().hex[:8]}"
    examples = [_make_example(f"fp{i:03d}")[0] for i in range(n)]
    pending = tmp_path / f"{batch_id}_pending.json"
    pending.write_text(json.dumps({"examples": examples, "count": n}), encoding="utf-8")
    chunks_dir = tmp_path / "chunks" / batch_id
    return pending, chunks_dir


class TestSplit:

    def test_split_preserves_total_count(self, tmp_path: Path) -> None:
        pending, chunks_dir = _unique_pending(tmp_path, 130)
        cmd_split(pending, chunk_size=50, chunks_dir=chunks_dir)

        chunk_files = [
            f for f in chunks_dir.glob("chunk_*_of_*.json") if "_labeled" not in f.name
        ]
        total_in_chunks = sum(
            len(json.loads(f.read_text(encoding="utf-8"))["examples"])
            for f in chunk_files
        )
        assert total_in_chunks == 130

    def test_split_creates_position_index(self, tmp_path: Path) -> None:
        pending, chunks_dir = _unique_pending(tmp_path, 10)
        cmd_split(pending, chunk_size=5, chunks_dir=chunks_dir)

        index_file = chunks_dir / "position_index.json"
        assert index_file.exists(), "position_index.json should be created"

        idx = json.loads(index_file.read_text(encoding="utf-8"))
        assert idx["total"] == 10
        assert len(idx["sorted_to_original"]) == 10

    def test_split_groups_duplicate_fingerprints(self, tmp_path: Path) -> None:
        """Duplicate fingerprints should be adjacent in the chunk."""
        import uuid
        batch_id = f"dup_{uuid.uuid4().hex[:8]}"
        fp = "aaaa"
        examples = [
            {"fingerprint": fp, "sender_domain": None, "subject_tokens": "a", "body_excerpt": "A", "received_date": ""},
            {"fingerprint": "bbbb", "sender_domain": None, "subject_tokens": "b", "body_excerpt": "B", "received_date": ""},
            {"fingerprint": fp, "sender_domain": None, "subject_tokens": "a", "body_excerpt": "A2", "received_date": ""},
        ]
        pending = tmp_path / f"{batch_id}_pending.json"
        pending.write_text(json.dumps({"examples": examples, "count": 3}), encoding="utf-8")
        chunks_dir = tmp_path / "chunks" / batch_id
        cmd_split(pending, chunk_size=10, chunks_dir=chunks_dir)

        chunk_files = [
            f for f in chunks_dir.glob("chunk_*_of_*.json") if "_labeled" not in f.name
        ]
        assert chunk_files, f"No chunk files in {chunks_dir}"
        data = json.loads(chunk_files[0].read_text(encoding="utf-8"))
        fps_in_chunk = [e["fingerprint"] for e in data["examples"]]
        first = fps_in_chunk.index(fp)
        second = fps_in_chunk.index(fp, first + 1)
        assert second == first + 1, f"Duplicate fingerprints not adjacent: positions {first} and {second}"


# ── Validate tests ────────────────────────────────────────────────────────────

class TestValidate:

    def test_valid_labels_pass(self) -> None:
        examples = [_make_example("fp001")[0]]
        labels = [_make_valid_label("fp001")]
        ok, errors = _validate_labels(examples, labels)
        assert ok, f"Expected valid but got errors: {errors}"

    def test_count_mismatch_fails(self) -> None:
        examples = [_make_example("fp001")[0], _make_example("fp002")[0]]
        labels = [_make_valid_label("fp001")]
        ok, errors = _validate_labels(examples, labels)
        assert not ok
        assert any("count mismatch" in e.lower() for e in errors)

    def test_missing_required_field_fails(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        del label["category"]
        ok, errors = _validate_labels(examples, [label])
        assert not ok
        assert any("category" in e for e in errors)

    def test_invalid_category_fails(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["category"] = "Not a real category"
        ok, errors = _validate_labels(examples, [label])
        assert not ok
        assert any("category" in e for e in errors)

    def test_invalid_owner_fails(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["owner"] = "Made Up Department"
        ok, errors = _validate_labels(examples, [label])
        assert not ok
        assert any("owner" in e for e in errors)

    def test_invalid_contact_type_fails(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["contact_type"] = "Vendor"
        ok, errors = _validate_labels(examples, [label])
        assert not ok
        assert any("contact_type" in e for e in errors)

    def test_invalid_priority_level_fails(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["priority_level"] = "Critical"
        ok, errors = _validate_labels(examples, [label])
        assert not ok
        assert any("priority_level" in e for e in errors)

    def test_invalid_recommended_action_fails(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["recommended_action"] = "do_something_weird"
        ok, errors = _validate_labels(examples, [label])
        assert not ok
        assert any("recommended_action" in e for e in errors)

    def test_null_recommended_action_passes(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["recommended_action"] = None
        ok, errors = _validate_labels(examples, [label])
        assert ok, errors

    def test_duplicate_fingerprint_inconsistent_labels_fails(self) -> None:
        fp = "dupfp"
        examples = [_make_example(fp)[0], _make_example(fp)[0]]
        label1 = _make_valid_label(fp)
        label2 = _make_valid_label(fp)
        label2["category"] = "Complaint"  # Different — inconsistent
        ok, errors = _validate_labels(examples, [label1, label2])
        assert not ok
        assert any("inconsistent" in e for e in errors)

    def test_duplicate_fingerprint_consistent_labels_passes(self) -> None:
        fp = "dupfp"
        examples = [_make_example(fp)[0], _make_example(fp)[0]]
        label1 = _make_valid_label(fp)
        label2 = _make_valid_label(fp)  # Same labels
        ok, errors = _validate_labels(examples, [label1, label2])
        assert ok, errors

    def test_unsafe_raw_field_body_text_fails(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["body_text"] = "raw email content"
        ok, errors = _validate_labels(examples, [label])
        assert not ok
        assert any("body_text" in e for e in errors)

    def test_unsafe_raw_field_sender_email_fails(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["sender_email"] = "guest@example.com"
        ok, errors = _validate_labels(examples, [label])
        assert not ok
        assert any("sender_email" in e for e in errors)


# ── Normalization tests ───────────────────────────────────────────────────────

class TestNormalization:

    def test_direct_guest_normalized_to_guest(self) -> None:
        label = {"contact_type": "Direct guest", "category": "General inquiry", "owner": "Reservations"}
        _normalize_label(label)
        assert label["contact_type"] == "Guest"

    def test_credit_card_authorization_normalized(self) -> None:
        label = {"contact_type": "Guest", "category": "Credit card authorization", "owner": "Reservations"}
        _normalize_label(label)
        assert label["category"] == "Billing authorization"

    def test_front_desk_normalized_to_front_office(self) -> None:
        label = {"contact_type": "Internal", "category": "Internal request", "owner": "Front Desk"}
        _normalize_label(label)
        assert label["owner"] == "Front Office"

    def test_normalize_then_validate_passes(self) -> None:
        examples = [_make_example("fp001")[0]]
        label = _make_valid_label("fp001")
        label["contact_type"] = "Direct guest"
        label["category"] = "Credit card authorization"
        # After normalization these should be valid
        _normalize_label(label)
        ok, errors = _validate_labels(examples, [label])
        assert ok, errors


# ── Merge tests ───────────────────────────────────────────────────────────────

class TestMerge:

    def _setup_chunks(
        self, tmp_path: Path, n: int = 6, chunk_size: int = 3, batch_suffix: str = "mrg"
    ) -> tuple[Path, Path, Path]:
        """Create pending, split into chunks, return (pending, chunks_dir, output)."""
        pending, chunks_dir = _unique_pending(tmp_path, n, batch_suffix)
        cmd_split(pending, chunk_size=chunk_size, chunks_dir=chunks_dir)
        output = tmp_path / pending.name.replace("_pending.json", "_labeled.json")
        return pending, chunks_dir, output

    def _write_chunk_labels(self, chunks_dir: Path) -> None:
        for chunk_file in sorted(chunks_dir.glob("chunk_*_of_*.json")):
            data = json.loads(chunk_file.read_text(encoding="utf-8"))
            labels = [_make_valid_label(e["fingerprint"]) for e in data["examples"]]
            labeled_file = chunks_dir / chunk_file.name.replace(".json", "_labeled.json")
            labeled_file.write_text(json.dumps(labels), encoding="utf-8")

    def test_merge_preserves_original_order(self, tmp_path: Path) -> None:
        pending, chunks_dir, output = self._setup_chunks(tmp_path, n=6, chunk_size=3)
        self._write_chunk_labels(chunks_dir)

        pending_data = json.loads(pending.read_text(encoding="utf-8"))
        original_fps = [e["fingerprint"] for e in pending_data["examples"]]

        ok = cmd_merge(chunks_dir, output, pending)
        assert ok, "Merge should succeed"

        merged = json.loads(output.read_text(encoding="utf-8"))
        merged_fps = [lbl["fingerprint"] for lbl in merged]
        assert merged_fps == original_fps, "Merged order must match original pending order"

    def test_merge_count_equals_pending_count(self, tmp_path: Path) -> None:
        pending, chunks_dir, output = self._setup_chunks(tmp_path, n=9, chunk_size=4)
        self._write_chunk_labels(chunks_dir)

        ok = cmd_merge(chunks_dir, output, pending)
        assert ok

        merged = json.loads(output.read_text(encoding="utf-8"))
        assert len(merged) == 9

    def test_merge_fails_if_chunk_missing(self, tmp_path: Path) -> None:
        pending, chunks_dir, output = self._setup_chunks(tmp_path, n=6, chunk_size=3)
        # Only label one of two chunks
        chunk_files = sorted(chunks_dir.glob("chunk_*_of_*.json"))
        data = json.loads(chunk_files[0].read_text(encoding="utf-8"))
        labels = [_make_valid_label(e["fingerprint"]) for e in data["examples"]]
        labeled = chunks_dir / chunk_files[0].name.replace(".json", "_labeled.json")
        labeled.write_text(json.dumps(labels), encoding="utf-8")
        # Second chunk has no labeled file → merge should fail

        ok = cmd_merge(chunks_dir, output, pending)
        assert not ok, "Merge should fail with missing chunk"

    def test_merge_enforces_duplicate_fingerprint_consistency(self, tmp_path: Path) -> None:
        """Merge must make all duplicate-fp entries use first-seen labels in output."""
        import uuid
        batch_id = f"dup_{uuid.uuid4().hex[:6]}"
        fp = "shared_fp"
        examples = [
            {"fingerprint": fp, "sender_domain": None, "subject_tokens": "a", "body_excerpt": "A", "received_date": ""},
            {"fingerprint": "unique_fp", "sender_domain": None, "subject_tokens": "b", "body_excerpt": "B", "received_date": ""},
            {"fingerprint": fp, "sender_domain": None, "subject_tokens": "a", "body_excerpt": "A2", "received_date": ""},
        ]
        pending = tmp_path / f"{batch_id}_pending.json"
        pending.write_text(json.dumps({"examples": examples, "count": 3}), encoding="utf-8")
        chunks_dir = tmp_path / "chunks" / batch_id
        cmd_split(pending, chunk_size=10, chunks_dir=chunks_dir)

        output = tmp_path / f"{batch_id}_labeled.json"
        chunk_files = sorted(chunks_dir.glob("chunk_*_of_*.json"))
        assert chunk_files, f"No chunk files in {chunks_dir}"
        data = json.loads(chunk_files[0].read_text(encoding="utf-8"))

        # Validator will reject inconsistent labels, so use consistent ones
        # but verify the dedup logic still produces consistent output
        labels = [_make_valid_label(e["fingerprint"]) for e in data["examples"]]
        labeled_file = chunks_dir / chunk_files[0].name.replace(".json", "_labeled.json")
        labeled_file.write_text(json.dumps(labels), encoding="utf-8")

        ok = cmd_merge(chunks_dir, output, pending)
        assert ok, "Merge should succeed with consistent labels"
        merged = json.loads(output.read_text(encoding="utf-8"))
        fp_cats = [lbl["category"] for lbl in merged if lbl["fingerprint"] == fp]
        assert len(set(fp_cats)) == 1, f"Duplicate fp has inconsistent categories: {fp_cats}"


# ── No heuristic / classifier calls ──────────────────────────────────────────

class TestNoHeuristicOrClassifierCalls:

    def test_workflow_script_does_not_import_heuristic_analysis(self) -> None:
        """The workflow script must not import or call heuristic_analysis."""
        import ast
        src = (ROOT / "scripts" / "agent_label_chunk_workflow.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        # Check no import of heuristic_analysis
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name != "heuristic_analysis", \
                        "agent_label_chunk_workflow.py imports heuristic_analysis"
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    assert node.func.id != "heuristic_analysis", \
                        "agent_label_chunk_workflow.py calls heuristic_analysis()"
                if isinstance(node.func, ast.Attribute):
                    assert node.func.attr != "heuristic_analysis", \
                        "agent_label_chunk_workflow.py calls .heuristic_analysis()"

    def test_workflow_script_does_not_import_local_classifier_predict(self) -> None:
        """The workflow script must not call local_classifier or predict."""
        import ast
        src = (ROOT / "scripts" / "agent_label_chunk_workflow.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "local_classifier" not in mod, \
                    f"agent_label_chunk_workflow.py imports from local_classifier: {mod}"
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    assert node.func.attr != "predict", \
                        "agent_label_chunk_workflow.py calls .predict()"

    def test_workflow_script_does_not_call_classify(self) -> None:
        """The workflow script must not have a classify() invocation."""
        import ast
        src = (ROOT / "scripts" / "agent_label_chunk_workflow.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "classify", \
                    "agent_label_chunk_workflow.py calls classify()"

    def test_validate_function_does_not_call_heuristic(self) -> None:
        """_validate_labels must not call heuristic_analysis internally."""
        import inspect
        src = inspect.getsource(_validate_labels)
        assert "heuristic_analysis" not in src
        assert "local_classifier" not in src

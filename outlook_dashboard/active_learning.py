"""Privacy-safe active-learning candidate ranking.

Ranks sanitized training examples for human or outside-agent review. This
module is deterministic, local-only, and never calls external AI or network
services.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

_UNSAFE_FIELDS = {
    "body_text",
    "body_content",
    "raw_body",
    "raw_text",
    "sender_email",
    "from_email",
    "subject",
    "graph_message_id",
    "outlook_entry_id",
    "entry_id",
    "message_id",
    "internet_message_id",
    "conversation_id",
}

_SAFE_FIELDS = {
    "email_fingerprint",
    "fingerprint",
    "import_key",
    "sender_domain",
    "subject_tokens",
    "body_redacted",
    "body_excerpt",
    "label_urgency",
    "label_owner",
    "label_category",
    "label_status",
    "label_sentiment",
    "label_recommended_action",
    "label_missing_info",
    "label_reply_required",
    "label_escalation_required",
    "urgency",
    "owner",
    "category",
    "status",
    "recommended_action",
    "risk_flags",
    "missing_information",
    "missing_info",
    "confidence",
    "confidence_score",
    "classifier_confidence_scores",
    "human_reviewed",
    "labeling_engine",
}


def rank_training_candidates(
    candidates: Iterable[Mapping[str, Any]],
    model_meta: Mapping[str, Any] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return sanitized candidates ranked by review value."""
    safe_candidates = [_sanitize_candidate(candidate) for candidate in candidates]
    label_counts = _candidate_label_counts(safe_candidates)
    ranked: list[dict[str, Any]] = []

    for candidate in safe_candidates:
        score, reasons = _score_candidate(candidate, label_counts, model_meta or {})
        item = dict(candidate)
        item["review_score"] = round(score, 3)
        item["review_reasons"] = reasons
        ranked.append(item)

    ranked.sort(key=lambda item: (-float(item["review_score"]), _stable_key(item)))
    return ranked[: max(0, int(limit))]


def _sanitize_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in candidate.items():
        key_text = str(key)
        if key_text.lower() in _UNSAFE_FIELDS:
            continue
        if key_text in _SAFE_FIELDS or key_text.startswith("label_"):
            safe[key_text] = value
    return safe


def _candidate_label_counts(candidates: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    counts = {"urgency": Counter(), "owner": Counter(), "category": Counter()}
    for candidate in candidates:
        for target in counts:
            value = _label_value(candidate, target)
            if value:
                counts[target][str(value)] += 1
    return counts


def _score_candidate(
    candidate: Mapping[str, Any],
    label_counts: dict[str, Counter[str]],
    model_meta: Mapping[str, Any],
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    missing_targets = [target for target in ("urgency", "owner", "category") if not _label_value(candidate, target)]
    if missing_targets:
        score += 35.0 + len(missing_targets) * 5.0
        reasons.append("missing labels")

    confidence = _confidence(candidate)
    if confidence is not None:
        low_confidence_points = max(0.0, 1.0 - confidence) * 30.0
        if low_confidence_points >= 6:
            reasons.append("low confidence")
        score += low_confidence_points

    risk_flags = candidate.get("risk_flags") or []
    if isinstance(risk_flags, str):
        risk_flags = [risk_flags] if risk_flags.strip() else []
    if risk_flags or candidate.get("label_escalation_required"):
        score += 18.0
        reasons.append("risk or escalation")

    if candidate.get("label_missing_info") or candidate.get("missing_info") or candidate.get("missing_information"):
        score += 8.0
        reasons.append("missing information")

    for target in ("urgency", "owner", "category"):
        value = _label_value(candidate, target)
        if not value:
            continue
        if _is_rare_label(target, str(value), label_counts, model_meta):
            score += 10.0
            reasons.append(f"rare {target}")

    if not reasons:
        reasons.append("baseline sample")
    return score, reasons


def _label_value(candidate: Mapping[str, Any], target: str) -> Any:
    if target == "urgency":
        return candidate.get("label_urgency") or candidate.get("urgency")
    return candidate.get(f"label_{target}") or candidate.get(target)


def _confidence(candidate: Mapping[str, Any]) -> float | None:
    raw = candidate.get("confidence_score", candidate.get("confidence"))
    if raw is None and isinstance(candidate.get("classifier_confidence_scores"), Mapping):
        values = [
            float(value)
            for value in candidate["classifier_confidence_scores"].values()
            if isinstance(value, (int, float))
        ]
        raw = min(values) if values else None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value > 1:
        value = value / 100.0
    return max(0.0, min(1.0, value))


def _is_rare_label(
    target: str,
    value: str,
    label_counts: dict[str, Counter[str]],
    model_meta: Mapping[str, Any],
) -> bool:
    target_meta = (model_meta.get("targets") or {}).get(target, {}) if isinstance(model_meta, Mapping) else {}
    dist = target_meta.get("label_distribution") or {}
    if dist:
        try:
            return int(dist.get(value, 0)) <= 2
        except (TypeError, ValueError):
            return False
    local_count = label_counts.get(target, Counter()).get(value, 0)
    if 0 < local_count <= 2:
        return True
    return False


def _stable_key(candidate: Mapping[str, Any]) -> str:
    basis = {
        key: candidate.get(key)
        for key in ("email_fingerprint", "fingerprint", "import_key", "sender_domain", "subject_tokens", "body_redacted")
        if candidate.get(key)
    }
    return hashlib.sha256(json.dumps(basis, sort_keys=True, default=str).encode("utf-8")).hexdigest()

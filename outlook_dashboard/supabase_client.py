from __future__ import annotations

import hashlib
import os

from .config import get_settings
from . import __version__
from .database import (
    cache_classification_rules,
    cache_known_senders,
    cache_prompt_versions,
    enqueue_feedback_upload,
    list_cached_classification_rules,
    list_cached_known_senders,
    list_cached_prompt_versions,
    list_pending_feedback_uploads,
    mark_feedback_upload_failed,
    mark_feedback_upload_succeeded,
)
from .runtime_log import get_logger

_log = get_logger("supabase")
_APP_VERSION = __version__
_rules_cache: list[dict] = []
_known_senders_cache: list[dict] = []
_prompt_versions_cache: list[dict] = []


def _url() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def _key() -> str:
    return os.getenv("SUPABASE_KEY", "")


def _configured() -> bool:
    return bool(_url() and _key())


def _headers(*, prefer_minimal: bool = False) -> dict[str, str]:
    h = {
        "apikey": _key(),
        "Authorization": f"Bearer {_key()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if prefer_minimal:
        h["Prefer"] = "return=minimal"
    return h


def _fingerprint(sender_email: str, subject: str) -> str:
    domain = (sender_email.split("@")[-1] if "@" in sender_email else sender_email).lower()
    tokens = " ".join(w.lower() for w in (subject or "").split() if len(w) > 3)
    return hashlib.sha256(f"{domain}:{tokens}".encode()).hexdigest()


def upload_feedback_event(
    email: dict,
    corrections: dict,
    feedback_text: str,
    *,
    summary_quality_rating: int | None = None,
    reply_quality_rating: int | None = None,
) -> None:
    """Upload one feedback correction to Supabase. Silent no-op if unconfigured."""
    if not _configured():
        return
    sender_email = str(email.get("sender_email") or "")
    domain = (sender_email.split("@")[-1] if "@" in sender_email else "").lower() or None
    payload = {
        "email_fingerprint": _fingerprint(sender_email, str(email.get("subject") or "")),
        "sender_domain": domain,
        "original_urgency": email.get("urgency_score"),
        "corrected_urgency": corrections.get("corrected_urgency"),
        "original_owner": email.get("recommended_department_owner"),
        "corrected_owner": corrections.get("corrected_owner"),
        "original_category": email.get("category"),
        "corrected_category": corrections.get("corrected_category"),
        "original_contact_type": email.get("contact_type"),
        "corrected_contact_type": corrections.get("corrected_contact_type"),
        "original_sentiment": email.get("guest_sentiment"),
        "corrected_sentiment": corrections.get("corrected_sentiment"),
        "original_status": email.get("status"),
        "corrected_status": corrections.get("corrected_status"),
        "summary_quality_rating": summary_quality_rating,
        "reply_quality_rating": reply_quality_rating,
        "confidence_score": email.get("confidence_score"),
        "feedback_notes": (feedback_text or "")[:500] or None,
        "analysis_engine": email.get("analysis_engine"),
        "app_version": _APP_VERSION,
    }
    ok, error = _post_feedback_payload(payload)
    if ok:
        _log.info("Supabase: feedback uploaded fingerprint=%.12s", payload["email_fingerprint"])
        return
    _log.warning("Supabase: upload failed; queued for retry: %s", error)
    enqueue_feedback_upload(payload, error=error, db_path=get_settings().database_path)


def _post_feedback_payload(payload: dict) -> tuple[bool, str]:
    try:
        import httpx
    except ImportError as exc:
        return False, f"httpx unavailable: {exc}"
    try:
        with httpx.Client(timeout=8) as client:
            r = client.post(
                f"{_url()}/rest/v1/feedback_events",
                json=payload,
                headers=_headers(prefer_minimal=True),
            )
        if r.status_code in (200, 201, 204):
            return True, ""
        return False, f"status={r.status_code} body={r.text[:200]}"
    except Exception as exc:
        return False, str(exc)


def flush_feedback_queue(limit: int = 25) -> int:
    """Retry queued feedback uploads. Returns number successfully flushed."""
    if not _configured():
        return 0
    db_path = get_settings().database_path
    flushed = 0
    for item in list_pending_feedback_uploads(limit=limit, db_path=db_path):
        payload = item.get("payload")
        if not isinstance(payload, dict):
            mark_feedback_upload_failed(int(item["id"]), "Invalid queued payload", db_path=db_path)
            continue
        ok, error = _post_feedback_payload(payload)
        if ok:
            mark_feedback_upload_succeeded(int(item["id"]), db_path=db_path)
            flushed += 1
        else:
            mark_feedback_upload_failed(int(item["id"]), error, db_path=db_path)
    if flushed:
        _log.info("Supabase: flushed %s queued feedback uploads", flushed)
    return flushed


def _download_and_cache(
    table: str,
    params: dict,
    label: str,
    cache_fn,
    list_fn,
    cache_var: list,
) -> list[dict]:
    """Shared download-then-cache pattern for all three Supabase reference tables."""
    db_path = get_settings().database_path
    if not _configured():
        result = list_fn(db_path=db_path)
        cache_var[:] = result
        return result
    try:
        import httpx

        with httpx.Client(timeout=10) as client:
            r = client.get(f"{_url()}/rest/v1/{table}", params=params, headers=_headers())
        if r.status_code == 200:
            rows = r.json()
            cache_var[:] = rows
            cache_fn(rows, db_path=db_path)
            _log.info("Supabase: downloaded %s %s", len(rows), label)
            return rows
        _log.warning("Supabase: %s download failed status=%s", label, r.status_code)
    except Exception as exc:
        _log.warning("Supabase: %s download error (non-fatal): %s", label, exc)
    cached = list_fn(db_path=db_path)
    if cached:
        cache_var[:] = cached
        _log.info("Supabase: using %s cached %s", len(cached), label)
    return cached


def download_approved_rules() -> list[dict]:
    return _download_and_cache(
        table="classification_rules",
        params={"status": "eq.approved", "select": "*"},
        label="approved rules",
        cache_fn=cache_classification_rules,
        list_fn=list_cached_classification_rules,
        cache_var=_rules_cache,
    )


def download_prompt_versions() -> list[dict]:
    return _download_and_cache(
        table="prompt_versions",
        params={"status": "eq.active", "select": "*"},
        label="active prompt versions",
        cache_fn=cache_prompt_versions,
        list_fn=list_cached_prompt_versions,
        cache_var=_prompt_versions_cache,
    )


def download_known_senders() -> list[dict]:
    return _download_and_cache(
        table="known_senders",
        params={"select": "*"},
        label="known sender mappings",
        cache_fn=cache_known_senders,
        list_fn=list_cached_known_senders,
        cache_var=_known_senders_cache,
    )


def get_cached_rules() -> list[dict]:
    if not _rules_cache:
        _rules_cache.extend(list_cached_classification_rules(db_path=get_settings().database_path))
    return _rules_cache


def get_cached_known_senders() -> list[dict]:
    if not _known_senders_cache:
        _known_senders_cache.extend(list_cached_known_senders(db_path=get_settings().database_path))
    return _known_senders_cache


def get_cached_prompt_versions() -> list[dict]:
    if not _prompt_versions_cache:
        _prompt_versions_cache.extend(list_cached_prompt_versions(db_path=get_settings().database_path))
    return _prompt_versions_cache


def promote_rule_candidates(candidates: list[dict]) -> None:
    """Upsert shared rules.

    Three matching corrections create visible candidates. Five or more corrections
    auto-promote the shared rule as approved, matching the hands-off roadmap.
    """
    if not _configured() or not candidates:
        return
    try:
        import httpx
    except ImportError as exc:
        _log.warning("Supabase: rule promote skipped because httpx is unavailable: %s", exc)
        return
    headers = _headers(prefer_minimal=True)
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    endpoint = f"{_url()}/rest/v1/classification_rules?on_conflict=rule_key"
    with httpx.Client(timeout=8) as client:
        for c in candidates:
            if c.get("status") in {"dismissed", "rejected"}:
                continue
            status = "approved" if int(c.get("correction_count") or 0) >= 5 else "pending_review"
            payload = {
                "rule_key": c["key"],
                "rule_type": c["type"],
                "pattern": c["pattern"],
                "action": c["suggestion"],
                "confidence": c["confidence"],
                "correction_count": c["correction_count"],
                "status": status,
            }
            try:
                r = client.post(endpoint, json=payload, headers=headers)
                if r.status_code in (200, 201, 204):
                    _log.info(
                        "Supabase: upserted rule %s status=%s corrections=%s", c["key"], status, c["correction_count"]
                    )
                    _rules_cache[:] = [rule for rule in _rules_cache if rule.get("rule_key") != c["key"]]
                    if status == "approved":
                        _rules_cache.append({**payload, "rule_key": c["key"]})
                else:
                    _log.warning("Supabase: rule promote failed status=%s body=%s", r.status_code, r.text[:200])
            except Exception as exc:
                _log.warning("Supabase: rule promote error (non-fatal): %s", exc)

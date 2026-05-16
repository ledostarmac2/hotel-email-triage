from __future__ import annotations

import hashlib
import os

import httpx

from .runtime_log import get_logger

_log = get_logger("supabase")
_APP_VERSION = "0.1.0"
_rules_cache: list[dict] = []


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
        "confidence_score": email.get("confidence_score"),
        "feedback_notes": (feedback_text or "")[:500] or None,
        "analysis_engine": email.get("analysis_engine"),
        "app_version": _APP_VERSION,
    }
    try:
        with httpx.Client(timeout=8) as client:
            r = client.post(
                f"{_url()}/rest/v1/feedback_events",
                json=payload,
                headers=_headers(prefer_minimal=True),
            )
        if r.status_code in (200, 201):
            _log.info("Supabase: feedback uploaded fingerprint=%.12s", payload["email_fingerprint"])
        else:
            _log.warning("Supabase: upload failed status=%s body=%s", r.status_code, r.text[:200])
    except Exception as exc:
        _log.warning("Supabase: upload error (non-fatal): %s", exc)


def download_approved_rules() -> list[dict]:
    """Download approved classification rules from Supabase, cache them, and return them."""
    global _rules_cache
    if not _configured():
        return []
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{_url()}/rest/v1/classification_rules",
                params={"status": "eq.approved", "select": "*"},
                headers=_headers(),
            )
        if r.status_code == 200:
            rules = r.json()
            _rules_cache = rules
            _log.info("Supabase: downloaded %s approved rules", len(rules))
            return rules
        _log.warning("Supabase: rules download failed status=%s", r.status_code)
    except Exception as exc:
        _log.warning("Supabase: rules download error (non-fatal): %s", exc)
    return []


def get_cached_rules() -> list[dict]:
    return _rules_cache


def promote_rule_candidates(candidates: list[dict]) -> None:
    """Upsert rule candidates with 3+ corrections into Supabase as approved rules. Silent no-op if unconfigured."""
    if not _configured() or not candidates:
        return
    headers = _headers(prefer_minimal=True)
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    for c in candidates:
        payload = {
            "rule_key": c["key"],
            "rule_type": c["type"],
            "pattern": c["pattern"],
            "action": c["suggestion"],
            "confidence": c["confidence"],
            "correction_count": c["correction_count"],
            "status": "approved",
        }
        try:
            with httpx.Client(timeout=8) as client:
                r = client.post(
                    f"{_url()}/rest/v1/classification_rules?on_conflict=rule_key",
                    json=payload,
                    headers=headers,
                )
            if r.status_code in (200, 201):
                _log.info("Supabase: promoted rule %s (%s corrections)", c["key"], c["correction_count"])
                _rules_cache[:] = [rule for rule in _rules_cache if rule.get("rule_key") != c["key"]]
                _rules_cache.append({**payload, "rule_key": c["key"]})
            else:
                _log.warning("Supabase: rule promote failed status=%s body=%s", r.status_code, r.text[:200])
        except Exception as exc:
            _log.warning("Supabase: rule promote error (non-fatal): %s", exc)

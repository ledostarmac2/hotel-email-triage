"""Sender domain reputation and pattern learning.

Aggregates per-domain profiles from Supabase feedback_events to provide
urgency bias, category/owner priors, and correction-rate signals.

Profiles are cached in SQLite and refreshed on demand (startup + admin trigger).
get_sender_profile() is synchronous, sub-millisecond once cached.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from .runtime_log import get_logger

_log = get_logger("sender_intelligence")
_lock = threading.Lock()
_cache: dict[str, dict[str, Any]] = {}
_last_refresh: datetime | None = None
_CACHE_TTL_HOURS = 6

# Minimum interactions required before we trust a profile
_MIN_INTERACTIONS_FOR_BIAS = 3

_UNKNOWN_PROFILE: dict[str, Any] = {
    "domain": "",
    "typical_category": None,
    "typical_owner": None,
    "avg_urgency": 2.5,
    "urgency_bias": 0.0,
    "correction_count": 0,
    "total_interactions": 0,
    "correction_rate": 0.0,
    "profile_confidence": 0.0,
    "last_seen": None,
}


def get_sender_profile(domain: str) -> dict[str, Any]:
    """Return reputation profile for a sender domain.

    Always returns a dict — unknown domains get a zero-confidence profile.
    Does not block on network calls; uses cached data only.
    """
    if not domain:
        return dict(_UNKNOWN_PROFILE)
    domain = domain.lower().strip()
    with _lock:
        profile = _cache.get(domain)
    if profile is not None:
        return dict(profile)
    # Try parent domain (e.g. mail.virtuoso.com -> virtuoso.com)
    parts = domain.split(".")
    if len(parts) > 2:
        parent = ".".join(parts[-2:])
        with _lock:
            profile = _cache.get(parent)
        if profile is not None:
            return dict(profile)
    return {**_UNKNOWN_PROFILE, "domain": domain}


def refresh_profiles(db_path: str | None = None, force: bool = False) -> int:
    """Download feedback_events from Supabase and rebuild per-domain profiles.

    Returns the number of distinct domain profiles loaded.
    Silently no-ops if Supabase is unreachable — stale cache is fine.
    """
    global _last_refresh
    with _lock:
        if (
            not force
            and _last_refresh is not None
            and datetime.now(tz=timezone.utc) - _last_refresh < timedelta(hours=_CACHE_TTL_HOURS)
        ):
            return len(_cache)

    rows = _fetch_feedback_rows()
    if rows is None:
        # Network failure — keep existing cache
        return len(_cache)

    profiles = _build_profiles(rows)
    with _lock:
        _cache.clear()
        _cache.update(profiles)
        _last_refresh = datetime.now(tz=timezone.utc)

    if db_path:
        _persist_to_sqlite(profiles, db_path)

    _log.info("Sender intelligence: %d domain profiles loaded.", len(profiles))
    return len(profiles)


def load_from_sqlite(db_path: str) -> int:
    """Warm the cache from a previously persisted SQLite snapshot.

    Called at app startup so the first email triage has profiles available
    without waiting for a Supabase round-trip.
    """
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT domain, profile_json FROM sender_profiles"
        ).fetchall()
        conn.close()
        profiles = {row[0]: json.loads(row[1]) for row in rows}
        with _lock:
            _cache.update(profiles)
        _log.debug("Sender intelligence: loaded %d profiles from SQLite.", len(profiles))
        return len(profiles)
    except Exception as exc:
        _log.debug("Sender intelligence: SQLite load skipped (%s).", exc)
        return 0


def _fetch_feedback_rows() -> list[dict] | None:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    try:
        import httpx
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }
        params = {
            "select": (
                "sender_domain,original_urgency,corrected_urgency,"
                "original_owner,corrected_owner,"
                "original_category,corrected_category,created_at"
            ),
            "order": "created_at.asc",
            "limit": "5000",
        }
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{url}/rest/v1/feedback_events", params=params, headers=headers)
        if r.status_code == 200:
            return r.json()
        _log.warning("Sender intelligence fetch: status %s", r.status_code)
        return None
    except Exception as exc:
        _log.debug("Sender intelligence fetch failed: %s", exc)
        return None


def _build_profiles(rows: list[dict]) -> dict[str, dict[str, Any]]:
    """Aggregate feedback_events rows into per-domain profiles."""
    from collections import Counter, defaultdict

    domain_data: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "urgency_original": [],
        "urgency_corrected": [],
        "owners_corrected": [],
        "categories_corrected": [],
        "correction_count": 0,
        "total": 0,
        "last_seen": None,
    })

    for row in rows:
        domain = str(row.get("sender_domain") or "").lower().strip()
        if not domain:
            continue
        d = domain_data[domain]
        d["total"] += 1
        ts = row.get("created_at")
        if ts and (d["last_seen"] is None or ts > d["last_seen"]):
            d["last_seen"] = ts

        orig_u = row.get("original_urgency")
        corr_u = row.get("corrected_urgency")
        if orig_u is not None:
            try:
                d["urgency_original"].append(int(orig_u))
            except (TypeError, ValueError):
                pass
        if corr_u is not None:
            try:
                d["urgency_corrected"].append(int(corr_u))
            except (TypeError, ValueError):
                pass

        corr_owner = row.get("corrected_owner")
        if corr_owner:
            d["owners_corrected"].append(str(corr_owner))

        corr_cat = row.get("corrected_category")
        if corr_cat:
            d["categories_corrected"].append(str(corr_cat))

        # Count as a correction if any field was explicitly changed
        if any([
            corr_u and corr_u != orig_u,
            row.get("corrected_owner") and row.get("corrected_owner") != row.get("original_owner"),
            row.get("corrected_category") and row.get("corrected_category") != row.get("original_category"),
        ]):
            d["correction_count"] += 1

    profiles: dict[str, dict[str, Any]] = {}
    for domain, d in domain_data.items():
        total = d["total"]
        correction_count = d["correction_count"]

        # Urgency bias: how much higher/lower corrections skew vs originals
        avg_orig = sum(d["urgency_original"]) / len(d["urgency_original"]) if d["urgency_original"] else 2.5
        avg_corr = sum(d["urgency_corrected"]) / len(d["urgency_corrected"]) if d["urgency_corrected"] else avg_orig
        urgency_bias = round(avg_corr - avg_orig, 2) if d["urgency_corrected"] else 0.0

        # Most common corrected owner/category
        def _most_common(lst: list[str]) -> str | None:
            if not lst:
                return None
            c = Counter(lst)
            top, _ = c.most_common(1)[0]
            return top

        typical_owner = _most_common(d["owners_corrected"])
        typical_category = _most_common(d["categories_corrected"])
        correction_rate = round(correction_count / total, 3) if total > 0 else 0.0
        profile_confidence = min(0.95, total / 20.0) if total >= _MIN_INTERACTIONS_FOR_BIAS else 0.0

        profiles[domain] = {
            "domain": domain,
            "typical_category": typical_category,
            "typical_owner": typical_owner,
            "avg_urgency": round(avg_corr, 2),
            "urgency_bias": urgency_bias,
            "correction_count": correction_count,
            "total_interactions": total,
            "correction_rate": correction_rate,
            "profile_confidence": round(profile_confidence, 3),
            "last_seen": d["last_seen"],
        }

    return profiles


def _persist_to_sqlite(profiles: dict[str, dict[str, Any]], db_path: str) -> None:
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sender_profiles (
                domain TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            )"""
        )
        for domain, profile in profiles.items():
            conn.execute(
                "INSERT OR REPLACE INTO sender_profiles (domain, profile_json, updated_at) "
                "VALUES (?, ?, datetime('now'))",
                (domain, json.dumps(profile)),
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        _log.debug("Sender intelligence: SQLite persist failed (%s).", exc)


def apply_sender_bias(
    analysis: dict[str, Any],
    domain: str,
) -> dict[str, Any]:
    """Apply sender profile bias to an existing analysis in-place.

    Only adjusts fields when profile_confidence is high enough and the
    suggested correction is meaningful (not a trivial nudge).
    """
    from .taxonomy import CATEGORIES, DEPARTMENT_OWNERS

    profile = get_sender_profile(domain)
    conf = profile.get("profile_confidence", 0.0)
    if conf < 0.4:
        return analysis

    # Nudge urgency up/down if there's a strong learned bias
    bias = profile.get("urgency_bias", 0.0)
    if abs(bias) >= 0.8 and conf >= 0.6:
        from .taxonomy import PRIORITY_LEVELS
        current_urgency = analysis.get("urgency_score") or 2
        nudged = max(1, min(5, int(round(current_urgency + bias))))
        if nudged != current_urgency:
            _URGENCY_TO_PRIORITY = {1: "Low", 2: "Normal", 3: "Normal", 4: "High", 5: "Immediate"}
            analysis["urgency_score"] = nudged
            analysis["priority_level"] = _URGENCY_TO_PRIORITY.get(nudged, "Normal")
            analysis["sender_bias_applied"] = f"urgency nudge {current_urgency}->{nudged} (domain bias={bias:+.1f})"

    # Override owner if the profile strongly prefers a different one
    typical_owner = profile.get("typical_owner")
    if (
        typical_owner
        and typical_owner in DEPARTMENT_OWNERS
        and typical_owner != analysis.get("recommended_department_owner")
        and conf >= 0.7
    ):
        analysis["recommended_department_owner"] = typical_owner
        analysis.setdefault("sender_bias_applied", "")
        analysis["sender_bias_applied"] = (
            analysis["sender_bias_applied"] + f"; owner -> {typical_owner} (domain profile)"
        ).lstrip("; ")

    return analysis

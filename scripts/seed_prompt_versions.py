"""Seed the Supabase prompt_versions table with the default Claude Analyze system prompt.

Run once after schema setup, or any time you want to sync the hardcoded prompt to Supabase
so it can be edited from the admin dashboard without a code deploy.

Usage:
    python scripts/seed_prompt_versions.py

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env or environment.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load env / bundled secrets
from outlook_dashboard.config import _load_env
_load_env()

from outlook_dashboard.ai import _build_system_prompt  # noqa: E402


def seed() -> None:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required.")
        sys.exit(1)

    prompt_text = _build_system_prompt(shared_rules=None)
    payload = {
        "prompt_key": "claude_analyze_system",
        "version": "1.0.0",
        "prompt_text": prompt_text,
        "status": "active",
        "metadata": {"description": "Default Claude Analyze system prompt — Waldorf Astoria New York"},
    }

    try:
        import httpx
    except ImportError:
        print("ERROR: httpx not installed. Run: pip install httpx")
        sys.exit(1)

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    r = httpx.post(
        f"{url}/rest/v1/prompt_versions?on_conflict=prompt_key",
        json=payload,
        headers=headers,
        timeout=15,
    )
    if r.status_code in (200, 201):
        row = r.json()
        if isinstance(row, list):
            row = row[0]
        print(f"Seeded prompt_versions: key=claude_analyze_system id={row.get('id')} version=1.0.0")
        print(f"Prompt length: {len(prompt_text)} chars")
    else:
        print(f"ERROR: Supabase returned {r.status_code}: {r.text[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    seed()

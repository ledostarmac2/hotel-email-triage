"""
Bundled credential store for ReplyRight.

This file no longer bundles privileged secrets (e.g. Supabase Service Role Key or
Anthropic API keys) via XOR obfuscation, as shipping privileged keys in a client
installer is a critical security vulnerability.

The application relies on local configuration (e.g., .env) or first-run setup UI
to obtain privileged credentials for the specific deployment environment.

Public or non-privileged keys (like SUPABASE_URL) may be stored here if absolutely
necessary, but prefer .env.
"""

from __future__ import annotations

import os
from contextlib import suppress

_SECRETS: dict[str, str] = {
    # DO NOT PUT PRIVILEGED SECRETS HERE.
    # ONLY NON-PRIVILEGED, PUBLICLY SAFE CONFIGURATION IS ALLOWED.
}

def inject() -> None:
    """Inject bundled credentials into os.environ for any key not already set."""
    for name, value in _SECRETS.items():
        if not os.environ.get(name):
            with suppress(Exception):
                os.environ[name] = value

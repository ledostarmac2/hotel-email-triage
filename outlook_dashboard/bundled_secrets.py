"""
Bundled credential store for ReplyRight.

Credentials are XOR-obfuscated so they do not appear as plaintext in git history
or compiled EXE strings. This is not cryptographic security — the keys are hotel
internal and the obfuscation is sufficient to prevent casual scraping.

To update credentials after acquiring new API keys, run:
    python scripts/seal_credentials.py

Bundled values are only injected if the corresponding environment variable is
absent, so a local .env always takes precedence.
"""

from __future__ import annotations

import base64
import os
from contextlib import suppress

_K = b"WaldorfAstoriaNYCWA"

_SECRETS: dict[str, str] = {
    "SUPABASE_URL": "PxUYFBxISW4XDA4eHAwnMCk0JzoWFgkAAQ8rFVocBxkALDgwMm80Dg==",
    "SUPABASE_KEY": "JAMzFBoQCigAHA4QBQQRPQAZeCc+XwM1IV5xFjteMC07ARAMFh4hVChUNRssAg==",
    "SUPABASE_SERVICE_ROLE_KEY": "JAMzFwoRFCQHKysHI1ALOCw+MhkMGysWPD4WHhYKOx4+egAmHxIfCwI=",
    "ANTHROPIC_API_KEY": "JApBBQEGSyADHV9BRBsrCHMcHmIrVAs9NxQgNUYNCyYLfAk7InEvMFQPBF8Sd0A9WyQgTCZrdRNzOFdaUlskAnI3NwgbLS4hdCwAeBUbAFMsA1EzKkYgAwsjJwYiGykwMCkTQkEhGRk2CDMo",
    "ANTHROPIC_MODEL": "NA0NEQsXSy4DARxfXUx5",
}


def _dec(encoded: str) -> str:
    raw = base64.b64decode(encoded)
    return bytes(d ^ _K[i % len(_K)] for i, d in enumerate(raw)).decode("utf-8")


def inject() -> None:
    """Inject bundled credentials into os.environ for any key not already set."""
    for name, encoded in _SECRETS.items():
        if not os.environ.get(name):
            with suppress(Exception):
                os.environ[name] = _dec(encoded)

"""
Run this script after updating .env to re-seal all credentials into bundled_secrets.py.

Usage:
    python scripts/seal_credentials.py

The script reads .env, encrypts each credential, and rewrites the _SECRETS dict
in outlook_dashboard/bundled_secrets.py.
"""
from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
BUNDLE_FILE = ROOT / "outlook_dashboard" / "bundled_secrets.py"

_K = b"WaldorfAstoriaNYCWA"

SEAL_KEYS = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "GOOGLE_AI_API_KEY",
    "GOOGLE_AI_MODEL",
]


def enc(value: str) -> str:
    b = value.encode("utf-8")
    return base64.b64encode(bytes(d ^ _K[i % len(_K)] for i, d in enumerate(b))).decode("ascii")


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        result[key.strip()] = val.strip()
    return result


def main() -> None:
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found.")
        sys.exit(1)

    env = load_env(ENV_FILE)
    secrets: dict[str, str] = {}
    for key in SEAL_KEYS:
        val = env.get(key, "").strip()
        if val:
            secrets[key] = enc(val)
            print(f"  sealed {key} ({len(val)} chars)")
        else:
            print(f"  SKIP   {key} (empty in .env)")

    lines = ["    \"" + k + "\": \"" + v + "\"," for k, v in secrets.items()]
    block = "\n".join(lines)

    src = BUNDLE_FILE.read_text(encoding="utf-8")
    new_src = re.sub(
        r"_SECRETS: dict\[str, str\] = \{[^}]*\}",
        "_SECRETS: dict[str, str] = {\n" + block + "\n}",
        src,
        flags=re.DOTALL,
    )
    if new_src == src:
        print("ERROR: could not locate _SECRETS block in bundled_secrets.py")
        sys.exit(1)

    BUNDLE_FILE.write_text(new_src, encoding="utf-8")
    print(f"\nDone. {BUNDLE_FILE} updated with {len(secrets)} sealed credentials.")
    print("Commit bundled_secrets.py to git — it is safe to share (obfuscated, not plaintext).")


if __name__ == "__main__":
    main()

"""Security tests: verify privileged credentials are absent from every
artifact that ships inside the installer or compiled EXE.

These tests run on the source tree before any build or tag is created.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# ── Patterns that must never appear in shippable source ──────────────────────

_ANTHROPIC_KEY_RE = re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")
_OPENAI_KEY_RE = re.compile(r"sk-proj-[A-Za-z0-9_\-]{10,}")
_GOOGLE_KEY_RE = re.compile(r"AIza[A-Za-z0-9_\-]{30,}")
_REAL_JWT_RE = re.compile(
    r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}"
)
_CLIENT_SECRET_ASSIGN_RE = re.compile(
    r"(?:client_secret|CLIENT_SECRET)\s*[=:]\s*['\"]?[A-Za-z0-9_\-\.]{12,}",
    re.IGNORECASE,
)

_DANGEROUS_PATTERNS = [
    ("Anthropic API key", _ANTHROPIC_KEY_RE),
    ("OpenAI API key", _OPENAI_KEY_RE),
    ("Google API key", _GOOGLE_KEY_RE),
    ("real JWT token", _REAL_JWT_RE),
]


# ── Test 1: full script audit ─────────────────────────────────────────────────


def test_check_no_bundled_secrets_script_passes() -> None:
    """The dedicated security-audit script must exit 0."""
    script = Path("scripts/check_no_bundled_secrets.py")
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Security audit script failed:\n{result.stdout}\n{result.stderr}"
    )


# ── Test 2: bundled_secrets.py ────────────────────────────────────────────────


def test_bundled_secrets_contains_no_privileged_key_names() -> None:
    """The _SECRETS dict must not contain any privileged key names."""
    text = Path("outlook_dashboard/bundled_secrets.py").read_text(encoding="utf-8")
    forbidden = [
        "SUPABASE_SERVICE_ROLE_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_AI_API_KEY",
        "GEMINI_API_KEY",
        "MICROSOFT_CLIENT_SECRET",
        "SMTP_PASSWORD",
    ]
    for key in forbidden:
        assert f'"{key}"' not in text and f"'{key}'" not in text, (
            f"bundled_secrets.py contains privileged key name {key!r} — remove it"
        )


def test_bundled_secrets_contains_no_real_secret_values() -> None:
    """bundled_secrets.py must not contain real API key values."""
    text = Path("outlook_dashboard/bundled_secrets.py").read_text(encoding="utf-8")
    for label, pattern in _DANGEROUS_PATTERNS:
        assert not pattern.search(text), (
            f"bundled_secrets.py appears to contain a real {label}"
        )


def test_bundled_secrets_service_role_string_absent() -> None:
    """The substring 'service_role' must not appear in bundled_secrets.py."""
    text = Path("outlook_dashboard/bundled_secrets.py").read_text(encoding="utf-8")
    assert "service_role" not in text.lower(), (
        "bundled_secrets.py contains 'service_role' — this key must never be bundled"
    )


# ── Test 3: installer artifacts ───────────────────────────────────────────────


def test_installer_iss_excludes_env_file() -> None:
    """.env must appear in an Excludes= clause in the Inno Setup script."""
    text = Path("installer/replyright_setup.iss").read_text(encoding="utf-8")
    excludes_lines = [l for l in text.splitlines() if "Excludes:" in l]
    assert excludes_lines, "No Excludes line found in replyright_setup.iss"
    excludes_text = " ".join(excludes_lines)
    assert ".env" in excludes_text, (
        ".env must be in the Inno Setup Excludes clause — "
        "removing it would bundle privileged credentials into the installer"
    )


def test_sample_env_has_no_real_secret_values() -> None:
    """installer/sample.env must contain only empty placeholders for secrets."""
    text = Path("installer/sample.env").read_text(encoding="utf-8")
    for label, pattern in _DANGEROUS_PATTERNS:
        assert not pattern.search(text), (
            f"installer/sample.env contains what looks like a real {label}"
        )
    # SERVICE_ROLE_KEY= must be present but empty
    svc_lines = [
        l for l in text.splitlines()
        if "SUPABASE_SERVICE_ROLE_KEY" in l and not l.strip().startswith("#")
    ]
    for line in svc_lines:
        _, _, val = line.partition("=")
        assert not val.strip(), (
            f"installer/sample.env has a non-empty SUPABASE_SERVICE_ROLE_KEY: {line!r}"
        )


def test_sample_env_has_no_anthropic_key() -> None:
    """installer/sample.env must not contain any provider API key values."""
    text = Path("installer/sample.env").read_text(encoding="utf-8")
    key_lines = [
        l for l in text.splitlines()
        if "ANTHROPIC_API_KEY" in l and not l.strip().startswith("#")
    ]
    for line in key_lines:
        _, _, val = line.partition("=")
        assert not val.strip(), (
            f"installer/sample.env has a non-empty ANTHROPIC_API_KEY: {line!r}"
        )


# ── Test 4: .env.example ──────────────────────────────────────────────────────


def test_env_example_has_no_service_role_key_field() -> None:
    """.env.example must not reference SUPABASE_SERVICE_ROLE_KEY at all."""
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text, (
        ".env.example must not reference SUPABASE_SERVICE_ROLE_KEY; "
        "that key is entered via the first-run credentials screen"
    )


def test_env_example_contains_no_real_secrets() -> None:
    """.env.example must contain no real API key values."""
    text = Path(".env.example").read_text(encoding="utf-8")
    for label, pattern in _DANGEROUS_PATTERNS:
        assert not pattern.search(text), (
            f".env.example appears to contain a real {label}"
        )


# ── Test 5: HTML templates ────────────────────────────────────────────────────


def test_credentials_setup_html_no_hardcoded_secrets() -> None:
    """The credentials setup page must not have pre-filled secret values."""
    text = Path("outlook_dashboard/static/credentials_setup.html").read_text(encoding="utf-8")
    for label, pattern in _DANGEROUS_PATTERNS:
        assert not pattern.search(text), (
            f"credentials_setup.html contains a real {label}"
        )


# ── Test 6: auth.py surface ───────────────────────────────────────────────────


def test_needs_credentials_setup_returns_true_when_no_supabase_url() -> None:
    """needs_credentials_setup() is True when env vars are absent."""
    from outlook_dashboard.auth import needs_credentials_setup

    saved_url = os.environ.pop("SUPABASE_URL", None)
    saved_svc = os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
    try:
        assert needs_credentials_setup() is True
    finally:
        if saved_url is not None:
            os.environ["SUPABASE_URL"] = saved_url
        if saved_svc is not None:
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = saved_svc


def test_needs_credentials_setup_returns_true_when_only_url_set() -> None:
    """needs_credentials_setup() is True when URL is set but service key is absent."""
    from outlook_dashboard.auth import needs_credentials_setup

    saved_url = os.environ.get("SUPABASE_URL")
    saved_svc = os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
    os.environ["SUPABASE_URL"] = "https://example.supabase.co"
    try:
        assert needs_credentials_setup() is True
    finally:
        if saved_url is not None:
            os.environ["SUPABASE_URL"] = saved_url
        else:
            os.environ.pop("SUPABASE_URL", None)
        if saved_svc is not None:
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = saved_svc


def test_needs_credentials_setup_returns_false_when_both_set() -> None:
    """needs_credentials_setup() is False when both URL and service key are set."""
    from outlook_dashboard.auth import needs_credentials_setup

    saved_url = os.environ.get("SUPABASE_URL")
    saved_svc = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    os.environ["SUPABASE_URL"] = "https://example.supabase.co"
    os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-service-role-key-value"
    try:
        assert needs_credentials_setup() is False
    finally:
        if saved_url is not None:
            os.environ["SUPABASE_URL"] = saved_url
        else:
            os.environ.pop("SUPABASE_URL", None)
        if saved_svc is not None:
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = saved_svc
        else:
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)


def test_admin_setup_available_false_without_service_key() -> None:
    """admin_setup_available() returns False when service-role key is absent."""
    from outlook_dashboard.auth import admin_setup_available

    saved_url = os.environ.get("SUPABASE_URL")
    saved_svc = os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
    os.environ["SUPABASE_URL"] = "https://example.supabase.co"
    try:
        assert admin_setup_available() is False
    finally:
        if saved_url is not None:
            os.environ["SUPABASE_URL"] = saved_url
        else:
            os.environ.pop("SUPABASE_URL", None)
        if saved_svc is not None:
            os.environ["SUPABASE_SERVICE_ROLE_KEY"] = saved_svc

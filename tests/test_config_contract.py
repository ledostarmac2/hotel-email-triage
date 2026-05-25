"""Contract tests: env-var access is consolidated through config.py.

Rules enforced:
- SUPABASE_URL / SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY must only be
  fetched by os.getenv inside outlook_dashboard/config.py.  All other
  modules must read them through get_settings().
- ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY must not be accessed
  via raw os.getenv outside config.py (same principle).
- No module other than config.py should import os solely to bypass Settings.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_DASHBOARD = Path("outlook_dashboard")
_CONFIG = _DASHBOARD / "config.py"

_SUPABASE_VARS = {
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
}
_AI_KEY_VARS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
}
_ALL_GUARDED_VARS = _SUPABASE_VARS | _AI_KEY_VARS

_RAW_GETENV = re.compile(
    r"""os\.getenv\s*\(\s*['"](?:""" + "|".join(_ALL_GUARDED_VARS) + r""")['"]\s*[,)]"""
)


def _py_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if p != _CONFIG]


def test_supabase_env_vars_only_in_config() -> None:
    """No raw os.getenv('SUPABASE_*') outside config.py."""
    violations: list[str] = []
    for path in _py_files(_DASHBOARD):
        text = path.read_text(encoding="utf-8")
        for var in _SUPABASE_VARS:
            pattern = re.compile(rf"""os\.getenv\s*\(\s*['\"]{re.escape(var)}['\"]""")
            for m in pattern.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                violations.append(f"{path}:{line_no}  →  {text.splitlines()[line_no-1].strip()}")
    assert not violations, (
        "Raw os.getenv for Supabase vars found outside config.py — use get_settings() instead:\n"
        + "\n".join(violations)
    )


def test_ai_key_env_vars_only_in_config() -> None:
    """No raw os.getenv for AI provider keys outside config.py."""
    violations: list[str] = []
    for path in _py_files(_DASHBOARD):
        text = path.read_text(encoding="utf-8")
        for var in _AI_KEY_VARS:
            pattern = re.compile(rf"""os\.getenv\s*\(\s*['\"]{re.escape(var)}['\"]""")
            for m in pattern.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                violations.append(f"{path}:{line_no}  →  {text.splitlines()[line_no-1].strip()}")
    assert not violations, (
        "Raw os.getenv for AI provider keys found outside config.py — use get_settings() instead:\n"
        + "\n".join(violations)
    )


def test_config_py_exposes_supabase_as_settings_fields() -> None:
    """config.py Settings must expose supabase_url, supabase_key, supabase_service_role_key."""
    text = _CONFIG.read_text(encoding="utf-8")
    for field in ("supabase_url", "supabase_key", "supabase_service_role_key"):
        assert field in text, f"config.py Settings is missing field: {field!r}"


def test_get_settings_is_importable() -> None:
    """get_settings must be importable without side effects."""
    from outlook_dashboard.config import get_settings
    s = get_settings()
    assert hasattr(s, "supabase_url")
    assert hasattr(s, "supabase_key")
    assert hasattr(s, "supabase_service_role_key")
    assert hasattr(s, "anthropic_api_key")


def test_settings_returns_strings_not_none() -> None:
    """All Settings fields must return str (possibly empty), never None."""
    from outlook_dashboard.config import get_settings
    s = get_settings()
    for attr in ("supabase_url", "supabase_key", "supabase_service_role_key", "anthropic_api_key"):
        val = getattr(s, attr)
        assert isinstance(val, str), f"get_settings().{attr} returned {type(val)!r}, expected str"

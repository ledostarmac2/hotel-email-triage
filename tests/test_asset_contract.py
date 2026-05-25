"""Contract tests: hardcoded asset paths actually exist on disk.

A missing asset is a silent runtime failure — the app launches but crashes
when it tries to serve or read the file.  These tests catch that before any
build or deploy step.
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ── Static web assets (served by FastAPI StaticFiles at /static) ──────────────

_STATIC = Path("outlook_dashboard/static")

_REQUIRED_STATIC_FILES = [
    "index.html",
    "login.html",
    "setup.html",
    "reset_password.html",
    "app.js",
    "styles.css",
    "replyright.ico",
    "replyright-logo.png",
]


@pytest.mark.parametrize("filename", _REQUIRED_STATIC_FILES)
def test_static_asset_exists(filename: str) -> None:
    path = _STATIC / filename
    assert path.exists(), f"Missing static asset: {path}"
    assert path.is_file(), f"Static asset is not a file: {path}"
    assert path.stat().st_size > 0, f"Static asset is empty: {path}"


# ── Build-time generated artifacts ────────────────────────────────────────────

def test_build_info_json_is_declared_in_add_data() -> None:
    """PyInstaller must bundle build_info.json so the running EXE can report its version."""
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "outlook_dashboard/build_info.json" in script


def test_static_dir_is_declared_in_add_data() -> None:
    """PyInstaller must bundle the entire static/ directory."""
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "outlook_dashboard/static" in script


# ── App icon ─────────────────────────────────────────────────────────────────

def test_icon_exists_and_referenced_in_build_script() -> None:
    icon = Path("outlook_dashboard/static/replyright.ico")
    assert icon.exists(), f"App icon missing: {icon}"
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "replyright.ico" in script, "build_exe.ps1 does not reference replyright.ico as --icon"


# ── Installer assets ─────────────────────────────────────────────────────────

def test_installer_iss_exists() -> None:
    assert Path("installer/replyright_setup.iss").exists()


def test_installer_sample_env_exists() -> None:
    assert Path("installer/sample.env").exists()


# ── STATIC_DIR derivation guard ──────────────────────────────────────────────

def test_static_dir_is_importable_from_config() -> None:
    """main.py resolves STATIC_DIR from DATA_DIR at import time — the directory must exist."""
    static = Path("outlook_dashboard/static")
    assert static.is_dir(), (
        "outlook_dashboard/static/ directory is missing — "
        "FastAPI StaticFiles mount will crash at startup"
    )


# ── Macro / support files ─────────────────────────────────────────────────────

def test_outlook_macro_bas_exists() -> None:
    """The Outlook VBA macro helper is bundled in static/ for user download."""
    assert (Path("outlook_dashboard/static/outlook_refresh_macro.bas")).exists()

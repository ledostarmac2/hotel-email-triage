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

def test_dockerfile_exists_for_ci_workflow() -> None:
    dockerfile = Path("Dockerfile")
    assert dockerfile.exists(), "GitHub Actions docker-build job expects a root Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")
    assert "outlook_dashboard.main:app" in text
    assert "/api/health" in text


def test_docker_compose_exists_for_local_server_smoke() -> None:
    compose = Path("docker-compose.yml")
    assert compose.exists(), "Keep docker-compose.yml for local Docker smoke checks"
    text = compose.read_text(encoding="utf-8")
    assert "replyright" in text
    assert "8000:8000" in text


def test_github_actions_use_node24_native_first_party_actions() -> None:
    workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24" not in workflow
    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "actions/checkout@v4" not in workflow
    assert "actions/setup-python@v5" not in workflow
    assert "actions/upload-artifact@v4" not in workflow


def test_release_extraction_audit_keeps_innoextract_optional() -> None:
    workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    assert '$ErrorActionPreference = "Continue"' in workflow
    assert "$chocoExit = $LASTEXITCODE" in workflow
    assert 'Get-Command "innoextract" -ErrorAction SilentlyContinue' in workflow
    assert 'Write-Warning "innoextract is unavailable' in workflow
    assert '$env:REPLYRIGHT_PAYLOAD_AUDIT = "1"' in workflow


def test_release_payload_audit_blocks_env_but_warns_on_scanner_noise() -> None:
    workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    assert 'throw "Release payload contains forbidden .env file(s): $paths"' in workflow
    assert "$payloadAuditExit = $LASTEXITCODE" in workflow
    assert 'Write-Warning "Payload secret scanner reported potential issues' in workflow
    assert "continuing release so installer can be tested" in workflow


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

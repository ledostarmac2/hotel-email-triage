from __future__ import annotations

from pathlib import Path


def test_pyinstaller_build_uses_onedir_bundle() -> None:
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "--onedir" in script
    assert "--onefile" not in script
    assert "dist\\ReplyRight\\ReplyRight.exe" in script


def test_inno_installer_bundles_onedir_app_and_excludes_runtime_secrets() -> None:
    iss = Path("installer/replyright_setup.iss").read_text(encoding="utf-8")
    assert "OutputBaseFilename=ReplyRightSetup-v{#MyAppVersion}" in iss
    assert 'Source: "..\\dist\\ReplyRight\\*"' in iss
    assert "recursesubdirs" in iss
    # Runtime-only data and local secrets must stay out of the installer.
    assert ".env" in iss
    assert "data\\*" in iss
    assert "*.sqlite3" in iss
    assert "*.log" in iss


def test_inno_installer_version_is_overridable() -> None:
    iss = Path("installer/replyright_setup.iss").read_text(encoding="utf-8")
    assert "#ifndef MyAppVersion" in iss


def test_release_workflow_uploads_setup_installer_only() -> None:
    workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "installer/output/ReplyRightSetup-v*.exe" in workflow
    assert "installer/output/ReplyRightSetup-${{ github.ref_name }}.exe" in workflow
    assert "dist/ReplyRight.exe" not in workflow
    assert ".\\dist\\ReplyRight\\ReplyRight.exe' --health-smoke" in workflow

from __future__ import annotations

from pathlib import Path


def test_pyinstaller_build_uses_onedir_bundle() -> None:
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "--onedir" in script
    assert "--onefile" not in script
    assert "dist\\ReplyRight\\ReplyRight.exe" in script


def test_build_exe_script_does_not_copy_env() -> None:
    """Ensure build_exe.ps1 does not copy .env to the packaged output."""
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "Copy-Item \".env\"" not in script
    assert "dist\\ReplyRight\\.env" not in script


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


def test_inno_installer_ships_sample_env() -> None:
    """installer/sample.env must be listed as a Source file in the .iss."""
    iss = Path("installer/replyright_setup.iss").read_text(encoding="utf-8")
    assert "sample.env" in iss


def test_sample_env_exists_and_has_required_fields() -> None:
    """installer/sample.env must exist and document the required config keys."""
    text = Path("installer/sample.env").read_text(encoding="utf-8")
    required_keys = ["SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "ANTHROPIC_API_KEY"]
    for key in required_keys:
        assert key in text, f"installer/sample.env is missing key {key!r}"


def test_sample_env_has_only_empty_values_for_secrets() -> None:
    """All privileged keys in sample.env must have empty values (placeholders only)."""
    text = Path("installer/sample.env").read_text(encoding="utf-8")
    secret_keys = ["SUPABASE_SERVICE_ROLE_KEY", "ANTHROPIC_API_KEY"]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        k, _, v = stripped.partition("=")
        if k.strip() in secret_keys:
            assert not v.strip(), (
                f"installer/sample.env has non-empty value for {k.strip()!r}: {line!r}"
            )


def test_release_workflow_uploads_setup_installer_only() -> None:
    workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "installer/output/ReplyRightSetup-v*.exe" in workflow
    assert "installer/output/ReplyRightSetup-${{ github.ref_name }}.exe" in workflow
    assert "dist/ReplyRight.exe" not in workflow
    assert ".\\dist\\ReplyRight\\ReplyRight.exe' --health-smoke" in workflow

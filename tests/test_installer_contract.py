from __future__ import annotations

from pathlib import Path


def test_pyinstaller_build_uses_onedir_bundle() -> None:
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "--onedir" in script
    assert "--onefile" not in script
    assert '$exeCandidate = Join-Path $distRoot "ReplyRight\\ReplyRight.exe"' in script
    assert "Test-RequiredPath" in script
    assert "Required build input missing" in script


def test_pyinstaller_build_bundles_kyc_selenium_dependency() -> None:
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    wrapper = Path("outlook_dashboard/kyc/automation.py").read_text(encoding="utf-8")
    launcher = Path("run_desktop.py").read_text(encoding="utf-8")
    assert "selenium" in requirements
    assert '"selenium"' in script
    assert "--collect-all selenium" in script
    assert "--collect-submodules selenium" in script
    assert "--hidden-import selenium.webdriver.edge.webdriver" in script
    assert "selenium.webdriver.edge.webdriver" in wrapper
    assert "_automation_source_path" in wrapper
    assert '"_MEIPASS"' in wrapper
    assert "--kyc-smoke" in launcher
    assert "_automation_source_path() is None" in launcher
    assert "_module() is None" in launcher


def test_build_exe_script_does_not_copy_env() -> None:
    """Ensure build_exe.ps1 does not copy .env to the packaged output."""
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert "Copy-Item \".env\"" not in script
    assert "dist\\ReplyRight\\.env" not in script


def test_installer_build_purges_runtime_env_from_payload() -> None:
    script = Path("installer/build_installer.ps1").read_text(encoding="utf-8")
    assert "Required installer input missing" in script
    assert "Get-ChildItem -LiteralPath $appDir -Recurse -Force -File" in script
    assert '$_.Name -eq ".env"' in script
    assert '$_.Name -like "*.env"' in script
    assert '$_.Name -ne "sample.env"' in script
    assert "Remove-Item -LiteralPath $envFile.FullName -Force" in script


def test_inno_installer_bundles_onedir_app_and_excludes_runtime_secrets() -> None:
    iss = Path("installer/replyright_setup.iss").read_text(encoding="utf-8")
    assert "OutputBaseFilename=ReplyRightSetup-v{#MyAppVersion}" in iss
    assert 'Source: "..\\dist\\ReplyRight\\*"' in iss
    assert "recursesubdirs" in iss
    # Runtime-only data and local secrets must stay out of the installer.
    assert 'Excludes: ".env,*.env,data\\*' in iss
    assert "data\\*" in iss
    assert "*.sqlite3" in iss
    assert "*.log" in iss


def test_inno_installer_is_per_user_and_no_admin_override() -> None:
    iss = Path("installer/replyright_setup.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss
    assert "PrivilegesRequiredOverridesAllowed" not in iss
    assert "{localappdata}\\Programs\\ReplyRight" in iss
    assert "{autopf}" not in iss
    assert "{commondesktop}" not in iss
    assert "{userdesktop}\\ReplyRight" in iss


def test_inno_installer_version_is_overridable() -> None:
    iss = Path("installer/replyright_setup.iss").read_text(encoding="utf-8")
    build_script = Path("installer/build_installer.ps1").read_text(encoding="utf-8")
    assert "#ifndef MyAppVersion" in iss
    assert "Could not read __version__" in build_script


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


def test_pyinstaller_collect_all_covers_runtime_top_level_packages() -> None:
    """--collect-all must cover every package that is imported at the top level
    of outlook_dashboard (i.e. packages that PyInstaller cannot trace lazily).

    Packages verified:
    - fastapi, starlette, pydantic: top-level imports in main.py
    - httpx: used in every Supabase HTTP function
    - anthropic: AI call path (collect-all to pick up streaming transports)
    - openai: AI call path (dynamic imports inside openai client)
    - sklearn / scikit_learn: ML classifiers
    - dateparser: date extraction
    - joblib / threadpoolctl: sklearn runtime deps
    - selenium: KYC browser automation
    - PySide6: Qt shell
    - outlook_dashboard / replyright_qt / replyright_core: local packages
    """
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    required_collect_all = [
        "fastapi",
        "starlette",
        "pydantic",
        "httpx",
        "anthropic",
        "openai",
        "sklearn",
        "scikit_learn",
        "dateparser",
        "joblib",
        "threadpoolctl",
        "selenium",
        "PySide6",
        "outlook_dashboard",
        "replyright_qt",
        "replyright_core",
    ]
    for pkg in required_collect_all:
        assert f"--collect-all {pkg}" in script, (
            f"build_exe.ps1 is missing --collect-all {pkg}"
        )


def test_release_workflow_uploads_setup_installer_only() -> None:
    workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "Upload CI installer artifact (not a release)" in workflow
    assert "ReplyRightSetup-ci-${{ github.sha }}" in workflow
    assert "installer/output/ReplyRightSetup-v*.exe" in workflow
    assert "installer/output/ReplyRightSetup-${{ github.ref_name }}.exe" in workflow
    assert "dist/ReplyRight.exe" not in workflow
    assert ".\\dist\\ReplyRight\\ReplyRight.exe' --health-smoke" in workflow

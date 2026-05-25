from __future__ import annotations

import re
import tomllib
from pathlib import Path
from unittest.mock import patch

from outlook_dashboard import __version__
from outlook_dashboard.main import app


def test_project_versions_match_runtime_version() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__


def test_installer_fallback_version_matches_runtime_version() -> None:
    iss = Path("installer/replyright_setup.iss").read_text(encoding="utf-8")
    match = re.search(r'#define MyAppVersion "([^"]+)"', iss)
    assert match, "installer/replyright_setup.iss must define a fallback MyAppVersion"
    assert match.group(1) == __version__


def test_fastapi_metadata_version_matches_runtime_version() -> None:
    assert app.version == __version__


def test_build_script_embeds_runtime_version_in_build_metadata() -> None:
    script = Path("build_exe.ps1").read_text(encoding="utf-8")
    assert 'Get-Content "outlook_dashboard\\__init__.py"' in script
    assert "$appVersion" in script
    assert '"version`":`"$appVersion`"' in script
    assert '"version`":`"0.1.0`"' not in script


def test_updater_build_info_fallback_uses_runtime_version() -> None:
    from outlook_dashboard import updater

    with patch.object(updater.Path, "exists", return_value=False):
        info = updater.get_build_info()

    assert info["version"] == __version__
    assert info["commit"] == "dev"
    assert info["build_date"] == "unknown"


def test_updater_current_version_source_is_runtime_version() -> None:
    source = Path("outlook_dashboard/updater.py").read_text(encoding="utf-8")
    assert "from . import __version__" in source
    assert "current = Version.parse(__version__)" in source

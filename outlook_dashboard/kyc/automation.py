"""Thin wrapper that loads kyc_automation.py from the bundled external source."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional

TEAM_MEMBERS = ["Hyun Song", "Eleanor Green", "Dakota Weglarz", "Brian Tarabocchia"]

_HERE = Path(__file__).resolve().parent  # outlook_dashboard/kyc/
_AUTOMATION_RELATIVE = Path(".external") / "KYC-Auto" / "Files" / "kyc_automation.py"

_cached_module = None


def _runtime_roots() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        roots.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)))
        roots.append(Path(sys.executable).resolve().parent)
    roots.extend([
        _HERE.parent.parent,
        _HERE.parent.parent.parent,
        Path.cwd(),
    ])

    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _automation_source_path() -> Path | None:
    for root in _runtime_roots():
        candidate = root / _AUTOMATION_RELATIVE
        if candidate.exists():
            return candidate
    return None


def _ensure_selenium_available() -> tuple[bool, str]:
    """Import KYC automation dependencies so PyInstaller can detect them."""
    try:
        from selenium.common.exceptions import NoSuchElementException, TimeoutException  # noqa: F401
        from selenium.webdriver.common.by import By  # noqa: F401
        from selenium.webdriver.common.keys import Keys  # noqa: F401
        from selenium.webdriver.edge.options import Options  # noqa: F401
        from selenium.webdriver.edge.service import Service  # noqa: F401
        from selenium.webdriver.edge.webdriver import WebDriver as EdgeWebDriver  # noqa: F401
        from selenium.webdriver.support import expected_conditions as EC  # noqa: F401
        from selenium.webdriver.support.ui import Select, WebDriverWait  # noqa: F401
    except ModuleNotFoundError as exc:
        return False, f"KYC automation dependency is missing: {exc}"
    except Exception as exc:
        return False, f"KYC automation dependency could not be loaded: {exc}"
    return True, ""


def _module():
    global _cached_module
    if _cached_module is None:
        automation_src = _automation_source_path()
        if automation_src is None:
            return None
        spec = importlib.util.spec_from_file_location("_kyc_automation_ext", automation_src)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _cached_module = mod
    return _cached_module


def run_kyc_inspection(
    account_name: Optional[str] = None,
    password: Optional[str] = None,
    available_team_members: Optional[list[str]] = None,
) -> tuple[bool, str]:
    ok, message = _ensure_selenium_available()
    if not ok:
        return False, message
    mod = _module()
    if mod is None:
        searched = ", ".join(str(root / _AUTOMATION_RELATIVE) for root in _runtime_roots())
        return (
            False,
            "KYC automation is not available in this build. "
            "Rebuild ReplyRight with the KYC automation bundle present, then try again. "
            f"Searched: {searched}",
        )
    return mod.run_kyc_inspection(
        account_name=account_name,
        password=password,
        available_team_members=available_team_members,
    )

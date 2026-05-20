"""Thin wrapper that loads kyc_automation.py from the bundled external source."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Optional

TEAM_MEMBERS = ["Hyun Song", "Eleanor Green", "Dakota Weglarz", "Brian Tarabocchia"]

_HERE = Path(__file__).resolve().parent            # outlook_dashboard/kyc/
_REPO_ROOT = _HERE.parent.parent                   # project root
_AUTOMATION_SRC = _REPO_ROOT / ".external" / "KYC-Auto" / "Files" / "kyc_automation.py"

_cached_module = None


def _module():
    global _cached_module
    if _cached_module is None:
        if not _AUTOMATION_SRC.exists():
            return None
        spec = importlib.util.spec_from_file_location("_kyc_automation_ext", _AUTOMATION_SRC)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _cached_module = mod
    return _cached_module


def run_kyc_inspection(
    account_name: Optional[str] = None,
    password: Optional[str] = None,
    available_team_members: Optional[list[str]] = None,
) -> tuple[bool, str]:
    mod = _module()
    if mod is None:
        return (
            False,
            "KYC automation is not available in this build. Rebuild ReplyRight with the KYC automation bundle present, then try again.",
        )
    return mod.run_kyc_inspection(
        account_name=account_name,
        password=password,
        available_team_members=available_team_members,
    )

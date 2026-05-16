from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path


class OutlookDesktopExportError(RuntimeError):
    pass


def export_mailbox_folder_to_msg(
    mailbox_name: str,
    folder_name: str,
    export_root: Path,
    macro_name: str,
) -> dict[str, object]:
    export_root.mkdir(parents=True, exist_ok=True)
    return _run_outlook_macro(macro_name, "")


def _run_outlook_macro(macro_name: str, original_error: str) -> dict[str, object]:
    if not macro_name:
        raise OutlookDesktopExportError((original_error or "Outlook desktop export failed.").strip())

    macro_json = json.dumps(macro_name)
    script = f"""
$ErrorActionPreference = "Stop"
$macroName = {macro_json}
Start-Process -FilePath "outlook.exe" -ArgumentList "/autorun", $macroName
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or original_error or "Could not start Outlook macro.").strip()
        raise OutlookDesktopExportError(detail)

    return {
        "mailbox": None,
        "folder": None,
        "export_dir": None,
        "checked_count": None,
        "exported_count": None,
        "skipped_count": None,
        "launched_macro": True,
        "macro": macro_name,
    }

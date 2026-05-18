from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .runtime_log import get_logger

DEFAULT_RELEASES_URL = "https://api.github.com/repos/ledostarmac2/hotel-email-triage/releases/latest"

_log = get_logger("updater")
_state_lock = threading.Lock()
_state: dict[str, Any] = {
    "checked": False,
    "available": False,
    "version": "",
    "url": "",
    "asset_url": "",
    "error": "",
    "downloading": False,
    "download_error": "",
}


@dataclass(frozen=True)
class Version:
    parts: tuple[int, ...]

    @classmethod
    def parse(cls, value: str) -> Version:
        digits = re.findall(r"\d+", value or "")
        return cls(tuple(int(part) for part in digits[:4]) or (0,))

    def _padded(self, length: int) -> tuple[int, ...]:
        return self.parts + (0,) * max(0, length - len(self.parts))

    def __gt__(self, other: Version) -> bool:
        length = max(len(self.parts), len(other.parts))
        return self._padded(length) > other._padded(length)


def get_build_info() -> dict[str, str]:
    """Return build metadata embedded at PyInstaller build time.

    Returns commit, build_date, and version from the bundled build_info.json.
    Falls back to __version__ with zeros when running from source without a built file.
    """
    candidates = [
        Path(__file__).parent / "build_info.json",
        Path(getattr(sys, "_MEIPASS", "")) / "outlook_dashboard" / "build_info.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {"commit": "dev", "build_date": "unknown", "version": __version__}


def start_update_check(releases_url: str = DEFAULT_RELEASES_URL) -> None:
    """Start a non-blocking latest-release check.

    The thread is daemonized and network calls time out after five seconds so
    startup is never delayed by GitHub availability.
    """
    thread = threading.Thread(target=_check_latest_release, args=(releases_url,), daemon=True)
    thread.start()


def get_update_status() -> dict[str, Any]:
    with _state_lock:
        return dict(_state)


def _set_state(**values: Any) -> None:
    with _state_lock:
        _state.update(values)


def _find_exe_asset_url(payload: dict) -> str:
    for asset in payload.get("assets", []):
        name = str(asset.get("name", "")).lower()
        if name.endswith(".exe"):
            return str(asset.get("browser_download_url", ""))
    return ""


def _check_latest_release(releases_url: str) -> None:
    try:
        request = urllib.request.Request(releases_url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        tag = str(payload.get("tag_name") or payload.get("name") or "").strip()
        html_url = str(payload.get("html_url") or payload.get("url") or "").strip()
        asset_url = _find_exe_asset_url(payload)
        latest = Version.parse(tag)
        current = Version.parse(__version__)
        available = bool(tag) and latest > current
        _set_state(
            checked=True,
            available=available,
            version=tag.lstrip("v"),
            url=html_url,
            asset_url=asset_url,
            error="",
        )
        if available:
            _log.info("ReplyRight update available: current=%s latest=%s url=%s", __version__, tag, html_url)
        else:
            _log.info("ReplyRight update check complete: current=%s latest=%s", __version__, tag or "none")
    except Exception as exc:
        _set_state(checked=True, available=False, version="", url="", asset_url="", error=str(exc)[:300])
        _log.warning("ReplyRight update check failed: %s", exc)


def download_and_apply_update(asset_url: str) -> None:
    """Download the new EXE and swap it in place via a helper script then exit.

    Runs in a background thread. The helper script waits for this process to
    exit, moves the downloaded file over ReplyRight.exe, then re-launches it.
    """
    if not asset_url:
        _set_state(download_error="No download URL available.")
        return

    _set_state(downloading=True, download_error="")
    try:
        exe_path = Path(sys.executable)
        new_exe = exe_path.with_suffix(".new.exe")
        helper = exe_path.with_name("_rr_update_helper.ps1")

        _log.info("Downloading update from %s -> %s", asset_url, new_exe)
        req = urllib.request.Request(asset_url, headers={"User-Agent": "ReplyRight-updater"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            new_exe.write_bytes(resp.read())

        helper_script = f"""
Start-Sleep -Seconds 3
$target = '{exe_path}'
$source = '{new_exe}'
try {{
    Copy-Item -Path $source -Destination $target -Force
    Remove-Item -Path $source -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath $target
}} catch {{
    [System.Windows.Forms.MessageBox]::Show("Update failed: $_", "ReplyRight Updater")
}}
Remove-Item -Path $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
"""
        helper.write_text(helper_script, encoding="utf-8")
        _log.info("Launching update helper and exiting for replacement.")
        os.startfile(str(helper))  # type: ignore[attr-defined]
        os.kill(os.getpid(), 15)  # SIGTERM — triggers lifespan shutdown
    except Exception as exc:
        _set_state(downloading=False, download_error=str(exc)[:300])
        _log.error("Update download failed: %s", exc)


def start_download(asset_url: str) -> None:
    """Start the download-and-apply flow in a background thread."""
    thread = threading.Thread(target=download_and_apply_update, args=(asset_url,), daemon=True)
    thread.start()

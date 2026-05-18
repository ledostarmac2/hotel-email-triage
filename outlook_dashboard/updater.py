from __future__ import annotations

import json
import re
import threading
import urllib.request
from dataclasses import dataclass
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
    "error": "",
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


def _check_latest_release(releases_url: str) -> None:
    try:
        request = urllib.request.Request(releases_url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        tag = str(payload.get("tag_name") or payload.get("name") or "").strip()
        html_url = str(payload.get("html_url") or payload.get("url") or "").strip()
        latest = Version.parse(tag)
        current = Version.parse(__version__)
        available = bool(tag) and latest > current
        _set_state(checked=True, available=available, version=tag.lstrip("v"), url=html_url, error="")
        if available:
            _log.info("ReplyRight update available: current=%s latest=%s url=%s", __version__, tag, html_url)
        else:
            _log.info("ReplyRight update check complete: current=%s latest=%s", __version__, tag or "none")
    except Exception as exc:
        _set_state(checked=True, available=False, version="", url="", error=str(exc)[:300])
        _log.warning("ReplyRight update check failed: %s", exc)

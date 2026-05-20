from __future__ import annotations

import json
from unittest.mock import patch

from outlook_dashboard import updater


class FakeResponse:
    payload = {
        "tag_name": "v9.9.9",
        "html_url": "https://example.com/release",
        "assets": [
            {
                "name": "ReplyRightSetup-v9.9.9.exe",
                "browser_download_url": "https://example.com/ReplyRightSetup-v9.9.9.exe",
            },
        ],
    }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_update_check_records_available_release() -> None:
    updater._set_state(checked=False, available=False, version="", url="", error="")

    with patch("urllib.request.urlopen", return_value=FakeResponse()):
        updater._check_latest_release("https://example.com/latest")

    status = updater.get_update_status()
    assert status["checked"] is True
    assert status["available"] is True
    assert status["version"] == "9.9.9"
    assert status["url"] == "https://example.com/release"
    assert status["asset_url"] == "https://example.com/ReplyRightSetup-v9.9.9.exe"


def test_update_check_ignores_bare_exe_release_asset() -> None:
    updater._set_state(checked=False, available=False, version="", url="", asset_url="", error="")

    class BareExeResponse(FakeResponse):
        payload = {
            "tag_name": "v9.9.9",
            "html_url": "https://example.com/release",
            "assets": [
                {
                    "name": "ReplyRight.exe",
                    "browser_download_url": "https://example.com/ReplyRight.exe",
                },
            ],
        }

    with patch("urllib.request.urlopen", return_value=BareExeResponse()):
        updater._check_latest_release("https://example.com/latest")

    status = updater.get_update_status()
    assert status["available"] is True
    assert status["asset_url"] == ""

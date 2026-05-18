from __future__ import annotations

import json
from unittest.mock import patch

from outlook_dashboard import updater


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps({"tag_name": "v0.1.1", "html_url": "https://example.com/release"}).encode("utf-8")


def test_update_check_records_available_release() -> None:
    updater._set_state(checked=False, available=False, version="", url="", error="")

    with patch("urllib.request.urlopen", return_value=FakeResponse()):
        updater._check_latest_release("https://example.com/latest")

    status = updater.get_update_status()
    assert status["checked"] is True
    assert status["available"] is True
    assert status["version"] == "0.1.1"
    assert status["url"] == "https://example.com/release"

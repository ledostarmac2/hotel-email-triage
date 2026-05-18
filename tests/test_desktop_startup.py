from __future__ import annotations

import socket
import urllib.error
from pathlib import Path


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_healthz_endpoint_public(app_client) -> None:
    response = app_client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_wait_for_server_health_uses_healthz(monkeypatch) -> None:
    import run_desktop

    called_urls: list[str] = []

    def opener(url: str, timeout: float = 1.0):
        called_urls.append(url)
        return _FakeResponse()

    run_desktop._wait_for_server_health("http://127.0.0.1:8123", opener=opener)

    assert called_urls == ["http://127.0.0.1:8123/healthz"]


def test_wait_for_server_health_times_out_cleanly(tmp_path: Path, monkeypatch) -> None:
    import run_desktop

    monkeypatch.setattr(run_desktop, "LOG_PATH", str(tmp_path / "startup.log"))

    def opener(url: str, timeout: float = 1.0):
        raise urllib.error.URLError("refused")

    try:
        run_desktop._wait_for_server_health(
            "http://127.0.0.1:8124",
            timeout_seconds=0.02,
            interval_seconds=0.001,
            opener=opener,
        )
    except RuntimeError as exc:
        assert "did not become healthy" in str(exc)
        assert "refused" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected RuntimeError")


def test_choose_app_port_prefers_available_port(tmp_path: Path, monkeypatch) -> None:
    import run_desktop

    monkeypatch.setattr(run_desktop, "LOG_PATH", str(tmp_path / "startup.log"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        preferred = int(sock.getsockname()[1])

    assert run_desktop._choose_app_port("127.0.0.1", preferred) == preferred


def test_choose_app_port_moves_when_preferred_is_occupied(tmp_path: Path, monkeypatch) -> None:
    import run_desktop

    monkeypatch.setattr(run_desktop, "LOG_PATH", str(tmp_path / "startup.log"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        occupied = int(sock.getsockname()[1])
        chosen = run_desktop._choose_app_port("127.0.0.1", occupied)

    assert chosen > 0
    assert chosen != occupied


def test_launcher_does_not_open_external_browser_fallback() -> None:
    source = Path("run_desktop.py").read_text(encoding="utf-8")
    assert "webbrowser.open" not in source

from __future__ import annotations

import ctypes
import logging
import os
import socket
import sys
import traceback
import threading
import time
import urllib.error
import urllib.request


ROOT_DIR = (
    os.path.dirname(os.path.abspath(sys.executable))
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
DATA_DIR = os.path.join(ROOT_DIR, "data")
LOG_PATH = os.path.join(DATA_DIR, "replyright-startup.log")

WINDOW_TITLE = "ReplyRight"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
ICON_PATH = os.path.join(ROOT_DIR, "outlook_dashboard", "static", "replyright.ico")
STARTUP_TIMEOUT_SECONDS = 30.0
HEALTH_PATH = "/healthz"


def _log(message: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as file:
            file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def _show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, WINDOW_TITLE, 0x10)
    except Exception:
        _log(message)


def _startup_error_message(reason: str) -> str:
    return (
        "ReplyRight could not start.\n\n"
        f"{reason}\n\n"
        "Please close any existing ReplyRight windows and try again.\n\n"
        f"Diagnostics log:\n{LOG_PATH}"
    )


def _is_port_available(host: str, port: int) -> bool:
    bind_host = host or "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_host, port))
        return True
    except OSError as exc:
        _log(f"Port check failed for {bind_host}:{port}: {exc}")
        return False


def _choose_app_port(host: str, preferred_port: int) -> int:
    if preferred_port <= 0:
        preferred_port = 8000
    if _is_port_available(host, preferred_port):
        return preferred_port
    bind_host = host or "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((bind_host, 0))
        port = int(sock.getsockname()[1])
    _log(f"Preferred port {bind_host}:{preferred_port} is occupied; selected {port}")
    return port


def _wait_for_server_health(
    base_url: str,
    timeout_seconds: float = STARTUP_TIMEOUT_SECONDS,
    interval_seconds: float = 0.25,
    opener=urllib.request.urlopen,
) -> None:
    health_url = f"{base_url.rstrip('/')}{HEALTH_PATH}"
    _log(f"Waiting for server health at {health_url}")
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with opener(health_url, timeout=1.0) as response:
                status = int(getattr(response, "status", 200) or 200)
                if status < 200 or status >= 300:
                    last_error = f"HTTP {status}"
                    time.sleep(interval_seconds)
                    continue
                _log("Server health check succeeded")
                return
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = repr(exc)
            time.sleep(interval_seconds)
    raise RuntimeError(
        f"The local application server did not become healthy in {timeout_seconds:.0f} seconds. "
        f"Last error: {last_error or 'no response'}"
    )


def _wait_for_server(url: str, timeout_seconds: float = STARTUP_TIMEOUT_SECONDS) -> None:
    _wait_for_server_health(url, timeout_seconds=timeout_seconds)


def _open_qt_window(url: str) -> None:
    """Open the ReplyRight UI as a native PySide6 Qt window (no browser engine)."""
    try:
        from replyright_qt.app import run_app  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            f"PySide6 is not installed. Run: pip install PySide6>=6.7\n{exc}"
        ) from exc

    _log("PySide6 imported OK — opening native Qt window")
    run_app(url)
    _log("Qt window closed by user")


def main() -> None:
    _log("ReplyRight starting")
    _log(f"Executable: {sys.executable}")
    _log(f"Frozen: {getattr(sys, 'frozen', False)}")
    _log(f"Working directory: {os.getcwd()}")
    _log(f"Root directory: {ROOT_DIR}")

    if "--native" in sys.argv or os.getenv("REPLYRIGHT_NATIVE") == "1":
        _log("--native flag noted; Qt shell is the default, continuing normal startup")

    if "--kyc-smoke" in sys.argv or os.getenv("REPLYRIGHT_KYC_SMOKE") == "1":
        from outlook_dashboard.kyc.automation import _automation_source_path, _ensure_selenium_available, _module

        ok, message = _ensure_selenium_available()
        if not ok:
            raise RuntimeError(message)
        if _automation_source_path() is None:
            raise RuntimeError("KYC automation bundle was not found in the packaged runtime.")
        if _module() is None:
            raise RuntimeError("KYC automation module could not be imported from the packaged runtime.")
        _log("KYC Selenium dependency smoke succeeded")
        return

    health_smoke_only = "--health-smoke" in sys.argv or os.getenv("REPLYRIGHT_HEALTH_SMOKE") == "1"

    try:
        _log("Importing application modules")
        import uvicorn
        from outlook_dashboard.config import get_settings
        from outlook_dashboard.main import app
    except Exception:
        _log("Application import failed")
        _log(traceback.format_exc())
        raise

    _log("Application modules imported")
    settings = get_settings()

    app_port = _choose_app_port(settings.app_host, settings.app_port)
    url = f"http://{settings.app_host}:{app_port}"
    _log(f"Settings loaded: host={settings.app_host} port={app_port} db={settings.database_path}")
    logging.basicConfig(level=logging.WARNING)

    server_error: list[str] = []

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=settings.app_host,
            port=app_port,
            reload=False,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
    )

    def run_server() -> None:
        try:
            _log("Server thread starting")
            server.run()
            _log("Server thread exited")
        except Exception:
            details = traceback.format_exc()
            server_error.append(details)
            _log("Server thread crashed")
            _log(details)

    server_thread = threading.Thread(target=run_server, daemon=True)

    try:
        server_thread.start()
        _wait_for_server_health(url)
        if server_error:
            raise RuntimeError(server_error[-1])

        if health_smoke_only:
            _log("Health smoke mode succeeded; not opening Qt window")
            return

        # _open_qt_window blocks until the user closes the ReplyRight window,
        # then we fall through to the finally block to shut down the server.
        _open_qt_window(url)

    except Exception as exc:
        _log("Startup failed")
        _log(traceback.format_exc())
        _show_error(_startup_error_message(str(exc)))
        raise
    finally:
        _log("Shutting down server")
        server.should_exit = True
        if server_thread.is_alive():
            server_thread.join(timeout=3)
        _log("ReplyRight stopped")


if __name__ == "__main__":
    main()

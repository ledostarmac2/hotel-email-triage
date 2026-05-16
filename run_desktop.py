from __future__ import annotations

import ctypes
import sys
import traceback
import logging
import os
import subprocess
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


def _log(message: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as file:
            file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def _show_error(message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "ReplyRight", 0x10)
    except Exception:
        print(message)


def _wait_for_server(url: str, timeout_seconds: float = 15.0) -> None:
    _log(f"Waiting for server at {url}")
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1.0):
                _log("Server health check succeeded")
                return
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = repr(exc)
            time.sleep(0.25)
    raise RuntimeError(f"The local application server did not start in time. Last error: {last_error}")


def _edge_path() -> str:
    candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    raise RuntimeError("Microsoft Edge is required to open the ReplyRight desktop window.")


def main() -> None:
    _log("ReplyRight starting")
    _log(f"Executable: {sys.executable}")
    _log(f"Frozen: {getattr(sys, 'frozen', False)}")
    _log(f"Working directory: {os.getcwd()}")
    _log(f"Root directory: {ROOT_DIR}")

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
    url = f"http://{settings.app_host}:{settings.app_port}"
    _log(f"Settings loaded: host={settings.app_host} port={settings.app_port} db={settings.database_path}")
    logging.basicConfig(level=logging.WARNING)

    server_error: list[str] = []

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=settings.app_host,
            port=settings.app_port,
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
        _wait_for_server(url)
        if server_error:
            raise RuntimeError(server_error[-1])
        edge_path = _edge_path()
        edge_profile = os.path.join(DATA_DIR, "edge-profile")
        os.makedirs(edge_profile, exist_ok=True)
        _log(f"Launching Edge app window: {edge_path}")
        edge = subprocess.Popen(
            [
                edge_path,
                f"--app={url}",
                f"--user-data-dir={edge_profile}",
                "--new-window",
                "--disable-features=Translate",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _log(f"Edge process started: pid={edge.pid}")
        edge_started_at = time.time()
        edge.wait()
        _log(f"Edge process exited: code={edge.returncode}")
        if time.time() - edge_started_at < 3:
            raise RuntimeError(
                "ReplyRight opened Edge, but the Edge app process closed immediately. "
                "See data/replyright-startup.log for details."
            )
    except Exception as exc:
        _log("Startup failed")
        _log(traceback.format_exc())
        _show_error(str(exc))
        raise
    finally:
        _log("Shutting down server")
        server.should_exit = True
        if server_thread.is_alive():
            server_thread.join(timeout=3)
        _log("ReplyRight stopped")


if __name__ == "__main__":
    main()

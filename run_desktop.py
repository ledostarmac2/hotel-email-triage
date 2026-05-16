from __future__ import annotations

import ctypes
import sys
import traceback
import logging
import os
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
    raise RuntimeError(
        f"The local application server did not start in time. Last error: {last_error}"
    )


def _open_window(url: str) -> None:
    """Open the ReplyRight UI in a standalone embedded WebView2 window.

    Uses pywebview with the edgechromium (WebView2) backend — this is an
    *embedded* web control, not the Edge browser.  The window appears in the
    taskbar as its own app with no address bar, tabs, or browser chrome.
    """
    try:
        import webview  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "pywebview is not installed. Run:  pip install pywebview\n"
            "Or rebuild the EXE from source with build_exe.ps1."
        ) from exc

    _log("pywebview imported OK")
    _log(f"pywebview version: {getattr(webview, '__version__', 'unknown')}")

    # Verify pythonnet (clr) is importable — it's required by pywebview's
    # edgechromium/winforms backend and causes a native crash if missing.
    try:
        import clr as _clr  # noqa: F401
        _log("pythonnet (clr) imported OK")
    except ImportError as exc:
        raise RuntimeError(
            f"pythonnet (clr) is not available: {exc}\n\n"
            "pywebview needs pythonnet to drive the Windows Forms window.\n"
            "Rebuild from source with build_exe.ps1 to include it."
        ) from exc

    window = webview.create_window(
        title=WINDOW_TITLE,
        url=url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(760, 520),
        resizable=True,
    )
    _log(f"Opening standalone WebView2 window: {url}")
    try:
        # gui='edgechromium' → Microsoft Edge WebView2 embedded control.
        # This is NOT the Edge browser. It is a self-contained runtime that is
        # pre-installed on Windows 10 21H1+ and all Windows 11 machines.
        webview.start(gui="edgechromium", debug=False)
    except Exception as exc:
        raise RuntimeError(
            f"Could not open the WebView2 window: {exc}\n\n"
            "Ensure the Microsoft Edge WebView2 Runtime is installed:\n"
            "https://developer.microsoft.com/microsoft-edge/webview2/"
        ) from exc

    _log("WebView2 window closed by user")


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

        # _open_window blocks until the user closes the ReplyRight window,
        # then we fall through to the finally block to shut down the server.
        _open_window(url)

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

from __future__ import annotations

import importlib.util
import platform
from pathlib import Path


IS_WINDOWS = platform.system().lower() == "windows"


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


HAS_OUTLOOK_COM = IS_WINDOWS and _module_available("pythoncom") and _module_available("win32com.client")
HAS_WEBVIEW = _module_available("webview")


def webview2_runtime_installed() -> bool:
    """Best-effort WebView2 runtime detection.

    The desktop app can still fall back to the system browser when this returns
    false, so detection is intentionally conservative and side-effect free.
    """
    if not IS_WINDOWS:
        return False
    try:
        import winreg
    except ImportError:
        return False

    keys = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    )
    for root, key_path in keys:
        try:
            with winreg.OpenKey(root, key_path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
                if str(version).strip():
                    return True
        except OSError:
            continue

    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        env_value = __import__("os").environ.get(env_name, "")
        if not env_value:
            continue
        base = Path(env_value)
        runtime = base / "Microsoft" / "EdgeWebView" / "Application"
        if runtime.exists() and any(runtime.glob("*/msedgewebview2.exe")):
            return True
    return False


HAS_WEBVIEW2_RUNTIME = webview2_runtime_installed()

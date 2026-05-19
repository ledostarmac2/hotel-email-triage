from __future__ import annotations

import importlib.util
import platform

IS_WINDOWS = platform.system().lower() == "windows"


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


HAS_OUTLOOK_COM = IS_WINDOWS and _module_available("pythoncom") and _module_available("win32com.client")

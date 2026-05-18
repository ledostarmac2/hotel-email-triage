from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import DATA_DIR

PREFERENCES_PATH = DATA_DIR / "preferences.json"


def _read_preferences(path: Path | None = None) -> dict[str, Any]:
    path = path or PREFERENCES_PATH
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_preferences(data: dict[str, Any], path: Path | None = None) -> None:
    path = path or PREFERENCES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


def remembered_email() -> str:
    value = _read_preferences().get("remembered_email", "")
    return str(value).strip()


def save_remembered_email(email: str) -> None:
    data = _read_preferences()
    data["remembered_email"] = email.lower().strip()
    _write_preferences(data)


def clear_remembered_email() -> None:
    data = _read_preferences()
    if "remembered_email" in data:
        data.pop("remembered_email", None)
        _write_preferences(data)

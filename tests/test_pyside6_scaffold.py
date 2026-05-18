from __future__ import annotations

from pathlib import Path


def test_qt_scaffold_does_not_import_webview_shells() -> None:
    paths = list(Path("replyright_qt").rglob("*.py"))
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "import webview" not in text
    assert "import pywebview" not in text
    assert "QWebEngineView" not in text


def test_core_scaffold_has_no_ui_framework_imports() -> None:
    paths = list(Path("replyright_core").rglob("*.py"))
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "PySide6" not in text
    assert "webview" not in text

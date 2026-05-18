from __future__ import annotations

from pathlib import Path


def _scaffold_text(root: str) -> str:
    paths = list(Path(root).rglob("*.py"))
    return "\n".join(p.read_text(encoding="utf-8") for p in paths)


def test_replyright_qt_has_no_qwebengineview() -> None:
    assert "QWebEngineView" not in _scaffold_text("replyright_qt")


def test_replyright_qt_has_no_pywebview_import() -> None:
    text = _scaffold_text("replyright_qt")
    assert "import webview" not in text
    assert "import pywebview" not in text
    assert "from webview" not in text
    assert "from pywebview" not in text


def test_replyright_qt_has_no_qtwebengine_module_import() -> None:
    text = _scaffold_text("replyright_qt")
    assert "QtWebEngine" not in text
    assert "QWebEngine" not in text


def test_replyright_qt_has_no_electron_reference() -> None:
    text = _scaffold_text("replyright_qt")
    assert "electron" not in text.lower() or "# electron" in text.lower()


def test_replyright_qt_has_no_tauri_reference() -> None:
    assert "tauri" not in _scaffold_text("replyright_qt").lower()


def test_replyright_core_has_no_pyside6_import() -> None:
    text = _scaffold_text("replyright_core")
    assert "PySide6" not in text
    assert "PyQt" not in text


def test_replyright_core_has_no_webview_import() -> None:
    text = _scaffold_text("replyright_core")
    assert "webview" not in text
    assert "QWebEngineView" not in text


def test_replyright_qt_main_raises_if_run_directly() -> None:
    source = Path("replyright_qt/main_qt.py").read_text(encoding="utf-8")
    assert "RuntimeError" in source


def test_replyright_qt_windows_have_pyside6_import_guard() -> None:
    for path in Path("replyright_qt/windows").rglob("*.py"):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "QWidget" in source or "QMainWindow" in source:
            assert "except ImportError" in source, (
                f"{path} uses Qt widgets but has no ImportError guard for PySide6"
            )

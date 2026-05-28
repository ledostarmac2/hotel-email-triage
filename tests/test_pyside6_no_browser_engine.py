from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage


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


def test_sidebar_uses_project_icon_assets() -> None:
    expected = {
        "inbox",
        "review",
        "urgent",
        "vip",
        "missing",
        "kyc",
        "settings",
        "admin",
    }
    icon_dir = Path("replyright_qt/resources/icons")

    for name in expected:
        icon_path = icon_dir / f"{name}.png"
        assert icon_path.exists(), f"Missing sidebar icon asset: {icon_path}"
        image = QImage(str(icon_path))
        assert not image.isNull(), f"Sidebar icon is not a valid image: {icon_path}"
        assert image.width() >= 64
        assert image.height() >= 64



def test_replyright_qt_windows_import_pyside6_directly() -> None:
    """PySide6 is now a real dependency — windows should import it unconditionally."""
    for path in Path("replyright_qt/windows").rglob("*.py"):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "QWidget" in source or "QMainWindow" in source:
            assert "from PySide6" in source, (
                f"{path} uses Qt widgets but does not import PySide6 directly"
            )


def test_main_window_auto_refreshes_inbox_once_on_startup() -> None:
    source = Path("replyright_qt/windows/main_window.py").read_text(encoding="utf-8")
    load_inbox_block = source.split("def load_inbox", 1)[1].split("def _on_queue_changed", 1)[0]
    assert "_load_emails()" in load_inbox_block
    assert "_auto_sync_started" in load_inbox_block
    assert "QTimer.singleShot" in load_inbox_block
    assert "self._on_sync" in load_inbox_block


def test_theme_makes_plain_labels_transparent() -> None:
    """Plain QLabel text should not paint dark strips behind settings/detail copy."""
    from replyright_qt.styles.theme import get_stylesheet

    stylesheet = get_stylesheet("dark")
    assert "QLabel {\n    background-color: transparent;\n}" in stylesheet
    # Intentional badge/chip backgrounds should remain explicitly styled.
    assert "QLabel#badge-urgency-1 { background-color:" in stylesheet
    assert "QLabel#chip {\n    background-color:" in stylesheet


def test_sidebar_nav_uses_scroll_area_for_adaptive_height() -> None:
    """The nav stack should scroll instead of squeezing brand/profile assets."""
    source = Path("replyright_qt/widgets/sidebar_nav.py").read_text(encoding="utf-8")
    assert "QScrollArea" in source
    assert 'nav_scroll.setObjectName("sidebar-scroll")' in source
    assert "nav_scroll.setWidgetResizable(True)" in source
    assert "logo.setMinimumHeight" in source
    assert "self.setMinimumHeight(54)" in source

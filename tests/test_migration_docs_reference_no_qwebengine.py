from __future__ import annotations

from pathlib import Path


def _plan() -> str:
    return Path("docs/archive/migration/PYSIDE6_MIGRATION_PLAN.md").read_text(encoding="utf-8")


def _native_ui_doc() -> str:
    return Path("docs/archive/migration/NATIVE_UI_MIGRATION.md").read_text(encoding="utf-8")


def test_migration_plan_says_no_qwebengineview() -> None:
    assert "QWebEngineView" in _plan()
    assert "not" in _plan().lower() or "must not" in _plan().lower() or "Do not" in _plan()


def test_migration_plan_names_pyside6_as_target() -> None:
    assert "PySide6" in _plan()


def test_migration_plan_does_not_list_electron_as_option() -> None:
    plan = _plan()
    assert "Electron" not in plan or "not" in plan.lower()


def test_migration_plan_does_not_list_tauri_as_option() -> None:
    plan = _plan()
    assert "Tauri" not in plan or "not" in plan.lower()


def test_migration_plan_says_native_widgets() -> None:
    plan = _plan()
    assert "native" in plan.lower()
    assert "widget" in plan.lower()


def test_migration_plan_has_acceptance_criteria() -> None:
    assert "Acceptance Criteria" in _plan() or "acceptance criteria" in _plan().lower()


def test_migration_plan_acceptance_criteria_excludes_webengine() -> None:
    assert "QWebEngineView" in _plan()


def test_native_ui_doc_references_pyside6_scaffold() -> None:
    doc = _native_ui_doc()
    assert "replyright_core" in doc or "replyright_qt" in doc or "PySide6" in doc


def test_migration_plan_mentions_no_reply_sending() -> None:
    plan = _plan()
    assert "reply" in plan.lower() and ("no" in plan.lower() or "not" in plan.lower())


def test_migration_plan_says_no_pywebview_in_new_shell() -> None:
    plan = _plan()
    assert "pywebview" in plan.lower()

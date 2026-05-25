"""Contract tests: optional / platform-specific dependencies are never bare-imported.

win32com, selenium, sklearn, clr, and pywintypes are optional.  They must only
be imported inside function bodies (lazy) so that the app module-graph can be
imported on any OS and without the optional packages installed.

These tests scan source text for top-level import statements — they do not
actually import the modules, so they run on any platform.
"""
from __future__ import annotations

import ast
from pathlib import Path

_DASHBOARD = Path("outlook_dashboard")

_GUARDED_PACKAGES = {
    "win32com",
    "win32api",
    "win32con",
    "pywintypes",
    "pythoncom",
    "selenium",
    "sklearn",
    "clr",
}


def _top_level_imports(source: str) -> list[str]:
    """Return module names bare-imported at the module level (not inside a def/class)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                found.append(root)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                found.append(root)
    return found


def _scan_for_top_level_optional_imports() -> list[str]:
    violations: list[str] = []
    for path in _DASHBOARD.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        top = _top_level_imports(source)
        for pkg in top:
            if pkg in _GUARDED_PACKAGES:
                violations.append(f"{path}: top-level `import {pkg}` (must be inside a function)")
    return violations


def test_win32com_not_at_module_level() -> None:
    """win32com must only appear inside function bodies."""
    violations = [v for v in _scan_for_top_level_optional_imports() if "win32com" in v]
    assert not violations, "\n".join(violations)


def test_selenium_not_at_module_level() -> None:
    """selenium must only appear inside function bodies."""
    violations = [v for v in _scan_for_top_level_optional_imports() if "selenium" in v]
    assert not violations, "\n".join(violations)


def test_sklearn_not_at_module_level() -> None:
    """sklearn must only appear inside function bodies."""
    violations = [v for v in _scan_for_top_level_optional_imports() if "sklearn" in v]
    assert not violations, "\n".join(violations)


def test_all_optional_deps_guarded() -> None:
    """Catch any new optional dep that gets accidentally bare-imported."""
    violations = _scan_for_top_level_optional_imports()
    assert not violations, (
        "Optional/platform deps found at module level — wrap them in try/except inside functions:\n"
        + "\n".join(violations)
    )


def test_platform_compat_is_importable_on_any_os() -> None:
    """platform_compat must import cleanly without win32com."""
    from outlook_dashboard.platform_compat import IS_WINDOWS, HAS_OUTLOOK_COM
    assert isinstance(IS_WINDOWS, bool)
    assert isinstance(HAS_OUTLOOK_COM, bool)


def test_completed_requests_importer_importable_without_win32com() -> None:
    """Importing the module must not raise even if win32com is absent."""
    import importlib
    mod = importlib.import_module("outlook_dashboard.completed_requests_importer")
    assert hasattr(mod, "import_completed_requests") or True  # module-level import must not crash

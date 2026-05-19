from __future__ import annotations

import sys

from outlook_dashboard import platform_compat


def test_platform_flags_are_booleans() -> None:
    assert isinstance(platform_compat.IS_WINDOWS, bool)
    assert isinstance(platform_compat.HAS_OUTLOOK_COM, bool)


def test_outlook_com_flag_is_windows_only() -> None:
    if platform_compat.HAS_OUTLOOK_COM:
        assert platform_compat.IS_WINDOWS


def test_runtime_platform_matches_sys_platform() -> None:
    assert platform_compat.IS_WINDOWS is sys.platform.startswith("win")

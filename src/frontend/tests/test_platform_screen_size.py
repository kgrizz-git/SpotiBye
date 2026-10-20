"""macOS screen-size lookup must never reach Tk or ask Finder via osascript."""

from __future__ import annotations

import sys

import pytest

from ..utils import platform_utils


@pytest.fixture
def on_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform_utils.platform, "system", lambda: "Darwin")
    # A Tk import or a subprocess call would mean the old crash-prone chain ran.
    monkeypatch.setitem(sys.modules, "tkinter", None)

    def _no_subprocess(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("macOS screen size must not shell out")

    monkeypatch.setattr(platform_utils.subprocess, "run", _no_subprocess)


def test_uses_coregraphics_size(
    on_macos: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        platform_utils, "_macos_main_display_size", lambda: (2560, 1440)
    )
    assert platform_utils.get_screen_resolution() == (2560, 1440)


def test_falls_back_to_default_when_coregraphics_fails(
    on_macos: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail() -> tuple[int, int]:
        raise OSError("CoreGraphics not found")

    monkeypatch.setattr(platform_utils, "_macos_main_display_size", _fail)
    assert platform_utils.get_screen_resolution() == (1920, 1080)

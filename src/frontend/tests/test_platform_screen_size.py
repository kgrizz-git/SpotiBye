"""macOS screen-size lookup must never reach Tk or ask Finder via osascript."""

from __future__ import annotations

import ctypes
import ctypes.util
import sys
from unittest.mock import MagicMock

import pytest

from ..utils import platform_utils


@pytest.fixture
def on_macos(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    monkeypatch.setattr(platform_utils.platform, "system", lambda: "Darwin")
    monkeypatch.delitem(sys.modules, "tkinter", raising=False)
    run = MagicMock()
    monkeypatch.setattr(platform_utils.subprocess, "run", run)
    return run


def _assert_no_tk_or_subprocess(run: MagicMock) -> None:
    # Checked after the call, so a swallowed exception cannot hide a regression.
    run.assert_not_called()
    assert "tkinter" not in sys.modules


def test_uses_coregraphics_size(
    on_macos: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    size = MagicMock(return_value=(2560, 1440))
    monkeypatch.setattr(platform_utils, "_macos_main_display_size", size)
    assert platform_utils.get_screen_resolution() == (2560, 1440)
    size.assert_called_once()
    _assert_no_tk_or_subprocess(on_macos)


@pytest.mark.parametrize("failure", [OSError("CoreGraphics not found"), None])
def test_falls_back_when_coregraphics_fails_or_reports_zero(
    on_macos: MagicMock, monkeypatch: pytest.MonkeyPatch, failure: Exception | None
) -> None:
    size = MagicMock(side_effect=failure, return_value=(0, 0))
    monkeypatch.setattr(platform_utils, "_macos_main_display_size", size)
    assert platform_utils.get_screen_resolution() == (1440, 900)
    _assert_no_tk_or_subprocess(on_macos)


def test_ctypes_helper_decodes_cgrect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs the real helper against a fake CoreGraphics, so it is covered on Linux."""

    class FakeCoreGraphics:
        def __init__(self) -> None:
            self.CGMainDisplayID = MagicMock(return_value=7)
            self.CGDisplayBounds = MagicMock()

    fake = FakeCoreGraphics()

    def bounds(display_id: int) -> object:
        assert display_id == 7
        rect = fake.CGDisplayBounds.restype()
        rect.size.width, rect.size.height = 1512.0, 982.0
        return rect

    fake.CGDisplayBounds.side_effect = bounds
    monkeypatch.setattr(ctypes.util, "find_library", lambda _name: "/fake/CoreGraphics")
    monkeypatch.setattr(ctypes, "CDLL", lambda _path: fake)

    assert platform_utils._macos_main_display_size() == (1512, 982)
    assert fake.CGMainDisplayID.restype is ctypes.c_uint32
    assert fake.CGDisplayBounds.argtypes == [ctypes.c_uint32]


def test_ctypes_helper_raises_without_coregraphics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ctypes.util, "find_library", lambda _name: None)
    with pytest.raises(OSError):
        platform_utils._macos_main_display_size()


@pytest.mark.skipif(sys.platform != "darwin", reason="needs real CoreGraphics")
def test_real_coregraphics_reports_a_screen() -> None:
    width, height = platform_utils._macos_main_display_size()
    assert width > 0 and height > 0
    assert platform_utils._macos_main_display_size() == (width, height)

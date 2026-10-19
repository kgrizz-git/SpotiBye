"""Tests for the pure window-icon resolver (never opens a real window)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ..utils.platform_utils import resolve_window_icon

_ICON_NAME = "SpotiBye black edited 1.png"


def test_returns_png_when_present(tmp_path: Path) -> None:
    icon = tmp_path / "resources" / _ICON_NAME
    icon.parent.mkdir()
    icon.write_bytes(b"fake")
    assert resolve_window_icon(tmp_path) == icon


def test_returns_none_when_missing(tmp_path: Path) -> None:
    assert resolve_window_icon(tmp_path) is None


def test_returns_none_when_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    icon = tmp_path / "resources" / _ICON_NAME
    icon.parent.mkdir()
    icon.write_bytes(b"fake")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert resolve_window_icon(tmp_path) is None


def test_default_root_resolves_to_existing_file() -> None:
    icon = resolve_window_icon()
    assert icon is not None
    assert icon.is_file()

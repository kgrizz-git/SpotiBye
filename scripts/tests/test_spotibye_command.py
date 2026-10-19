#!/usr/bin/env python3
"""Static checks for the macOS SpotiBye.command launcher (shell behavior is manual)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "SpotiBye.command"


def _text() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def test_launcher_exists_at_repo_root() -> None:
    assert LAUNCHER.is_file()


def test_launcher_is_lf_only() -> None:
    assert b"\r" not in LAUNCHER.read_bytes()


def test_launcher_is_executable() -> None:
    if os.name == "posix":
        assert os.access(LAUNCHER, os.X_OK)
    try:
        out = subprocess.run(
            ["git", "ls-files", "-s", "SpotiBye.command"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git index not available")
    if not out.strip():
        pytest.skip("SpotiBye.command is not tracked yet")
    assert out.startswith("100755"), out


def test_launcher_execs_frontend_entry_point() -> None:
    assert 'exec "$PY" run_frontend_backend.py' in _text()


def test_icon_block_is_guarded_by_resource_fork_check() -> None:
    text = _text()
    guard = text.index("xattr -p com.apple.ResourceFork")
    assert guard < text.index("setIconForFileOptions")


def test_launcher_does_not_use_setfile() -> None:
    assert "SetFile" not in _text()

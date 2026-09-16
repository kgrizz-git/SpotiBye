"""Tests for scripts/setup-selfhost.py (chunk A: CLI + prerequisites)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "setup_selfhost", SCRIPTS_DIR / "setup-selfhost.py"
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod  # dataclasses resolve types via sys.modules
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


def test_parse_args_defaults() -> None:
    config = _mod.parse_args([])
    assert not config.dry_run
    assert not config.check_only
    assert not config.force


def test_parse_args_flags() -> None:
    config = _mod.parse_args(["--dry-run", "--check", "--force"])
    assert config.dry_run
    assert config.check_only
    assert config.force


# ---------------------------------------------------------------------------
# prerequisites
# ---------------------------------------------------------------------------


def test_check_tool_found() -> None:
    with mock.patch.object(_mod.shutil, "which", return_value="/x"):
        result = _mod.check_tool("npm")
    assert result.ok


def test_check_tool_missing_has_hint() -> None:
    with mock.patch.object(_mod.shutil, "which", return_value=None):
        result = _mod.check_tool("npm")
    assert not result.ok
    assert "nodejs.org" in result.hint


def test_check_tool_missing_never_leaks() -> None:
    with mock.patch.object(_mod.shutil, "which", return_value=None):
        result = _mod.check_tool("openssl")
    assert "secret" not in result.hint.lower()


def test_check_python_version_current() -> None:
    assert _mod.check_python_version().ok


def test_report_all_ok() -> None:
    results = [
        _mod.PrereqResult(name="python", ok=True),
        _mod.PrereqResult(name="npm", ok=True),
    ]
    assert _mod.report_prerequisites(results)


def test_report_failure() -> None:
    results = [
        _mod.PrereqResult(name="python", ok=True),
        _mod.PrereqResult(name="npm", ok=False, hint="install it"),
    ]
    assert not _mod.report_prerequisites(results)


# ---------------------------------------------------------------------------
# portals and probes
# ---------------------------------------------------------------------------


def test_open_portal_dry_run_does_not_open_browser() -> None:
    with mock.patch.object(_mod.webbrowser, "open") as opener:
        _mod.open_portal("https://example.com", dry_run=True)
    opener.assert_not_called()


def test_run_step_success() -> None:
    ok, _ = _mod.run_step([sys.executable, "-c", "print('hi')"])
    assert ok


def test_run_step_failure() -> None:
    ok, _ = _mod.run_step([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert not ok

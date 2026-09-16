"""Tests for scripts/setup-selfhost.py (chunk A: CLI + prerequisites)."""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib.util

_SPEC = importlib.util.spec_from_file_location(
    "setup_selfhost", Path(__file__).resolve().parents[1] / "setup-selfhost.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _module  # required: dataclasses resolve types via sys.modules
_SPEC.loader.exec_module(_module)


class ParseArgsTest(unittest.TestCase):
    def test_defaults(self) -> None:
        config = _module.parse_args([])
        self.assertFalse(config.dry_run)
        self.assertFalse(config.check_only)
        self.assertFalse(config.force)

    def test_flags(self) -> None:
        config = _module.parse_args(["--dry-run", "--check", "--force"])
        self.assertTrue(config.dry_run)
        self.assertTrue(config.check_only)
        self.assertTrue(config.force)


class PrereqTest(unittest.TestCase):
    def test_check_tool_found(self) -> None:
        with mock.patch.object(_module.shutil, "which", return_value="/x"):
            result = _module.check_tool("npm")
        self.assertTrue(result.ok)

    def test_check_tool_missing_has_hint(self) -> None:
        with mock.patch.object(_module.shutil, "which", return_value=None):
            result = _module.check_tool("npm")
        self.assertFalse(result.ok)
        self.assertIn("nodejs.org", result.hint)

    def test_check_tool_missing_never_leaks(self) -> None:
        with mock.patch.object(_module.shutil, "which", return_value=None):
            result = _module.check_tool("openssl")
        self.assertNotIn("secret", result.hint.lower())

    def test_check_python_version_current(self) -> None:
        result = _module.check_python_version()
        self.assertTrue(result.ok)

    def test_report_all_ok(self) -> None:
        results = [
            _module.PrereqResult(name="python", ok=True),
            _module.PrereqResult(name="npm", ok=True),
        ]
        self.assertTrue(_module.report_prerequisites(results))

    def test_report_failure(self) -> None:
        results = [
            _module.PrereqResult(name="python", ok=True),
            _module.PrereqResult(name="npm", ok=False, hint="install it"),
        ]
        self.assertFalse(_module.report_prerequisites(results))


class PortalTest(unittest.TestCase):
    def test_open_portal_dry_run_does_not_open_browser(self) -> None:
        with mock.patch.object(_module.webbrowser, "open") as opener:
            _module.open_portal("https://example.com", dry_run=True)
        opener.assert_not_called()

    def test_run_step_success(self) -> None:
        ok, _ = _module.run_step(
            [sys.executable, "-c", "print('hi')"]
        )
        self.assertTrue(ok)

    def test_run_step_failure(self) -> None:
        ok, _ = _module.run_step(
            [sys.executable, "-c", "import sys; sys.exit(3)"]
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

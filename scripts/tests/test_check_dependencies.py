"""Tests for scripts/check-dependencies.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_dependencies", SCRIPTS_DIR / "check-dependencies.py"
)
assert _spec is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_main(*argv: str, all_pass: bool = True) -> int:
    """Call main() with all check functions mocked and sys.argv controlled."""
    check_mocks = {
        "check_python_security": mock.Mock(return_value=all_pass),
        "check_python_outdated": mock.Mock(return_value=all_pass),
        "check_node_security": mock.Mock(return_value=all_pass),
        "check_node_outdated": mock.Mock(return_value=all_pass),
    }
    with mock.patch.multiple(_mod, **check_mocks):
        with mock.patch("sys.argv", ["check-dependencies.py", *argv]):
            return _mod.main()


# ---------------------------------------------------------------------------
# main() return value
# ---------------------------------------------------------------------------


class TestMainReturnValue:
    def test_returns_zero_when_all_checks_pass(self) -> None:
        assert _run_main(all_pass=True) == 0

    def test_returns_zero_even_when_checks_fail(self) -> None:
        # Non-CI mode must always return 0; exit code is informational only.
        assert _run_main(all_pass=False) == 0

    def test_ci_mode_returns_zero_when_all_pass(self) -> None:
        assert _run_main("--ci", all_pass=True) == 0

    def test_ci_mode_exits_one_when_checks_fail(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            _run_main("--ci", all_pass=False)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# --security / --outdated flag routing
# ---------------------------------------------------------------------------


class TestFlagRouting:
    def test_security_flag_skips_outdated_checks(self) -> None:
        outdated_mock = mock.Mock(return_value=True)
        with mock.patch.multiple(
            _mod,
            check_python_security=mock.Mock(return_value=True),
            check_node_security=mock.Mock(return_value=True),
            check_python_outdated=outdated_mock,
            check_node_outdated=outdated_mock,
        ):
            with mock.patch("sys.argv", ["check-dependencies.py", "--security"]):
                _mod.main()
        outdated_mock.assert_not_called()

    def test_outdated_flag_skips_security_checks(self) -> None:
        security_mock = mock.Mock(return_value=True)
        with mock.patch.multiple(
            _mod,
            check_python_security=security_mock,
            check_node_security=security_mock,
            check_python_outdated=mock.Mock(return_value=True),
            check_node_outdated=mock.Mock(return_value=True),
        ):
            with mock.patch("sys.argv", ["check-dependencies.py", "--outdated"]):
                _mod.main()
        security_mock.assert_not_called()

    def test_no_flags_runs_all_four_checks(self) -> None:
        check_mocks = {
            k: mock.Mock(return_value=True)
            for k in [
                "check_python_security",
                "check_python_outdated",
                "check_node_security",
                "check_node_outdated",
            ]
        }
        with mock.patch.multiple(_mod, **check_mocks):
            with mock.patch("sys.argv", ["check-dependencies.py"]):
                _mod.main()
        for m in check_mocks.values():
            m.assert_called_once()


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_returns_true_on_zero_exit(self) -> None:
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)):
            assert _mod.run_command(["echo", "hi"]) is True

    def test_returns_false_on_nonzero_exit(self) -> None:
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=1)):
            assert _mod.run_command(["false"]) is False

    def test_returns_false_when_command_not_found(self) -> None:
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            assert _mod.run_command(["nonexistent-tool"]) is False

    def test_splits_string_command_before_passing_to_subprocess(self) -> None:
        with mock.patch(
            "subprocess.run", return_value=mock.Mock(returncode=0)
        ) as run_mock:
            _mod.run_command("echo hello world")
        passed_cmd = run_mock.call_args[0][0]
        assert passed_cmd == ["echo", "hello", "world"]

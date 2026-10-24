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
        "check_manifest_drift": mock.Mock(return_value=all_pass),
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

    def test_no_flags_runs_all_five_checks(self) -> None:
        check_mocks = {
            k: mock.Mock(return_value=True)
            for k in [
                "check_manifest_drift",
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


# ---------------------------------------------------------------------------
# Manifest parsing (requirements.txt ↔ pyproject.toml)
# ---------------------------------------------------------------------------


class TestParseRequirementsFile:
    def test_parses_names_specifiers_and_extras(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text(
            "kivy==2.3.1\n"
            "bandit[toml]>=1.7.8\n"
            "urllib3==2.8.0  # inline comment\n"
        )
        parsed = _mod.parse_requirements_file(req)
        assert parsed == {
            "kivy": _mod.Requirement((), "==2.3.1"),
            "bandit": _mod.Requirement(("toml",), ">=1.7.8"),
            "urllib3": _mod.Requirement((), "==2.8.0"),
        }

    def test_skips_comments_blank_lines_and_index_options(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text(
            "# a comment\n\n--index-url https://example.invalid\n"
            "--extra-index-url=https://example.invalid\npillow==13.0.0\n"
        )
        assert _mod.parse_requirements_file(req) == {
            "pillow": _mod.Requirement((), "==13.0.0")
        }

    @pytest.mark.parametrize(
        "line",
        [
            "-r other.txt",
            "-rother.txt",
            "--requirement=other.txt",
            "-c constraints.txt",
            "--constraint constraints.txt",
            "-e .",
            "--editable git+https://example.invalid/widget.git#egg=widget",
        ],
    )
    def test_rejects_options_that_hide_dependencies(
        self, tmp_path: Path, line: str
    ) -> None:
        # Skipping these would let packages bypass the drift comparison.
        req = tmp_path / "requirements.txt"
        req.write_text(f"pillow==13.0.0\n{line}\n")
        with pytest.raises(ValueError, match="unsupported option"):
            _mod.parse_requirements_file(req)

    def test_rejects_unnamed_requirement(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("./vendor/widget-1.0.whl\n")
        with pytest.raises(ValueError, match="cannot parse requirement"):
            _mod.parse_requirements_file(req)

    @pytest.mark.parametrize("line", ["widget[toml", "widget[a,b", "widget["])
    def test_rejects_unclosed_extras(self, tmp_path: Path, line: str) -> None:
        """Unclosed extras must fail, not be folded into the specifier.

        The earlier regex implementation parsed ``widget[toml`` as a name plus
        the spec ``'[toml'``, which let a malformed line into the comparison.
        The linear splitter rejects it; this pins that behaviour.
        """
        req = tmp_path / "requirements.txt"
        req.write_text(f"{line}\n")
        with pytest.raises(ValueError, match="cannot parse requirement"):
            _mod.parse_requirements_file(req)

    def test_normalizes_separators_and_case(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("Kivy_Deps.SDL2==0.8.0\n")
        assert _mod.parse_requirements_file(req) == {
            "kivy-deps-sdl2": _mod.Requirement((), "==0.8.0")
        }


class TestParsePyprojectDependencies:
    def test_reads_runtime_dependencies_only(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\n'
            'dependencies = ["kivy==2.3.1", "urllib3==2.8.0"]\n'
            '[project.optional-dependencies]\n'
            'development = ["black", "ruff==0.15.20"]\n'
        )
        assert _mod.parse_pyproject_dependencies(pyproject) == {
            "kivy": _mod.Requirement((), "==2.3.1"),
            "urllib3": _mod.Requirement((), "==2.8.0"),
        }

    def test_missing_dependencies_key_is_empty(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "spotibye"\n')
        assert _mod.parse_pyproject_dependencies(pyproject) == {}

    def test_rejects_unparseable_dependency(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\ndependencies = ["./vendor/widget-1.0.whl"]\n')
        with pytest.raises(ValueError, match="cannot parse dependency"):
            _mod.parse_pyproject_dependencies(pyproject)


class TestManifestDrift:
    def _write(
        self, tmp_path: Path, requirements: str, pyproject_deps: str
    ) -> tuple[Path, Path]:
        req = tmp_path / "requirements.txt"
        pyproject = tmp_path / "pyproject.toml"
        req.write_text(requirements)
        pyproject.write_text(f"[project]\ndependencies = {pyproject_deps}\n")
        return req, pyproject

    def test_agreeing_manifests_pass(self, tmp_path: Path) -> None:
        req, pyproject = self._write(
            tmp_path,
            "pillow==13.0.0\nurllib3==2.8.0\n",
            '["pillow==13.0.0", "urllib3==2.8.0"]',
        )
        assert _mod.check_manifest_drift(req, pyproject) is True

    def test_specifier_mismatch_fails(self, tmp_path: Path) -> None:
        req, pyproject = self._write(
            tmp_path, "pillow==13.0.0\n", '["pillow>=13.0.0"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is False

    def test_package_declared_only_in_pyproject_fails(self, tmp_path: Path) -> None:
        req, pyproject = self._write(
            tmp_path, "pillow==13.0.0\n", '["pillow==13.0.0", "spotipy>=2.25.2"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is False

    def test_package_declared_only_in_requirements_fails(self, tmp_path: Path) -> None:
        req, pyproject = self._write(
            tmp_path, "pillow==13.0.0\ncharset-normalizer==3.4.0\n", '["pillow==13.0.0"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is False

    def test_allowlisted_single_manifest_package_passes(self, tmp_path: Path) -> None:
        # pyinstaller is intentionally build-only, pinned in requirements.txt.
        req, pyproject = self._write(
            tmp_path, "pillow==13.0.0\npyinstaller==6.22.3\n", '["pillow==13.0.0"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is True

    def test_name_differences_are_normalized(self, tmp_path: Path) -> None:
        req, pyproject = self._write(
            tmp_path, "Kivy_Deps.SDL2==0.8.0\n", '["kivy-deps-sdl2==0.8.0"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is True

    def test_extras_differences_fail(self, tmp_path: Path) -> None:
        # Extras change what actually gets installed, so they must match.
        req, pyproject = self._write(
            tmp_path, "requests[security]==2.34.2\n", '["requests==2.34.2"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is False

    def test_extras_order_does_not_matter(self, tmp_path: Path) -> None:
        req, pyproject = self._write(
            tmp_path, "requests[security,socks]==2.34.2\n", '["requests[socks,security]==2.34.2"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is True

    def test_allowlisted_package_in_wrong_manifest_fails(self, tmp_path: Path) -> None:
        # pyinstaller is allowlisted for requirements.txt only; in pyproject it
        # is real drift, not a permitted difference.
        req, pyproject = self._write(
            tmp_path, "pillow==13.0.0\n", '["pillow==13.0.0", "pyinstaller==6.22.3"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is False

    def test_allowlisted_package_in_both_manifests_fails(self, tmp_path: Path) -> None:
        # Identical pins in both still mean pyinstaller became a runtime
        # dependency, which is exactly the migration the allowlist forbids.
        req, pyproject = self._write(
            tmp_path,
            "pillow==13.0.0\npyinstaller==6.22.3\n",
            '["pillow==13.0.0", "pyinstaller==6.22.3"]',
        )
        assert _mod.check_manifest_drift(req, pyproject) is False

    def test_hidden_include_fails_instead_of_passing(self, tmp_path: Path) -> None:
        req, pyproject = self._write(
            tmp_path, "pillow==13.0.0\n-r extra.txt\n", '["pillow==13.0.0"]'
        )
        assert _mod.check_manifest_drift(req, pyproject) is False

    def test_url_fragment_is_not_treated_as_a_comment(self, tmp_path: Path) -> None:
        req, pyproject = self._write(
            tmp_path,
            "widget @ https://example.invalid/widget-1.0.whl#sha256=abc\n",
            '["widget @ https://example.invalid/widget-1.0.whl#sha256=abc"]',
        )
        assert _mod.check_manifest_drift(req, pyproject) is True


class TestManifestsFlag:
    def test_manifests_flag_skips_other_checks(self) -> None:
        other = mock.Mock(return_value=True)
        drift = mock.Mock(return_value=True)
        with mock.patch.multiple(
            _mod,
            check_manifest_drift=drift,
            check_python_security=other,
            check_python_outdated=other,
            check_node_security=other,
            check_node_outdated=other,
        ):
            with mock.patch("sys.argv", ["check-dependencies.py", "--manifests"]):
                _mod.main()
        drift.assert_called_once()
        other.assert_not_called()

    def test_ci_mode_exits_one_on_drift(self) -> None:
        with mock.patch.multiple(
            _mod,
            check_manifest_drift=mock.Mock(return_value=False),
            check_python_security=mock.Mock(return_value=True),
            check_python_outdated=mock.Mock(return_value=True),
            check_node_security=mock.Mock(return_value=True),
            check_node_outdated=mock.Mock(return_value=True),
        ):
            with mock.patch(
                "sys.argv", ["check-dependencies.py", "--manifests", "--ci"]
            ):
                with pytest.raises(SystemExit) as exc_info:
                    _mod.main()
        assert exc_info.value.code == 1

    def test_manifests_exits_one_on_drift_without_ci(self) -> None:
        """Regression: the wired callers pass no --ci, so drift must still gate."""
        with mock.patch.multiple(
            _mod,
            check_manifest_drift=mock.Mock(return_value=False),
            check_python_security=mock.Mock(return_value=True),
            check_python_outdated=mock.Mock(return_value=True),
            check_node_security=mock.Mock(return_value=True),
            check_node_outdated=mock.Mock(return_value=True),
        ):
            with mock.patch("sys.argv", ["check-dependencies.py", "--manifests"]):
                with pytest.raises(SystemExit) as exc_info:
                    _mod.main()
        assert exc_info.value.code == 1

    def test_manifests_returns_zero_when_manifests_agree(self) -> None:
        with mock.patch.multiple(
            _mod,
            check_manifest_drift=mock.Mock(return_value=True),
            check_python_security=mock.Mock(return_value=True),
            check_python_outdated=mock.Mock(return_value=True),
            check_node_security=mock.Mock(return_value=True),
            check_node_outdated=mock.Mock(return_value=True),
        ):
            with mock.patch("sys.argv", ["check-dependencies.py", "--manifests"]):
                assert _mod.main() == 0


class TestRepoManifestsAgree:
    def test_real_repository_manifests_agree(self) -> None:
        """Guard the actual files, not just synthetic fixtures."""
        assert _mod.check_manifest_drift() is True

    def test_advisory_packages_stay_exactly_pinned(self) -> None:
        """Pillow and urllib3 carried PR #64's advisories.

        A floor makes them unscannable by OSV-Scanner and invisible to the
        GitHub dependency graph, so both manifests must pin them exactly.
        """
        requirements = _mod.parse_requirements_file(
            _mod.REPO_ROOT / "requirements.txt"
        )
        pyproject = _mod.parse_pyproject_dependencies(
            _mod.REPO_ROOT / "pyproject.toml"
        )
        for manifest_name, parsed in (
            ("requirements.txt", requirements),
            ("pyproject.toml", pyproject),
        ):
            for package in ("pillow", "urllib3"):
                assert package in parsed, f"{package} missing from {manifest_name}"
                assert parsed[package].spec.startswith("=="), (
                    f"{package} must be exactly pinned in {manifest_name}, "
                    f"found '{parsed[package].spec}'"
                )

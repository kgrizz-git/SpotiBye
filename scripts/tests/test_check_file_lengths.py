#!/usr/bin/env python3
"""Unit tests for scripts/check_file_lengths.py."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

# Ensure scripts directory is on sys.path for import
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_file_lengths as cfl  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]


def test_classify_path() -> None:
    # Documentation files
    assert cfl.classify_path("README.md") == cfl.CLASSIFICATION_DOC
    assert cfl.classify_path("docs/index.md") == cfl.CLASSIFICATION_DOC
    assert cfl.classify_path("dev-docs/architecture.md") == cfl.CLASSIFICATION_DOC
    assert cfl.classify_path("docs/helper.py") == cfl.CLASSIFICATION_DOC
    assert cfl.classify_path("dev-docs/scripts/helper.py") == cfl.CLASSIFICATION_DOC

    # Test files
    assert cfl.classify_path("tests/test_foo.py") == cfl.CLASSIFICATION_TEST
    assert cfl.classify_path("src/frontend/tests/test_ui.py") == cfl.CLASSIFICATION_TEST
    assert (
        cfl.classify_path("src/frontend/test_something.py") == cfl.CLASSIFICATION_TEST
    )
    assert (
        cfl.classify_path("src/frontend/something_test.py") == cfl.CLASSIFICATION_TEST
    )

    # Code files
    assert cfl.classify_path("src/frontend/main.py") == cfl.CLASSIFICATION_CODE
    assert cfl.classify_path("scripts/check_file_lengths.py") == cfl.CLASSIFICATION_CODE

    # Skipped files
    assert cfl.classify_path("src/backend/index.ts") == cfl.CLASSIFICATION_SKIP
    assert cfl.classify_path("package.json") == cfl.CLASSIFICATION_SKIP


def test_get_limit() -> None:
    assert cfl.get_limit(cfl.CLASSIFICATION_CODE) == 700
    assert cfl.get_limit(cfl.CLASSIFICATION_DOC) == 300
    assert cfl.get_limit(cfl.CLASSIFICATION_TEST) == 1000


def test_glob_exemption_matching() -> None:
    exemptions = [
        {"pattern": "src/frontend/ui/backend_playlist_card.py", "reason": "test"},
        {"pattern": "dev-docs/**/*.md", "reason": "all dev-docs markdown"},
    ]
    spec = cfl.build_exemption_spec(exemptions)

    # Direct match
    assert cfl.is_exempt("src/frontend/ui/backend_playlist_card.py", spec) is True
    assert cfl.is_exempt("src/frontend/ui/other_card.py", spec) is False

    # ** matching zero or more directories
    # File directly under dev-docs/
    assert cfl.is_exempt("dev-docs/README.md", spec) is True
    # File in nested subdirectory
    assert cfl.is_exempt("dev-docs/exec-plans/active/2026-07-07-plan.md", spec) is True
    # Non-md file under dev-docs
    assert cfl.is_exempt("dev-docs/something.py", spec) is False
    # File outside dev-docs
    assert cfl.is_exempt("docs/index.md", spec) is False


def test_scan_mode_fallback(tmp_path: Path) -> None:
    # Create valid code file
    code_dir = tmp_path / "src"
    code_dir.mkdir()
    code_file = code_dir / "app.py"
    code_file.write_text("print('hello')\n")

    # Create ignored .venv directory with oversized file
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    venv_file = venv_dir / "big.py"
    venv_file.write_text("print('x')\n" * 1500)

    # Create ignored node_modules directory
    nm_dir = tmp_path / "node_modules"
    nm_dir.mkdir()
    nm_file = nm_dir / "ignored.py"
    nm_file.write_text("print('x')\n")

    found_files = cfl.walk_repo(tmp_path, extra_excludes=[])
    # Normalize paths for comparison
    found_paths = {p.replace("\\", "/") for p in found_files}
    assert "src/app.py" in found_paths
    assert not any(p.startswith(".venv/") for p in found_paths)
    assert not any(p.startswith("node_modules/") for p in found_paths)


def test_expired_exemption_detection(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    exemptions_file = tmp_path / "exemptions.json"
    exemptions_data = {
        "exemptions": [
            {
                "pattern": "expired_file.py",
                "reason": "testing expiration",
                "expires": yesterday,
            }
        ]
    }
    exemptions_file.write_text(json.dumps(exemptions_data))

    # Create expired_file.py
    expired_file = tmp_path / "expired_file.py"
    expired_file.write_text("# code\n" * 10)

    spec = cfl.build_exemption_spec(exemptions_data["exemptions"])

    # Enforcement mode: should report expired exemption as violation (exit code 1)
    exit_code = cfl.check_files(
        file_paths=["expired_file.py"],
        repo_root=tmp_path,
        exemptions_spec=spec,
        exemptions_data=exemptions_data["exemptions"],
        warn_mode=False,
        ci_mode=False,
        extra_excludes=[],
    )
    assert exit_code == 1
    err_output = capsys.readouterr().err
    assert "exemption has expired" in err_output
    assert "ERROR:" in err_output

    # Warn mode: should report warning and return 0
    exit_code_warn = cfl.check_files(
        file_paths=["expired_file.py"],
        repo_root=tmp_path,
        exemptions_spec=spec,
        exemptions_data=exemptions_data["exemptions"],
        warn_mode=True,
        ci_mode=False,
        extra_excludes=[],
    )
    assert exit_code_warn == 0
    err_output_warn = capsys.readouterr().err
    assert "exemption has expired" in err_output_warn
    assert "WARNING:" in err_output_warn


def test_mutual_exclusivity_warn_and_ci(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exemptions_file = tmp_path / "exemptions.json"
    exemptions_file.write_text('{"exemptions": []}')

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_file_lengths.py",
            "--exemptions",
            str(exemptions_file),
            "--warn",
            "--ci",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        cfl.main()
    assert exc_info.value.code != 0


def test_check_files_warn_vs_enforce(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Create an oversized code file (> 700 lines)
    big_file = tmp_path / "big_app.py"
    big_file.write_text("x = 1\n" * 705)

    exemptions_data: list[cfl.ExemptionEntry] = []
    spec = cfl.build_exemption_spec(exemptions_data)

    # In warn mode, returns 0
    exit_code_warn = cfl.check_files(
        file_paths=["big_app.py"],
        repo_root=tmp_path,
        exemptions_spec=spec,
        exemptions_data=exemptions_data,
        warn_mode=True,
        ci_mode=False,
        extra_excludes=[],
    )
    assert exit_code_warn == 0
    err_output_warn = capsys.readouterr().err
    assert "WARNING:" in err_output_warn
    assert "exceeds 700 line limit" in err_output_warn

    # In enforce mode, returns 1
    exit_code_enforce = cfl.check_files(
        file_paths=["big_app.py"],
        repo_root=tmp_path,
        exemptions_spec=spec,
        exemptions_data=exemptions_data,
        warn_mode=False,
        ci_mode=False,
        extra_excludes=[],
    )
    assert exit_code_enforce == 1
    err_output_enforce = capsys.readouterr().err
    assert "ERROR:" in err_output_enforce
    assert "exceeds 700 line limit" in err_output_enforce

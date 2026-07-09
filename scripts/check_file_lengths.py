#!/usr/bin/env python3
"""
Pre-commit hook that checks line counts of staged files against configured limits.

Rules:
  - docs/** or dev-docs/**  → 300-line limit (documentation)
  - **/tests/** or test_*.py / *_test.py → 1000-line limit (tests)
  - All other .py files → 700-line limit (code)
  - All .md files → 300-line limit (documentation)
  - Exemptions are read from a JSON file (gitignore-style globs)

Usage:
    python scripts/check_file_lengths.py --exemptions scripts/file-length-exemptions.json [--warn] [--ci] [--count-only] [--exclude PATTERN] [file ...]

Options:
    --exemptions PATH   Required. Path to exemptions JSON file.
    --warn              Print warnings, exit 0 regardless of violations.
    --ci                Exit 1 on any violation. Mutually exclusive with --warn.
    --count-only        Print exemption count summary and exit 0. No violation reporting.
    --exclude PATTERN   Extra exclusion pattern (repeatable) for scan-mode.
                        When no filenames are given, the script walks the repo root
                        (excluding .venv/, venv/, node_modules/, build/, dist/,
                        backups/, backend-backup/, __pycache__/, plus any extra
                        --exclude patterns).

Modes:
    Default (no flags)  Enforcement: exit 1 on violations.
    --warn              Warning: exit 0 always.
    --ci                CI enforcement: exit 1 on violations, full-scan fallback.
    --count-only        Summary: exit 0, prints exemption counts only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import pathspec
except ImportError:
    print(
        "ERROR: pathspec is required. Install with: pip install -e '.[development]'",
        file=sys.stderr,
    )
    sys.exit(1)

logger = logging.getLogger("check_file_lengths")

ExemptionEntry = dict[str, str]
ExemptionSpec = pathspec.PathSpec[pathspec.pattern.Pattern]

CODE_LIMIT = 700
DOC_LIMIT = 300
TEST_LIMIT = 1000

EXCLUDE_DIRS: list[str] = [
    ".git",
    ".gemini",
    "tmp",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    "backups",
    "backend-backup",
    "__pycache__",
]

PRE_COMMIT_EXCLUDE_RE = re.compile(
    r"^backend-backup/|"
    r"^srcamas/|"
    r"^backups/|"
    r"^docs/old-docs-backup/|"
    r"^SpotifyPlaylistExporterV2-BACKUP-COPY-READ-ONLY/"
)

CLASSIFICATION_DOC = "doc"
CLASSIFICATION_TEST = "test"
CLASSIFICATION_CODE = "code"
CLASSIFICATION_SKIP = "skip"

DOC_DIR_NAMES = {"docs", "dev-docs"}
TEST_DIR_NAME = "tests"
TEST_PREFIX = "test_"
TEST_SUFFIX = "_test.py"
PY_EXT = ".py"
MD_EXT = ".md"


def classify_path(file_path: str) -> str:
    path = file_path.replace("\\", "/")

    if path.endswith(MD_EXT):
        return CLASSIFICATION_DOC

    if not path.endswith(PY_EXT):
        return CLASSIFICATION_SKIP

    parts = path.split("/")

    if set(parts) & DOC_DIR_NAMES:
        return CLASSIFICATION_DOC

    if TEST_DIR_NAME in parts:
        return CLASSIFICATION_TEST

    filename = parts[-1] if parts else path
    if filename.startswith(TEST_PREFIX) or filename.endswith(TEST_SUFFIX):
        return CLASSIFICATION_TEST

    return CLASSIFICATION_CODE


def get_limit(classification: str) -> int:
    return {
        CLASSIFICATION_DOC: DOC_LIMIT,
        CLASSIFICATION_TEST: TEST_LIMIT,
        CLASSIFICATION_CODE: CODE_LIMIT,
    }[classification]


def count_lines(file_path: Path) -> int:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def load_exemptions(exemptions_path: Path) -> list[ExemptionEntry]:
    if not exemptions_path.exists():
        raise FileNotFoundError(f"Exemptions file not found: {exemptions_path}")
    with open(exemptions_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "exemptions" not in data:
        raise ValueError("Invalid exemptions file: missing 'exemptions' key")
    return data["exemptions"]


def build_exemption_spec(exemptions: list[ExemptionEntry]) -> ExemptionSpec:
    patterns: list[str] = []
    for entry in exemptions:
        patterns.append(entry["pattern"])
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def is_exempt(file_path: str, spec: ExemptionSpec) -> bool:
    return spec.match_file(file_path)


def get_expired_entries(
    exemptions: list[ExemptionEntry], *, grace_days: int = 0
) -> tuple[list[ExemptionEntry], list[ExemptionEntry]]:
    today = date.today()
    grace_date = today - timedelta(days=grace_days)
    expired = []
    nearing = []
    for entry in exemptions:
        expires_str = entry.get("expires")
        if not expires_str:
            continue
        expires_date = datetime.fromisoformat(expires_str).date()
        if expires_date < grace_date:
            expired.append(entry)
        elif expires_date <= today + timedelta(days=7):
            nearing.append(entry)
    return expired, nearing


def print_count_only(exemptions_path: Path) -> None:
    try:
        exemptions = load_exemptions(exemptions_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    expired, nearing = get_expired_entries(exemptions)
    print(f"Total exemptions: {len(exemptions)}")
    print(f"  Active (not expired): {len(exemptions) - len(expired)}")
    print(f"  Expired: {len(expired)}")
    print(f"  Expiring within 7 days: {len(nearing)}")
    if expired:
        print("\nExpired exemptions:")
        for entry in expired:
            print(f"  {entry['pattern']} — expired {entry.get('expires', 'unknown')}")
    if nearing:
        print("\nExemptions expiring within 7 days:")
        for entry in nearing:
            print(f"  {entry['pattern']} — expires {entry.get('expires', 'unknown')}")


def should_exclude_dir(
    dir_path: Path, repo_root: Path, extra_excludes: list[str]
) -> bool:
    if dir_path.name in EXCLUDE_DIRS:
        return True
    rel_dir = str(dir_path.relative_to(repo_root))
    if PRE_COMMIT_EXCLUDE_RE.match(rel_dir + "/"):
        return True
    for pattern in extra_excludes:
        if re.match(pattern, rel_dir) or re.search(pattern, rel_dir):
            return True
    return False


def walk_repo(repo_root: Path, extra_excludes: list[str]) -> list[str]:
    files: list[str] = []
    for root_str, dirs, filenames in os.walk(repo_root):
        root_path = Path(root_str)
        dirs[:] = [
            d
            for d in dirs
            if not should_exclude_dir(root_path / d, repo_root, extra_excludes)
        ]
        for filename in filenames:
            if filename.endswith((PY_EXT, MD_EXT)):
                file_path = root_path / filename
                files.append(str(file_path.relative_to(repo_root)))
    return files


def check_files(
    file_paths: list[str],
    repo_root: Path,
    exemptions_spec: ExemptionSpec,
    exemptions_data: list[ExemptionEntry],
    warn_mode: bool,
    ci_mode: bool,
    extra_excludes: list[str],
) -> int:
    violations: list[str] = []
    warnings: list[str] = []

    if not file_paths:
        file_paths = walk_repo(repo_root, extra_excludes)

    for file_path in file_paths:
        abs_path = repo_root / file_path
        if not abs_path.exists():
            logger.debug("Skipping non-existent file: %s", file_path)
            continue

        classification = classify_path(file_path)
        if classification == CLASSIFICATION_SKIP:
            continue

        if is_exempt(file_path, exemptions_spec):
            expired, _ = get_expired_entries(exemptions_data)
            expired_patterns = {e["pattern"] for e in expired}
            if file_path in expired_patterns or any(
                pathspec.PathSpec.from_lines("gitignore", [ep]).match_file(file_path)
                for ep in expired_patterns
            ):
                prefix = "ERROR:" if not warn_mode else "WARNING:"
                msg = f"{prefix} {file_path} exemption has expired"
                violations.append(msg) if not warn_mode else warnings.append(msg)
            continue

        limit = get_limit(classification)
        line_count = count_lines(abs_path)
        label = {
            CLASSIFICATION_DOC: "documentation",
            CLASSIFICATION_TEST: "test",
            CLASSIFICATION_CODE: "code",
        }[classification]

        if line_count > limit:
            prefix = "ERROR:" if not warn_mode else "WARNING:"
            msg = f"{prefix} {file_path} has {line_count} lines, exceeds {limit} line limit for {label} files"
            guidance = [
                "Consider refactoring or splitting this file.",
                "See dev-docs/guides/file-length-policy.md for how to split large files.",
                "To add an exemption, edit scripts/file-length-exemptions.json with a reason.",
            ]
            full_msg = f"{msg}\n  " + "\n  ".join(guidance)
            if not warn_mode:
                violations.append(full_msg)
            else:
                warnings.append(full_msg)

    if warnings:
        for w in warnings:
            print(w, file=sys.stderr)
        print(
            f"\n{len(warnings)} file(s) exceed limits (warnings only).", file=sys.stderr
        )

    if violations:
        for v in violations:
            print(v, file=sys.stderr)
        print(f"\n{len(violations)} file(s) exceed limits.", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check file line counts against configured limits",
    )
    parser.add_argument(
        "--exemptions",
        required=True,
        type=Path,
        help="Path to exemptions JSON file",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Extra exclusion pattern for scan-mode (repeatable)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--warn",
        action="store_true",
        help="Print warnings only, never block the commit",
    )
    mode_group.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: exit 1 on violation, full-scan fallback",
    )
    mode_group.add_argument(
        "--count-only",
        action="store_true",
        help="Print exemption summary and exit 0; no violation reporting",
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="File paths to check (passed by pre-commit via pass_filenames: true)",
    )

    args = parser.parse_args()

    if args.count_only:
        print_count_only(args.exemptions)
        return 0

    repo_root = Path.cwd()
    warn_mode = args.warn
    ci_mode = args.ci

    try:
        exemptions_data = load_exemptions(args.exemptions)
    except (FileNotFoundError, ValueError) as e:
        msg = f"ERROR: {e}"
        if warn_mode:
            print(msg, file=sys.stderr)
            return 0
        print(msg, file=sys.stderr)
        return 1

    exemptions_spec = build_exemption_spec(exemptions_data)

    return check_files(
        file_paths=args.files,
        repo_root=repo_root,
        exemptions_spec=exemptions_spec,
        exemptions_data=exemptions_data,
        warn_mode=warn_mode,
        ci_mode=ci_mode,
        extra_excludes=args.exclude,
    )


if __name__ == "__main__":
    sys.exit(main())

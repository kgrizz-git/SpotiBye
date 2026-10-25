#!/usr/bin/env python3
"""
Local dependency checks: manifest agreement, security, and outdated packages.

This script checks for:
1. Manifest drift between `requirements.txt` and `pyproject.toml` (runtime deps)
2. Security vulnerabilities (pip-audit, npm audit)
3. Outdated packages (pip-review, npm outdated)

Security enforcement for pushes and PRs is OSV-Scanner's job (pre-commit and
GitHub Actions); the audit commands here are for ad hoc use. The manifest check
is the exception: it runs in `scripts/verify-all.sh` and the CI hygiene job
because CI installs from `pyproject.toml` while release builds install from
`requirements.txt`, so divergence silently ships a different dependency set.

Usage:
    python scripts/check-dependencies.py [--manifests] [--security] [--outdated]

Options:
    --manifests  Check only that the two manifests agree
    --security   Check only for security vulnerabilities
    --outdated   Check only for outdated packages
    (none)       Run all checks
"""

import argparse
import re
import shlex
import subprocess  # nosec: B404 - subprocess is needed for security scanning
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Canonical manifest filenames, referenced in messages and defaults.
REQUIREMENTS_FILE = "requirements.txt"
PYPROJECT_FILE = "pyproject.toml"

#: Packages that are intentionally declared in only one manifest, mapped to
#: ``(expected_file, reason)``. Anything not listed here must appear in both
#: with the same extras and specifier, and the direction is enforced so an
#: allowlisted entry cannot quietly migrate to the other manifest.
MANIFEST_ALLOWLIST: dict[str, tuple[str, str]] = {
    # build-only tool: `build.yml` bundles the app and needs PyInstaller, but it
    # is not a runtime dependency, so it stays out of the packaged metadata.
    "pyinstaller": (
        REQUIREMENTS_FILE,
        "build-only tool, pinned in requirements.txt for build.yml",
    ),
}

#: Characters allowed in a PEP 508 distribution name. Used by the linear
#: splitter below; no regex, so there is no backtracking to exploit.
_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


def run_command(cmd, cwd=None, description=None):
    """Run a shell command and return success status."""
    if description:
        print(f"\n{'=' * 60}")
        print(f"🔍 {description}")
        print("=" * 60)

    try:
        if isinstance(cmd, str):
            cmd = shlex.split(cmd)

        result = subprocess.run(  # nosec: B603 - using shell=False with validated input
            cmd, cwd=cwd, shell=False, capture_output=False, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        cmd_name = cmd.split()[0] if isinstance(cmd, str) else cmd[0]
        print(f"❌ Command not found: {cmd_name}")
        print(f"   Install with: pip install {cmd_name}")
        return False


def normalize_name(name: str) -> str:
    """Normalize a distribution name per PEP 503 (case and separators)."""
    return re.sub(r"[-_.]+", "-", name).lower()


class Requirement(NamedTuple):
    """The parts of a requirement that change what gets installed."""

    extras: tuple[str, ...]
    spec: str

    def __str__(self) -> str:
        extras = f"[{','.join(self.extras)}]" if self.extras else ""
        return f"{extras}{self.spec}"


def _strip_comment(line: str) -> str:
    """Drop a pip-style comment without eating URL fragments.

    pip only treats ``#`` as a comment when it starts the line or follows
    whitespace, so ``name @ https://host/path#sha256=...`` keeps its fragment.
    """
    if line.lstrip().startswith("#"):
        return ""
    marker = re.search(r"\s#", line)
    if marker is not None:
        line = line[: marker.start()]
    return line.strip()


def _parse_requirement(line: str) -> tuple[str, Requirement] | None:
    """Split ``name[extras]specifier`` without a backtracking-prone regex."""
    text = line.strip()
    end = 0
    while end < len(text) and text[end] in _NAME_CHARS:
        end += 1
    name = text[:end]
    if not name or not name[0].isalnum():
        return None

    rest = text[end:]
    extras: tuple[str, ...] = ()
    if rest.startswith("["):
        close = rest.find("]")
        if close == -1:
            return None
        extras = tuple(
            sorted(
                normalize_name(extra.strip())
                for extra in rest[1:close].split(",")
                if extra.strip()
            )
        )
        rest = rest[close + 1 :]

    return normalize_name(name), Requirement(extras, rest.strip())


#: The only requirements-file options accepted. Each one selects where packages
#: come from, never which packages or versions are installed. Every unlisted
#: option is rejected, so resolution-changing flags (``--pre``, ``--find-links``,
#: ``--requirement``, ``--constraint``, ``--editable``, ...) cannot smuggle
#: dependencies past the drift comparison.
_ALLOWED_LONG_OPTIONS = (
    "--index-url",
    "--extra-index-url",
    "--trusted-host",
    "--no-cache-dir",
)
_ALLOWED_SHORT_OPTIONS = ("-i",)


def _is_allowed_option(line: str) -> bool:
    option = re.split(r"[\s=]", line, maxsplit=1)[0]
    if option.startswith("--"):
        return option in _ALLOWED_LONG_OPTIONS
    # Short options may be glued to their value, e.g. ``-ihttps://host``.
    return option[:2] in _ALLOWED_SHORT_OPTIONS


def parse_requirements_file(path: Path) -> dict[str, Requirement]:
    """Return ``{normalized_name: Requirement}`` for a requirements.txt file.

    Only allow-listed installer options are skipped; any other option, a
    duplicate normalized name, or a line that is not a named requirement raises
    ``ValueError`` so nothing escapes the comparison.
    """
    requirements: dict[str, Requirement] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = _strip_comment(raw_line)
        if not line:
            continue
        if line.startswith("-"):
            if not _is_allowed_option(line):
                raise ValueError(f"{path.name}: unsupported option '{line}'")
            continue
        parsed = _parse_requirement(line)
        if parsed is None:
            raise ValueError(f"{path.name}: cannot parse requirement '{line}'")
        if parsed[0] in requirements:
            raise ValueError(f"{path.name}: duplicate requirement for '{parsed[0]}'")
        requirements[parsed[0]] = parsed[1]
    return requirements


def parse_pyproject_dependencies(path: Path) -> dict[str, Requirement]:
    """Return ``{normalized_name: Requirement}`` for ``[project].dependencies``.

    ``[project.optional-dependencies]`` is deliberately excluded: developer
    tooling (ruff, black, bandit, pytest, ...) legitimately exists only there
    and is never bundled into the released application. A duplicate normalized
    name raises ``ValueError`` rather than silently overwriting an earlier pin.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    dependencies: dict[str, Requirement] = {}
    for entry in data.get("project", {}).get("dependencies", []):
        parsed = _parse_requirement(entry.strip())
        if parsed is None:
            raise ValueError(f"{path.name}: cannot parse dependency '{entry}'")
        if parsed[0] in dependencies:
            raise ValueError(f"{path.name}: duplicate dependency for '{parsed[0]}'")
        dependencies[parsed[0]] = parsed[1]
    return dependencies


def _compare_manifests(
    requirements: dict[str, Requirement], pyproject: dict[str, Requirement]
) -> list[str]:
    """Return one human-readable problem per disagreeing package."""
    problems: list[str] = []
    for name in sorted(requirements.keys() | pyproject.keys()):
        in_requirements = name in requirements
        in_pyproject = name in pyproject
        allowed = MANIFEST_ALLOWLIST.get(name)
        if in_requirements and in_pyproject:
            if allowed is not None:
                # Declaring a single-manifest package in both is the migration
                # the allowlist exists to catch (e.g. pyinstaller as runtime).
                problems.append(
                    f"{name}: allowlisted for {allowed[0]} only but declared in both"
                )
            elif requirements[name] != pyproject[name]:
                problems.append(
                    f"{name}: {REQUIREMENTS_FILE} has '{requirements[name]}' but "
                    f"{PYPROJECT_FILE} has '{pyproject[name]}'"
                )
            continue
        present_in = REQUIREMENTS_FILE if in_requirements else PYPROJECT_FILE
        if allowed is None:
            problems.append(f"{name}: declared only in {present_in}")
        elif allowed[0] != present_in:
            problems.append(
                f"{name}: allowlisted for {allowed[0]} but declared in {present_in}"
            )
    return problems


def check_manifest_drift(
    requirements_path: Path | None = None, pyproject_path: Path | None = None
) -> bool:
    """Fail when the runtime dependency manifests disagree."""
    requirements_path = requirements_path or REPO_ROOT / REQUIREMENTS_FILE
    pyproject_path = pyproject_path or REPO_ROOT / PYPROJECT_FILE

    print(
        f"\n📦 Python Manifest Agreement ({REQUIREMENTS_FILE} ↔ {PYPROJECT_FILE})"
    )
    try:
        requirements = parse_requirements_file(requirements_path)
        pyproject = parse_pyproject_dependencies(pyproject_path)
    except ValueError as error:
        print(f"❌ {error}")
        return False

    problems = _compare_manifests(requirements, pyproject)
    if problems:
        print(f"❌ {len(problems)} mismatch(es):")
        for problem in problems:
            print(f"   - {problem}")
        print(
            "\n   Fix by making the specifiers identical in both files, or add the"
            " package to MANIFEST_ALLOWLIST in scripts/check-dependencies.py with the"
            " expected file and a reason if it is intentionally single-manifest."
        )
        return False

    shared = len(requirements.keys() & pyproject.keys())
    print(f"✅ {shared} runtime dependencies agree across both manifests")
    return True


def check_python_security():
    """Check Python dependencies for known vulnerabilities."""
    print("\n📦 Python Security Check (pip-audit)")
    return run_command(
        "pip-audit --requirement=requirements.txt --desc",
        description="Scanning Python dependencies for CVEs",
    )


def check_python_outdated():
    """Check for outdated Python packages."""
    print("\n📦 Python Outdated Packages (pip-review)")
    success = run_command(
        "pip-review --local", description="Checking for outdated Python packages"
    )
    if not success:
        print("\n💡 To update packages, run: pip-review --local --auto")
    return success


def check_node_security():
    """Check Node.js dependencies for known vulnerabilities."""
    backend_dir = Path("src/backend")
    if not backend_dir.exists():
        print("⚠️  Backend directory not found, skipping Node.js checks")
        return True

    print("\n📦 Node.js Security Check (npm audit)")
    return run_command(
        "npm audit",
        cwd=str(backend_dir),
        description="Scanning Node.js dependencies for CVEs",
    )


def check_node_outdated():
    """Check for outdated Node.js packages."""
    backend_dir = Path("src/backend")
    if not backend_dir.exists():
        print("⚠️  Backend directory not found, skipping Node.js checks")
        return True

    print("\n📦 Node.js Outdated Packages (npm outdated)")
    return run_command(
        "npm outdated",
        cwd=str(backend_dir),
        description="Checking for outdated Node.js packages",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Check dependencies for manifest drift, security issues and updates"
    )
    parser.add_argument(
        "--manifests",
        action="store_true",
        help="Check only that requirements.txt and pyproject.toml agree",
    )
    parser.add_argument(
        "--security",
        action="store_true",
        help="Check only for security vulnerabilities",
    )
    parser.add_argument(
        "--outdated", action="store_true", help="Check only for outdated packages"
    )
    parser.add_argument(
        "--ci", action="store_true", help="CI mode - fail on any finding (exit code 1)"
    )

    args = parser.parse_args()

    # No mode flag means "run everything"; otherwise run exactly what was asked.
    explicit_mode = args.manifests or args.security or args.outdated
    run_manifests = args.manifests or not explicit_mode
    run_security = args.security or not explicit_mode
    run_outdated = args.outdated or not explicit_mode

    results = []

    if run_manifests:
        results.append(("Manifest drift", check_manifest_drift()))

    if run_security:
        results.append(("Python Security", check_python_security()))
        results.append(("Node.js Security", check_node_security()))

    if run_outdated:
        results.append(("Python Outdated", check_python_outdated()))
        results.append(("Node.js Outdated", check_node_outdated()))

    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")
        if not passed:
            all_passed = False

    print("\n💡 Tips:")
    print("  - Security issues should be fixed immediately")
    print("  - Outdated packages: review changelogs before updating")
    print("  - Use: pip-review --local --auto  (to auto-update Python)")
    print("  - Use: npm update  (to update Node.js packages)")
    print("  - Use: ncu -u && npm install  (for major Node.js updates)")

    # `--manifests` is a correctness gate: drift is always a bug, so it exits
    # non-zero whenever it was explicitly requested, with or without --ci.
    # Other modes stay informational locally and only gate under --ci.
    if not all_passed and (args.ci or args.manifests):
        sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())

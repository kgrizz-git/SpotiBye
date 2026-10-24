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

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Packages that are intentionally declared in only one manifest, with the
#: reason. Anything not listed here must appear in both with the same specifier.
MANIFEST_ALLOWLIST: dict[str, str] = {
    # build-only tool: `build.yml` bundles the app and needs PyInstaller, but it
    # is not a runtime dependency, so it stays out of the packaged metadata.
    "pyinstaller": "build-only tool, pinned in requirements.txt for build.yml",
}

#: PEP 508 name + optional extras + version specifier. Options (-r, -e) and
#: comments are handled before this pattern is applied.
_REQUIREMENT_RE = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?P<extras>\[[^\]]*\])?(?P<spec>.*)$")


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


def parse_requirements_file(path: Path) -> dict[str, str]:
    """Return ``{normalized_name: specifier}`` for a requirements.txt file."""
    requirements: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = _REQUIREMENT_RE.match(line)
        if match is None:
            continue
        requirements[normalize_name(match.group("name"))] = match.group("spec").strip()
    return requirements


def parse_pyproject_dependencies(path: Path) -> dict[str, str]:
    """Return ``{normalized_name: specifier}`` for ``[project].dependencies``.

    ``[project.optional-dependencies]`` is deliberately excluded: developer
    tooling (ruff, black, bandit, pytest, ...) legitimately exists only there
    and is never bundled into the released application.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    dependencies: dict[str, str] = {}
    for entry in data.get("project", {}).get("dependencies", []):
        match = _REQUIREMENT_RE.match(entry.strip())
        if match is None:
            continue
        dependencies[normalize_name(match.group("name"))] = match.group("spec").strip()
    return dependencies


def check_manifest_drift(
    requirements_path: Path | None = None, pyproject_path: Path | None = None
) -> bool:
    """Fail when the runtime dependency manifests disagree."""
    requirements_path = requirements_path or REPO_ROOT / "requirements.txt"
    pyproject_path = pyproject_path or REPO_ROOT / "pyproject.toml"

    requirements = parse_requirements_file(requirements_path)
    pyproject = parse_pyproject_dependencies(pyproject_path)

    problems: list[str] = []
    for name in sorted(requirements.keys() | pyproject.keys()):
        in_requirements = name in requirements
        in_pyproject = name in pyproject
        if in_requirements and in_pyproject:
            if requirements[name] != pyproject[name]:
                problems.append(
                    f"{name}: requirements.txt has '{requirements[name]}' but "
                    f"pyproject.toml has '{pyproject[name]}'"
                )
            continue
        if name in MANIFEST_ALLOWLIST:
            continue
        only = "requirements.txt" if in_requirements else "pyproject.toml"
        problems.append(f"{name}: declared only in {only}")

    print("\n📦 Python Manifest Agreement (requirements.txt ↔ pyproject.toml)")
    if problems:
        print(f"❌ {len(problems)} mismatch(es):")
        for problem in problems:
            print(f"   - {problem}")
        print(
            "\n   Fix by making the specifiers identical in both files, or add the"
            " package to MANIFEST_ALLOWLIST in scripts/check-dependencies.py with a"
            " reason if it is intentionally single-manifest."
        )
        return False

    print(f"✅ {len(requirements)} runtime dependencies agree across both manifests")
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

    if args.ci and not all_passed:
        sys.exit(1)

    return 0


if __name__ == "__main__":
    sys.exit(main())

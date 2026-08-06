#!/usr/bin/env python3
"""
Local ad hoc dependency security and update checker.

This script checks for:
1. Security vulnerabilities (pip-audit, npm audit)
2. Outdated packages (pip-review, npm outdated)

This script is intended for manual use. Automated pre-push and PR dependency
vulnerability enforcement is handled by OSV-Scanner in pre-commit and GitHub
Actions to avoid maintaining multiple blocking scanners with overlapping output.

Usage:
    python scripts/check-dependencies.py [--security] [--outdated]

Options:
    --security   Check only for security vulnerabilities
    --outdated   Check only for outdated packages
    (none)       Run both checks
"""

import subprocess  # nosec: B404 - subprocess is needed for security scanning
import sys
import argparse
import shlex
from pathlib import Path


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
        description="Check dependencies for security issues and updates"
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

    # If neither flag specified, run both
    run_security = not args.outdated or args.security
    run_outdated = not args.security or args.outdated

    results = []

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

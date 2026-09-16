#!/usr/bin/env python3
"""Interactive SpotiBye self-host setup.

Walks a user through registering their own Spotify app and backend:
checks prerequisites, opens portal pages, collects credentials, validates
them, and writes local config. Never prints secret values.

Usage:
    python scripts/setup-selfhost.py [--dry-run] [--check] [--force]

Options:
    --dry-run  Print what would be done without writing anything.
    --check    Verify prerequisites only, then exit.
    --force    Allow overwriting an existing .dev.vars.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess  # nosec B404 - subprocess is needed for tool checks
import sys
import webbrowser
from dataclasses import dataclass, field


SPOTIFY_DASHBOARD_URL = "https://developer.spotify.com/dashboard"
CLOUDFLARE_DASHBOARD_URL = "https://dash.cloudflare.com/"

REQUIRED_PYTHON = (3, 10)
REQUIRED_TOOLS = ("node", "npm", "npx", "openssl")


@dataclass
class PrereqResult:
    """Outcome of a single prerequisite check."""

    name: str
    ok: bool
    hint: str = ""


@dataclass
class SetupConfig:
    """Runtime options for the setup flow."""

    dry_run: bool = False
    check_only: bool = False
    force: bool = False
    failures: list[str] = field(default_factory=list)


def parse_args(argv: list[str] | None = None) -> SetupConfig:
    """Parse command-line flags into a SetupConfig."""
    parser = argparse.ArgumentParser(
        description="Interactive SpotiBye self-host setup."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing anything.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify prerequisites only, then exit.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing .dev.vars.",
    )
    args = parser.parse_args(argv)
    return SetupConfig(
        dry_run=args.dry_run, check_only=args.check, force=args.force
    )


def check_python_version() -> PrereqResult:
    """Verify the running interpreter meets the minimum version."""
    if sys.version_info >= REQUIRED_PYTHON:
        return PrereqResult(name="python", ok=True)
    return PrereqResult(
        name="python",
        ok=False,
        hint=(
            "Python >=3.10 is required "
            f"(running {sys.version.split()[0]}). "
            "Install from https://www.python.org/downloads/"
        ),
    )


def check_tool(name: str) -> PrereqResult:
    """Verify a CLI tool is on PATH, with a copy-pasteable fix."""
    if shutil.which(name) is not None:
        return PrereqResult(name=name, ok=True)
    fixes = {
        "node": "Install Node 24 (see .nvmrc): https://nodejs.org/",
        "npm": "npm ships with Node: https://nodejs.org/",
        "npx": "npx ships with Node: https://nodejs.org/",
        "openssl": "macOS/Linux ship openssl; Windows: use Git Bash or "
        "https://slproweb.com/products/Win32OpenSSL.html",
    }
    return PrereqResult(
        name=name, ok=False, hint=fixes.get(name, f"Install {name}.")
    )


def check_prerequisites() -> list[PrereqResult]:
    """Run all prerequisite checks and return the results."""
    results = [check_python_version()]
    results.extend(check_tool(tool) for tool in REQUIRED_TOOLS)
    return results


def report_prerequisites(results: list[PrereqResult]) -> bool:
    """Print a one-screen prerequisite summary. Returns True if all pass."""
    failed = [r for r in results if not r.ok]
    for result in results:
        status = "ok" if result.ok else "MISSING"
        print(f"  [{status}] {result.name}")
    if not failed:
        print("All prerequisites satisfied.")
        return True
    print("\nFix the missing items, then re-run:")
    for result in failed:
        print(f"  - {result.name}: {result.hint}")
    return False


def open_portal(url: str, dry_run: bool = False) -> None:
    """Open a portal page in the user's browser (or print it dry-run)."""
    if dry_run:
        print(f"  [dry-run] would open: {url}")
        return
    webbrowser.open(url)
    print(f"  Opened in your browser: {url}")


def run_step(cmd: list[str]) -> tuple[bool, str]:
    """Run a read-only probe command, returning (ok, output)."""
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, no shell
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output


def main(argv: list[str] | None = None) -> int:
    """Entry point: check prerequisites, then run the guided flow."""
    config = parse_args(argv)
    print("SpotiBye self-host setup — prerequisite check")
    results = check_prerequisites()
    if not report_prerequisites(results):
        return 1
    if config.check_only:
        return 0
    print("\nStep 1: register a Spotify app")
    open_portal(SPOTIFY_DASHBOARD_URL, dry_run=config.dry_run)
    print("\nCredential collection and validation land in the next chunk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

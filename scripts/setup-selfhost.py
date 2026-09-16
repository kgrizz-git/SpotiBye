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
import base64
import getpass
import json
import secrets
import shutil
import subprocess  # nosec B404 - subprocess is needed for tool checks
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path


SPOTIFY_DASHBOARD_URL = "https://developer.spotify.com/dashboard"
CLOUDFLARE_DASHBOARD_URL = "https://dash.cloudflare.com/"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

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


def repo_root() -> Path:
    """Return the repository root (parent of scripts/)."""
    return Path(__file__).resolve().parent.parent


def prompt_client_id() -> str:
    """Prompt for the Spotify Client ID, validating format immediately."""
    while True:
        value = input("  Spotify Client ID: ").strip()
        if len(value) == 32 and all(c in "0123456789abcdefABCDEF" for c in value):
            return value
        print(
            "  That doesn't look like a Client ID "
            "(expect 32 hex characters from the app Settings page). Try again."
        )


def prompt_client_secret() -> str:
    """Prompt for the Client Secret without echoing it. Never printed."""
    value = getpass.getpass("  Spotify Client Secret (hidden): ").strip()
    if not value:
        print("  Secret cannot be empty. Try again.")
        return prompt_client_secret()
    return value


def validate_spotify_credentials(
    client_id: str, client_secret: str
) -> tuple[bool, str]:
    """Smoke-test ID+secret via a client_credentials token request.

    Returns (ok, message). The message never contains the secret.
    """
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    request = urllib.request.Request(
        SPOTIFY_TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401):
            return False, (
                "Spotify rejected the credentials (invalid client). "
                "Check the Client ID/Secret in the dashboard and try again."
            )
        return False, f"Spotify returned HTTP {exc.code}; try again later."
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return False, f"Could not reach Spotify ({exc}); check your network."
    except (ValueError, json.JSONDecodeError):
        return False, "Spotify returned an unreadable response; try again later."
    if isinstance(payload, dict) and payload.get("access_token"):
        return True, "credentials accepted by Spotify"
    return False, "Spotify response missing access_token; try again later."


def generate_jwt_secret() -> str:
    """Generate a random local JWT secret (64 hex chars)."""
    return secrets.token_hex(32)


def build_dev_vars_content(
    client_id: str, client_secret: str, jwt_secret: str
) -> str:
    """Render .dev.vars content. Callers must never print the result."""
    lines = [
        "# Local SpotiBye backend secrets — generated by setup-selfhost.py.",
        "# Never commit this file.",
        f'SPOTIFY_CLIENT_ID="{client_id}"',
        f'SPOTIFY_CLIENT_SECRET="{client_secret}"',
        f'JWT_SECRET="{jwt_secret}"',
        "",
    ]
    return "\n".join(lines)


def write_dev_vars(
    path: Path,
    client_id: str,
    client_secret: str,
    jwt_secret: str,
    force: bool = False,
    dry_run: bool = False,
) -> bool:
    """Write .dev.vars unless it exists (without --force). Never prints values."""
    if dry_run:
        print(f"  [dry-run] would write {path} (values redacted)")
        return True
    if path.exists() and not force:
        print(
            f"  {path} already exists. Re-run with --force to overwrite, "
            "or edit it by hand."
        )
        return False
    path.write_text(
        build_dev_vars_content(client_id, client_secret, jwt_secret),
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print(f"  Wrote {path} (mode 0600)")
    return True


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
    print("\nStep 2: Spotify credentials")
    try:
        client_id = prompt_client_id()
        client_secret = prompt_client_secret()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return 1
    ok, message = validate_spotify_credentials(client_id, client_secret)
    print(f"  [{'ok' if ok else 'FAIL'}] Spotify credentials: {message}")
    if not ok:
        return 1
    jwt_secret = generate_jwt_secret()
    print("  [ok] generated local JWT secret")
    dev_vars = repo_root() / "src" / "backend" / ".dev.vars"
    if not write_dev_vars(
        dev_vars, client_id, client_secret, jwt_secret,
        force=config.force, dry_run=config.dry_run,
    ):
        return 1
    print("\nYou're ready: cd src/backend && npm run dev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

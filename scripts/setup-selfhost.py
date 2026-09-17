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
import re
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
SELFHOST_CONFIG_NAME = "wrangler.selfhost.toml"

REQUIRED_PYTHON = (3, 10)
REQUIRED_TOOLS = ("node", "npm", "npx")
REQUIRED_NODE_MAJOR = 24


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
    }
    return PrereqResult(
        name=name, ok=False, hint=fixes.get(name, f"Install {name}.")
    )


def check_node_version() -> PrereqResult:
    """Verify node exists and meets the pinned major version."""
    if shutil.which("node") is None:
        return PrereqResult(
            name="node-version",
            ok=False,
            hint="Install Node 24 (see .nvmrc): https://nodejs.org/",
        )
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, no shell
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return PrereqResult(
            name="node-version", ok=False, hint="Could not run node."
        )
    match = re.search(r"v(\d+)", proc.stdout.strip())
    if match is None:
        return PrereqResult(
            name="node-version",
            ok=False,
            hint="Could not parse node version; reinstall Node 24.",
        )
    if int(match.group(1)) >= REQUIRED_NODE_MAJOR:
        return PrereqResult(
            name=f"node {proc.stdout.strip()}", ok=True
        )
    return PrereqResult(
        name="node-version",
        ok=False,
        hint=(
            f"Node {REQUIRED_NODE_MAJOR}+ required "
            f"(found {proc.stdout.strip()}). "
            "Install from https://nodejs.org/ (see .nvmrc)."
        ),
    )


def check_prerequisites() -> list[PrereqResult]:
    """Run all prerequisite checks and return the results."""
    results = [check_python_version()]
    results.extend(check_tool(tool) for tool in REQUIRED_TOOLS)
    results.append(check_node_version())
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
    while True:
        value = getpass.getpass("  Spotify Client Secret (hidden): ").strip()
        if value:
            return value
        print("  Secret cannot be empty. Try again.")


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
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 # nosemgrep - URL is the hardcoded SPOTIFY_TOKEN_URL constant; user input only in header/body
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, (
                "Spotify rejected the credentials (invalid client). "
                "Check the Client ID/Secret in the dashboard and try again."
            )
        if exc.code == 400:
            return False, (
                "Spotify rejected the request (bad request body); try again."
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


def backend_dir() -> Path:
    """Return the backend directory (src/backend under the repo root)."""
    return repo_root() / "src" / "backend"


def run_wrangler(
    args: list[str],
    cwd: Path | None = None,
    secret_input: str | None = None,
) -> tuple[bool, str]:
    """Run a wrangler subcommand via npx. Secret goes via stdin, never argv.

    Returns (ok, output). Output may contain IDs but never the secret:
    callers must not print raw output when secret_input was provided.
    """
    cmd = ["npx", "wrangler", *args]
    try:
        proc = subprocess.run(  # noqa: S603 - argv list, no shell
            cmd,
            input=secret_input,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(cwd) if cwd is not None else None,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (proc.stdout + proc.stderr).strip()
    return proc.returncode == 0, output


def provision_kv_namespace(
    binding: str, preview: bool = False, cwd: Path | None = None
) -> tuple[bool, str]:
    """Create a KV namespace, returning (ok, namespace-id-or-message).

    The ID is extracted from wrangler's output; the message never
    contains secrets (no secret is involved in this call).
    """
    args = ["kv", "namespace", "create", binding]
    if preview:
        args.append("--preview")
    ok, output = run_wrangler(args, cwd=cwd)
    if not ok:
        return False, output
    match = re.search(
        r'(?:id|preview_id)\s*=\s*"([a-fA-F0-9]{32})"',
        output,
        re.IGNORECASE,
    )
    if match is None:
        return False, "could not parse a namespace ID from wrangler output"
    return True, match.group(1)


def create_queue(
    name: str, cwd: Path | None = None
) -> tuple[bool, str]:
    """Create a queue; already-existing counts as success."""
    ok, output = run_wrangler(["queues", "create", name], cwd=cwd)
    if ok:
        return True, f"queue {name} ready"
    if "already exists" in output.lower():
        return True, f"queue {name} already exists"
    return False, output


def upload_secret(
    key: str,
    value: str,
    env: str,
    config: str,
    cwd: Path | None = None,
    dry_run: bool = False,
) -> bool:
    """Pipe a secret into `wrangler secret put`. The value never hits argv.

    Returns True on success. Nothing about the value is printed.
    """
    if dry_run:
        print(f"  [dry-run] would upload secret {key} (--env {env})")
        return True
    ok, output = run_wrangler(
        ["secret", "put", key, "--env", env, "-c", config],
        cwd=cwd,
        secret_input=value,
    )
    if ok:
        print(f"  [ok] uploaded secret {key} (--env {env})")
        return True
    # Never print wrangler output here: on failure it may echo the secret.
    print(f"  [FAIL] uploading {key} (details redacted); try again.")
    return False


def patch_kv_ids(
    toml_text: str, ids: dict[str, tuple[str, str]]
) -> str:
    """Replace id/preview_id in every kv_namespaces block for known bindings.

    `ids` maps binding name -> (id, preview_id). Unknown bindings are
    left untouched. Returns the patched text.
    """
    out: list[str] = []
    current_binding: str | None = None
    in_kv_block = False
    for line in toml_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[[") and "kv_namespaces" in stripped:
            in_kv_block = True
            current_binding = None
            out.append(line)
            continue
        if stripped.startswith("[[") or (
            stripped.startswith("[") and not stripped.startswith("[\"")
        ):
            in_kv_block = False
            current_binding = None
            out.append(line)
            continue
        if in_kv_block and stripped.startswith('binding = "'):
            current_binding = stripped.split('"')[1]
            out.append(line)
            continue
        if (
            in_kv_block
            and current_binding in ids
            and re.match(r'^(id|preview_id)\s*=', stripped)
        ):
            key = "id" if stripped.startswith("id") else "preview_id"
            value = ids[current_binding][0 if key == "id" else 1]
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f'{indent}{key} = "{value}"')
            continue
        out.append(line)
    return "\n".join(out) + "\n"


def patch_allowlist(toml_text: str, uris: str) -> str:
    """Replace every ALLOWED_REDIRECT_URIS value with `uris`.

    Comment lines are left untouched; inline occurrences (e.g. inside
    `vars = { ... }`) are replaced.
    """
    out: list[str] = []
    for line in toml_text.splitlines():
        if line.strip().startswith("#"):
            out.append(line)
            continue
        out.append(
            re.sub(
                r'\bALLOWED_REDIRECT_URIS\s*=\s*"[^"]*"',
                lambda _match: f'ALLOWED_REDIRECT_URIS = "{uris}"',
                line,
            )
        )
    return "\n".join(out) + "\n"


def generate_selfhost_config(
    template_path: Path,
    output_path: Path,
    kv_ids: dict[str, tuple[str, str]],
    redirect_uris: str,
    force: bool = False,
    dry_run: bool = False,
) -> bool:
    """Write a per-user wrangler config. Never touches the tracked file."""
    if dry_run:
        print(f"  [dry-run] would write {output_path}")
        return True
    if output_path.exists() and not force:
        print(
            f"  {output_path} already exists. Re-run with --force to "
            "overwrite, or edit it by hand."
        )
        return False
    text = template_path.read_text(encoding="utf-8")
    text = patch_kv_ids(text, kv_ids)
    text = patch_allowlist(text, redirect_uris)
    output_path.write_text(text, encoding="utf-8")
    print(f"  Wrote {output_path}")
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
    print("\nYou're ready: cd src/backend && npm install && npm run dev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

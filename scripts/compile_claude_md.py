#!/usr/bin/env python3
"""
Compile CLAUDE.md from AGENTS.md source.

Generates a Claude-specific entry point by prepending a Claude header block
to the full AGENTS.md body. The generated file is marked as such; hand-edits
will be lost on regeneration.

Usage:
    python scripts/compile_claude_md.py [--check]

Options:
    --check    Exit non-zero with a diff summary if CLAUDE.md is out of sync.
               Used by the pre-commit hook to enforce freshness.
"""

from __future__ import annotations

import argparse
import difflib
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
CLAUDE_PATH = REPO_ROOT / "CLAUDE.md"

logger = logging.getLogger("compile_claude_md")

CLAUDE_SPECIFIC_HEADER = """\
# CLAUDE.md

> Claude Code entry point for SpotiBye. Generated from `AGENTS.md`;
> on any conflict, `AGENTS.md` wins. Do not hand-edit — edit `AGENTS.md`
> and re-run `scripts/compile_claude_md.py`.

## Claude-specific notes

- **Sub-agents:** invoke by name from `.claude/sub-agents/` when the task
  matches an available specialist (architecture, dependency, test coverage,
  security, behavior evaluation).
- **Skills:** progressive-disclosure skill dirs live in `.skills/` (same as
  other agents).

<!-- GENERATED FROM AGENTS.md — DO NOT HAND-EDIT. Edit AGENTS.md and re-run scripts/compile_claude_md.py instead. -->

"""


def read_agents() -> str:
    return AGENTS_PATH.read_text(encoding="utf-8")


def build_claude_md(agents_body: str) -> str:
    return CLAUDE_SPECIFIC_HEADER + agents_body


def write_claude_md(content: str) -> None:
    CLAUDE_PATH.write_text(content, encoding="utf-8")
    logger.info("Wrote %s", CLAUDE_PATH)


def check_claude_md(expected: str) -> int:
    if not CLAUDE_PATH.exists():
        logger.error("CLAUDE.md does not exist; run without --check to generate.")
        return 1

    actual = CLAUDE_PATH.read_text(encoding="utf-8")
    if actual != expected:
        logger.error("CLAUDE.md is out of sync with AGENTS.md.")
        diff = list(
            difflib.unified_diff(
                actual.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile="current CLAUDE.md",
                tofile="expected (from AGENTS.md)",
                n=3,
            )
        )
        sys.stdout.writelines(diff)
        return 1

    logger.info("CLAUDE.md is in sync with AGENTS.md.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile CLAUDE.md from AGENTS.md source"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero with a diff summary if CLAUDE.md is out of sync.",
    )
    args = parser.parse_args()

    if not AGENTS_PATH.exists():
        logger.error("AGENTS.md not found at %s", AGENTS_PATH)
        return 1

    agents_body = read_agents()
    expected = build_claude_md(agents_body)

    if args.check:
        return check_claude_md(expected)

    write_claude_md(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main())

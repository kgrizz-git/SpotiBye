#!/usr/bin/env python3
"""Warn-level docs hygiene checks (TO_DO lifecycle, plan indexes, CHANGELOG shape).

Warn-only: always exits 0 until the release-tag gate recorded in the
docs-harness housekeeping plan flips these to errors. Prints findings as
`WARNING: ...` lines on stderr, mirroring scripts/check-repo-structure.sh.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TODO_PATH = REPO_ROOT / "dev-docs" / "backlog" / "TO_DO.md"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
ACTIVE_DIR = REPO_ROOT / "dev-docs" / "exec-plans" / "active"
ACTIVE_README = ACTIVE_DIR / "README.md"
DEV_DOCS_README = REPO_ROOT / "dev-docs" / "README.md"
INVESTIGATIONS_DIR = REPO_ROOT / "dev-docs" / "investigations"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
CLAUDE_PATH = REPO_ROOT / "CLAUDE.md"

warnings: list[str] = []


def warn(msg: str) -> None:
    warnings.append(msg)


def check_todo_done_items() -> None:
    if not TODO_PATH.exists():
        return
    count = sum(
        1 for line in TODO_PATH.read_text(encoding="utf-8").splitlines()
        if re.match(r"\s*-\s*\[x\]", line)
    )
    if count:
        warn(
            f"{TODO_PATH.relative_to(REPO_ROOT)} retains {count} checked "
            "'[x]' item(s) — log + delete per AGENTS.md same-PR housekeeping"
        )


def active_plans() -> list[Path]:
    if not ACTIVE_DIR.exists():
        return []
    return sorted(p for p in ACTIVE_DIR.glob("*.md") if p.name != "README.md")


def check_fully_checked_plans() -> None:
    for plan in active_plans():
        text = plan.read_text(encoding="utf-8")
        if "- [ ]" not in text and "- [x]" in text:
            warn(
                f"{plan.relative_to(REPO_ROOT)} is fully checked but still "
                "in active/ — move to completed/ and update the index"
            )


def check_active_readme_sync() -> None:
    if not ACTIVE_README.exists():
        return
    readme = ACTIVE_README.read_text(encoding="utf-8")
    on_disk = {p.name for p in active_plans()}
    linked = set(re.findall(r"\]\(\./([^)]+\.md)\)", readme))
    for name in sorted(on_disk - linked):
        warn(f"active/README.md does not index active plan {name}")
    for name in sorted(linked - on_disk):
        warn(f"active/README.md links {name}, which is not in active/")


def check_changelog_headings() -> None:
    if not CHANGELOG_PATH.exists():
        return
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    unreleased = re.split(r"^## \[(?!\s*Unreleased)", text, maxsplit=1, flags=re.MULTILINE)[0]
    seen: dict[str, int] = {}
    for line in unreleased.splitlines():
        if line.startswith("### "):
            seen[line] = seen.get(line, 0) + 1
    for heading, count in sorted(seen.items()):
        if count > 1:
            warn(
                f"CHANGELOG.md Unreleased repeats '{heading}' "
                f"{count}x — squash to one section"
            )


def check_plan_backlinks() -> None:
    if not TODO_PATH.exists():
        return
    todo = TODO_PATH.read_text(encoding="utf-8")
    for plan in active_plans():
        stem = plan.stem
        if stem not in todo and plan.name not in todo:
            warn(
                f"active plan {plan.name} has no backlink in "
                "dev-docs/backlog/TO_DO.md (asymmetric linkage rule)"
            )


def check_claude_sync() -> None:
    if not (AGENTS_PATH.exists() and CLAUDE_PATH.exists()):
        return
    claude = CLAUDE_PATH.read_text(encoding="utf-8")
    if "DO NOT HAND-EDIT" not in claude:
        warn("CLAUDE.md lacks the generated-file marker — regenerate via scripts/compile_claude_md.py")
        return
    marker_at = claude.find("<!-- GENERATED")
    body = claude[marker_at:].split("\n", 1)[1] if "\n" in claude[marker_at:] else ""
    agents = AGENTS_PATH.read_text(encoding="utf-8")
    if body.lstrip("\n") != agents:
        warn("CLAUDE.md body differs from AGENTS.md — re-run scripts/compile_claude_md.py")


def check_staleness() -> None:
    # NOTE: file mtime drives the >30d/>60d checks, so warnings flap across
    # branch switches and fresh checkouts. Acceptable for warn-only mode;
    # revisit (e.g. git log dates) if these ever become errors.
    now = time.time()
    for plan in active_plans():
        age_days = (now - plan.stat().st_mtime) / 86400
        if age_days > 30:
            warn(f"active plan {plan.name} untouched for {age_days:.0f}d — triage or archive")
    if TODO_PATH.exists():
        for lineno, line in enumerate(TODO_PATH.read_text(encoding="utf-8").splitlines(), 1):
            match = re.search(r"in progress (\d{4}-\d{2}-\d{2})", line)
            if match:
                try:
                    year, month, day = (int(part) for part in match.group(1).split("-"))
                    age_days = (now - time.mktime((year, month, day, 0, 0, 0, 0, 0, -1))) / 86400
                except (ValueError, OverflowError):
                    continue
                if age_days > 14:
                    warn(f"TO_DO.md:{lineno} 'in progress' is {age_days:.0f}d old — confirm or re-date")
    if INVESTIGATIONS_DIR.exists():
        for note in INVESTIGATIONS_DIR.glob("*.md"):
            age_days = (now - note.stat().st_mtime) / 86400
            if age_days > 60:
                warn(f"{note.relative_to(REPO_ROOT)} older than 60d — promote, archive, or delete")
    if DEV_DOCS_README.exists():
        index = DEV_DOCS_README.read_text(encoding="utf-8")
        for doc in (REPO_ROOT / "dev-docs").glob("*.md"):
            if doc.name == "README.md":
                continue
            if doc.name not in index:
                warn(f"{doc.relative_to(REPO_ROOT)} is not linked from dev-docs/README.md")


def main() -> int:
    check_todo_done_items()
    check_fully_checked_plans()
    check_active_readme_sync()
    check_changelog_headings()
    check_plan_backlinks()
    check_claude_sync()
    check_staleness()
    for message in warnings:
        print(f"WARNING: {message}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

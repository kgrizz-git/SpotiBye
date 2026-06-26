# Docs Taxonomy Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate user-facing documentation from developer and agent-facing documentation.

**Architecture:** `docs/` becomes the end-user documentation tree. `dev-docs/` owns contributor guides, architecture decisions, references, execution plans, investigations, assessments, archives, and backlog material.

**Tech Stack:** Markdown documentation, shell structure checks, pre-commit local hook.

---

### Task 1: Move Documentation Into Canonical Trees

**Files:**
- Move user-facing files under `docs/`
- Move developer-facing files under `dev-docs/`

- [x] Move durable design decisions to `dev-docs/architecture/design-decisions/`.
- [x] Move third-party references to `dev-docs/references/`.
- [x] Move implementation plans to `dev-docs/exec-plans/`.
- [x] Move developer guides to `dev-docs/guides/`.
- [x] Move investigations and assessments to `dev-docs/investigations/` or `dev-docs/assessments/`.
- [x] Move backlog files to `dev-docs/backlog/`.
- [x] Leave only user-facing docs in `docs/`.

### Task 2: Update Navigation and Agent Guidance

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `docs/index.md`
- Modify: `dev-docs/README.md`
- Modify: `.github/pull_request_template.md`

- [x] Update agent guidance to define `docs/` as user-facing and `dev-docs/` as developer-facing.
- [x] Update the user docs index.
- [x] Update the developer docs index.
- [x] Update PR checklist links.

### Task 3: Enforce the New Structure

**Files:**
- Modify: `scripts/check-repo-structure.sh`

- [x] Fail when developer-only directories reappear under `docs/`.
- [x] Fail when likely developer-only Markdown files are added directly under `docs/`.
- [x] Check active plans under `dev-docs/exec-plans/active/`.
- [x] Warn about unindexed Markdown files.

### Task 4: Verify and Complete

**Files:**
- Move: `dev-docs/exec-plans/active/2026-06-26-docs-taxonomy-migration.md`
- Modify: `dev-docs/exec-plans/completed/README.md`

- [x] Run the repo structure check.
- [x] Run a link/path search for old canonical locations.
- [x] Move this plan to completed.
- [x] Add this plan to the completed-plan index.

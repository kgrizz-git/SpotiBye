# Repo Organization & Agent Infrastructure Improvements

> **For agentic workers:** Implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Mark each step complete as you finish it.

**Goal:** Consolidate scattered docs/plans, remove duplicated agent config, create a `CLAUDE.md`, and add a pre-commit hook to prevent structural drift.

**Why:** The repo accumulated structural debt from multiple AI tools (Cursor, Windsurf, Qwen, Claude Code). Plans live in 3+ places, agent config is in 6 directories, there's no `CLAUDE.md`, and `dev-docs/` has no lifecycle enforcement.

---

## Phase 1: Create CLAUDE.md

- [x] Create `/CLAUDE.md` as the Claude Code entry point. It should be a focused subset of `AGENTS.md`:
  - Test commands (copy from AGENTS.md "Running Tests & Verification")
  - Key principles (the 6 rules from AGENTS.md "Key Principles")
  - Navigation pointers: `ARCHITECTURE.md`, `docs/index.md`, `dev-docs/code-map.md`
  - Plans/docs placement conventions (from AGENTS.md lines 31–39)
  - Sub-agent reference: point to `.claude/sub-agents/`
  - Changelog rule
- [x] Keep `AGENTS.md` intact — it serves Copilot/Codex/other tools. Add one line to AGENTS.md: "Claude Code users: see `CLAUDE.md` for a focused entry point."

---

## Phase 2: Consolidate Plans

- [x] Move `dev-docs/plans/reccobeats-wiring.md` → `dev-docs/exec-plans/active/2026-06-21-reccobeats-wiring.md`
- [x] Delete `dev-docs/plans/` directory entirely
- [x] Update all references in `dev-docs/backlog/TO_DO.md` that point to `plans/reccobeats-wiring.md` → new path `../dev-docs/exec-plans/active/2026-06-21-reccobeats-wiring.md`
- [x] Update `dev-docs/exec-plans/active/README.md` to list the moved plan

---

## Phase 3: Remove Duplicated/Stale Agent Config

- [x] Delete `.windsurf/rules/` (22 duplicate CodeGuard files — identical to `.cursor/rules/` but with `.md` extension). Already gitignored.
- [x] Delete `.windsurf/` directory entirely if empty after
- [x] Delete `.qwen/` directory (contains only a trivial `settings.json`)
- [x] Add to `.gitignore`:
  ```
  memory/
  .qwen/
  ```
- [x] Untrack the `memory/` directory: `git rm --cached -r memory/`
- [x] Untrack all `.DS_Store` files: `git rm --cached '**/.DS_Store'` (several are tracked in `dev-docs/`, `docs/`, `.skills/`)

---

## Phase 4: Add Lifecycle Guidance to dev-docs/

- [x] Update `dev-docs/README.md` to add these rules after the existing content:

  **Lifecycle rules:**
  - Investigation notes older than 60 days without updates should be reviewed for archival or deletion
  - Date-prefix tactical notes: `YYYY-MM-DD-topic.md` (e.g., `2026-06-15-bug-review.md`)
  - If a note becomes durable guidance, move it to `docs/` and update `docs/index.md`
  - Plans never go here — use `dev-docs/exec-plans/active/`

---

## Phase 5: Pre-commit Hook (Structural Guardrails)

- [x] Create `scripts/check-repo-structure.sh` (make executable) with these checks:
  1. **No plans in wrong locations**: Fail if any `.md` file exists in `dev-docs/plans/`
  2. **No completed plans left in active/**: Warn (don't fail) if any file in `dev-docs/exec-plans/active/` has >3 checkboxes and 0 unchecked (all `- [x]`, no `- [x]`)
  3. **No .DS_Store staged**: Fail if any `.DS_Store` is in the staged files
  4. **No .windsurf/rules/ resurrection**: Fail if `.windsurf/rules/` directory exists with content

- [x] Add to `.pre-commit-config.yaml` as a local hook:
  ```yaml
  - repo: local
    hooks:
      - id: check-repo-structure
        name: Check repo structure conventions
        entry: scripts/check-repo-structure.sh
        language: script
        pass_filenames: false
  ```

---

## Phase 6: Update AGENTS.md

- [x] Add line near top: "Claude Code users: see `CLAUDE.md` for a focused entry point."
- [x] Add note in "Plans and Documentation Conventions" section that `.windsurf/rules/` and `.qwen/` are removed; `.cursor/rules/` is the canonical location for IDE security rules
- [x] Keep the existing plan placement guidance (it's now enforced by the hook too)

---

## Verification

- [x] `git status` shows expected changes (deletions, new files, untracked removals)
- [x] `./scripts/check-repo-structure.sh` exits 0
- [x] Create a test file at `dev-docs/plans/test.md`, run hook → it rejects. Remove test file.
- [x] `pre-commit run --all-files` still passes (all existing hooks + new one)
- [x] Confirm `CLAUDE.md` exists and contains test commands, principles, navigation

---

## Files Summary

| File | Action |
|------|--------|
| `CLAUDE.md` | Create |
| `scripts/check-repo-structure.sh` | Create |
| `.pre-commit-config.yaml` | Edit — add local hook |
| `.gitignore` | Edit — add `memory/`, `.qwen/` |
| `dev-docs/README.md` | Edit — add lifecycle rules |
| `dev-docs/backlog/TO_DO.md` | Edit — fix plan path references |
| `dev-docs/exec-plans/active/README.md` | Edit — add reccobeats plan entry |
| `AGENTS.md` | Edit — small additions |
| `.windsurf/` | Delete |
| `.qwen/` | Delete |
| `dev-docs/plans/` | Delete (after moving content) |
| `memory/` | Untrack via git rm --cached |
| `**/.DS_Store` | Untrack via git rm --cached |

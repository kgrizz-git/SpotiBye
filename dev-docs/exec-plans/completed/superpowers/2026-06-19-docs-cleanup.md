# Documentation Cleanup and Agent Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate stale repository plans, clarify where documentation belongs, and give future coding agents precise rules for creating, updating, and archiving docs.

**Architecture:** Treat `docs/` as the durable documentation tree and `dev-docs/` as working notes, audits, and temporary analysis. Consolidate executable plans under `dev-docs/exec-plans/active/` and `dev-docs/exec-plans/completed/`, keep historical snapshots in `docs/old-docs-backup/`, and update every moved-file reference in the same change.

**Tech Stack:** Markdown docs, repository-local `rg`/`git mv` workflows, existing verification scripts, AGENTS.md, GitHub Copilot instructions.

---

## Related TODO

Source item: [dev-docs/backlog/TO_DO.md](../dev-docs/backlog/TO_DO.md)

> Clean up repo docs and plans, improve agent guidance for organization.

This plan expands that TODO into executable documentation maintenance tasks.

## Execution Status Rules

Agents executing this or any future implementation plan must keep tracking files current as part of the work, not as an afterthought:

- Mark each completed plan step by changing `- [ ]` to `- [x]` in the plan file before moving to the next task or checkpoint commit.
- Include plan checkbox updates in the same commit as the work they describe whenever practical.
- Keep the originating `dev-docs/backlog/TO_DO.md` item linked to the active plan while work is in progress.
- When all acceptance criteria are satisfied, mark the originating `dev-docs/backlog/TO_DO.md` item complete, move the plan from `dev-docs/exec-plans/active/` to `dev-docs/exec-plans/completed/`, and update both active/completed README indexes.
- Do not report a plan as complete while its plan checklist, TODO item, or exec-plan indexes still say it is active.

## Current Audit Snapshot

Run this before implementation to confirm the inventory has not drifted:

```bash
find docs/plans -maxdepth 1 -type f -print | sort
find docs/superpowers/plans -maxdepth 2 -type f -print | sort
find dev-docs/plans -maxdepth 2 -type f -print | sort
rg -n "docs/plans|dev-docs/plans/done|docs/superpowers/plans/superseded|old-docs-backup|agent-first-retrofit|exec-plans" AGENTS.md ARCHITECTURE.md docs dev-docs .github
```

Known current findings:

| Path | Current Status | Planned Outcome |
|---|---|---|
| `docs/plans/` | Legacy phase/spec plans; no index; item #10 in `dev-docs/backlog/tech-debt-tracker.md` tracks this as debt | Move files to `dev-docs/exec-plans/completed/legacy/` and update references |
| `dev-docs/plans/done/` | Completed implementation plans | Move files to `dev-docs/exec-plans/completed/dev-docs/` and update references |
| `docs/superpowers/plans/superseded/` | Superseded main-screen refactor plans | Move files to `dev-docs/exec-plans/completed/superseded/` and update references |
| `docs/superpowers/plans/2026-06-16-main-screen-refactor-V3.md` | Superseded by `2026-06-19-main-screen-refactor-completion-plan.md` | Move to `dev-docs/exec-plans/completed/superseded/` |
| `docs/superpowers/plans/2026-06-16-main-screen-refactor-review.md` | Review artifact, no longer active execution plan | Move to `dev-docs/exec-plans/completed/superseded/` |
| `docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md` | Completed and referenced from TO_DO | Move to `dev-docs/exec-plans/completed/superpowers/` and update TO_DO |
| `dev-docs/exec-plans/active/README.md` | Lists `agent-first-retrofit.md`, but that plan is already completed elsewhere | Replace with an accurate active-plan index |
| `dev-docs/exec-plans/completed/README.md` | Empty placeholder table | Populate with categorized completed-plan index |
| `dev-docs/plans/reccobeats-wiring.md` | Mixed state: Track D complete, UI verification items still open | Keep active unless follow-up inspection shows no remaining actionable items |
| `docs/old-docs-backup/` | Historical archive | Keep in place; do not move out of the tracked tree in this cleanup |
| `dev-docs/code-map.md` | Current but still notes stale v2 Mermaid subgraph | Update or add a follow-up item if not fixed in this cleanup |
| `docs/index.md` | Still lists `docs/plans/` as legacy | Replace with the consolidated exec-plan structure |
| `AGENTS.md` / `.github/copilot-instructions.md` | No explicit plan/doc placement conventions | Add concise documentation conventions |
| `dev-docs/README.md` | Missing | Create it |
| top-level `plans/` | Removed after this plan was relocated | Keep removed; do not create new root-level plan files |

## File Structure

Files/directories to create:

- `dev-docs/exec-plans/completed/legacy/` — legacy phase plans moved from `docs/plans/`.
- `dev-docs/exec-plans/completed/dev-docs/` — completed implementation plans moved from `dev-docs/plans/done/`.
- `dev-docs/exec-plans/completed/superseded/` — superseded Superpowers plans and review artifacts.
- `dev-docs/exec-plans/completed/superpowers/` — completed Superpowers execution plans that are not merely superseded drafts.
- `dev-docs/README.md` — guidance for working-note docs.

Files to modify:

- `dev-docs/backlog/TO_DO.md` — update this item to point to the relocated active plan; later mark complete.
- `dev-docs/exec-plans/active/README.md` — accurate active-plan index.
- `dev-docs/exec-plans/completed/README.md` — completed-plan index.
- `docs/index.md` — remove `docs/plans/` legacy entry and add consolidated plan/archive sections.
- `dev-docs/backlog/tech-debt-tracker.md` — resolve item #10 after migration.
- `AGENTS.md` — add repository doc-placement conventions.
- `.github/copilot-instructions.md` — mirror doc-placement conventions for Copilot.
- `dev-docs/architecture/design-decisions/resumable-export-cursors.md` — update link to moved resumable export plan.
- `dev-docs/agent-first-retrofit-guide.md` — either update stale path references or mark as historical.
- Any additional files found by `rg` that reference moved paths.

Files/directories to remove only after links are rewritten:

- `docs/plans/` — remove after all files are moved.
- `docs/superpowers/plans/superseded/` — remove after files are moved.
- `dev-docs/plans/done/` — remove after files are moved.

---

## Task 1: Confirm Active Plan Placement and Fix Indexes

**Files:**
- Modify: `dev-docs/backlog/TO_DO.md`
- Modify: `dev-docs/exec-plans/active/README.md`

- [x] **Step 1: Move the plan into the active exec-plan directory**

Completed:

```bash
mkdir -p dev-docs/exec-plans/active
mv plans/docs-cleanup-2026-06-19.md dev-docs/exec-plans/active/2026-06-19-docs-cleanup.md
rmdir plans
```

Result: `plans/` no longer exists, and this plan lives under `dev-docs/exec-plans/active/`.

- [x] **Step 2: Update the TO_DO link**

In `dev-docs/backlog/TO_DO.md`, replace:

```md
- Clean up repo docs and plans, improve agent guidance for organization — [completion plan](../plans/docs-cleanup-2026-06-19.md)
```

with:

```md
- Clean up repo docs and plans, improve agent guidance for organization — [active execution plan](../dev-docs/exec-plans/active/2026-06-19-docs-cleanup.md)
```

- [x] **Step 3: Replace the active-plan README table**

Replace `dev-docs/exec-plans/active/README.md` with:

```md
# Active Execution Plans

> Plans currently in progress. Move a plan to `../completed/` when it is fully executed and all references are updated.

| Plan | Description | Started |
|------|-------------|---------|
| [`2026-06-19-docs-cleanup.md`](2026-06-19-docs-cleanup.md) | Consolidate stale plans/docs and add documentation placement guidance | 2026-06-19 |
```

- [x] **Step 4: Verify relocation**

Run:

```bash
test -f dev-docs/exec-plans/active/2026-06-19-docs-cleanup.md
test ! -e plans
! rg -n "\.\./plans/docs-cleanup|plans/docs-cleanup-2026-06-19" dev-docs/backlog/TO_DO.md dev-docs/exec-plans/active/README.md
rg -n "2026-06-19-docs-cleanup" dev-docs/backlog/TO_DO.md dev-docs/exec-plans/active/README.md
```

Expected: no old root `plans/docs-cleanup-2026-06-19` path appears; the active plan path appears in TO_DO and active README.

- [x] **Step 5: Commit**

```bash
git add -A dev-docs/exec-plans/active dev-docs/backlog/TO_DO.md
git commit -m "docs: relocate docs cleanup plan"
```

---

## Task 2: Move Completed and Legacy Plans Into `dev-docs/exec-plans/completed/`

**Files:**
- Move: `docs/plans/*`
- Move: `dev-docs/plans/done/*`
- Move: `docs/superpowers/plans/superseded/*`
- Move: selected completed files from `docs/superpowers/plans/`
- Modify: `dev-docs/exec-plans/completed/README.md`

- [x] **Step 1: Create completed-plan archive directories**

Run:

```bash
mkdir -p dev-docs/exec-plans/completed/legacy
mkdir -p dev-docs/exec-plans/completed/dev-docs
mkdir -p dev-docs/exec-plans/completed/superseded
mkdir -p dev-docs/exec-plans/completed/superpowers
```

- [x] **Step 2: Move legacy `docs/plans/` files**

Run:

```bash
git mv docs/plans/*.md dev-docs/exec-plans/completed/legacy/
rmdir docs/plans
```

- [x] **Step 3: Move completed `dev-docs/plans/done/` files**

Run:

```bash
git mv dev-docs/plans/done/*.md dev-docs/exec-plans/completed/dev-docs/
rmdir dev-docs/plans/done
```

- [x] **Step 4: Move superseded Superpowers plans**

Run:

```bash
git mv docs/superpowers/plans/superseded/*.md dev-docs/exec-plans/completed/superseded/
rmdir docs/superpowers/plans/superseded
git mv docs/superpowers/plans/2026-06-16-main-screen-refactor-V3.md dev-docs/exec-plans/completed/superseded/
git mv docs/superpowers/plans/2026-06-16-main-screen-refactor-review.md dev-docs/exec-plans/completed/superseded/
```

- [x] **Step 5: Move completed Superpowers execution plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md dev-docs/exec-plans/completed/superpowers/
rmdir docs/superpowers/plans
rmdir docs/superpowers
```

If `rmdir docs/superpowers` fails because new files exist there, leave it in place and update its README/index instead.

- [x] **Step 6: Populate completed-plan README**

Replace `dev-docs/exec-plans/completed/README.md` with:

```md
# Completed Execution Plans

> Plans that have been fully executed or superseded. Kept for historical reference; do not add new active work here.

## Superpowers Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`superpowers/2026-06-19-main-screen-refactor-completion-plan.md`](superpowers/2026-06-19-main-screen-refactor-completion-plan.md) | Main screen refactor completion and verification | 2026-06-19 |

## Superseded Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`superseded/2026-06-16-main-screen-refactor.md`](superseded/2026-06-16-main-screen-refactor.md) | Superseded main screen refactor plan | Superseded |
| [`superseded/2026-06-16-main-screen-refactor-V2.md`](superseded/2026-06-16-main-screen-refactor-V2.md) | Superseded main screen refactor V2 plan | Superseded |
| [`superseded/2026-06-16-main-screen-refactor-V3.md`](superseded/2026-06-16-main-screen-refactor-V3.md) | Superseded by 2026-06-19 completion plan | Superseded |
| [`superseded/2026-06-16-main-screen-refactor-review.md`](superseded/2026-06-16-main-screen-refactor-review.md) | Main screen refactor review artifact | Superseded |

## Dev Docs Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`dev-docs/agent-first-retrofit.md`](dev-docs/agent-first-retrofit.md) | Agent-first repository retrofit | 2026-06 |
| [`dev-docs/analysis-queue-hardening.md`](dev-docs/analysis-queue-hardening.md) | Queue-backed playlist analysis hardening | 2026-06-19 |
| [`dev-docs/ci-fix-plan.md`](dev-docs/ci-fix-plan.md) | CI workflow fixes | 2026-06 |
| [`dev-docs/dead-code-cleanup.md`](dev-docs/dead-code-cleanup.md) | Dead code cleanup | 2026-06 |
| [`dev-docs/fix-analysis-403-spotify-api-migration.md`](dev-docs/fix-analysis-403-spotify-api-migration.md) | Spotify artist endpoint migration fix | 2026-06 |
| [`dev-docs/v2-extraction.md`](dev-docs/v2-extraction.md) | v2 extraction plan | 2026-06 |

## Legacy Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`legacy/backend-selector-gui-patch-plan.md`](legacy/backend-selector-gui-patch-plan.md) | Backend selector GUI patch | Historical |
| [`legacy/phase-1-cloudflare-backend.md`](legacy/phase-1-cloudflare-backend.md) | Cloudflare backend phase plan | Historical |
| [`legacy/phase-1-files.md`](legacy/phase-1-files.md) | Phase 1 file list | Historical |
| [`legacy/phase-2-files.md`](legacy/phase-2-files.md) | Phase 2 file list | Historical |
| [`legacy/phase-2-frontend-cloudflare-integration.md`](legacy/phase-2-frontend-cloudflare-integration.md) | Frontend/Cloudflare integration phase plan | Historical |
| [`legacy/phase-2-real-integration-testing.md`](legacy/phase-2-real-integration-testing.md) | Real integration testing phase plan | Historical |
| [`legacy/phase-3-frontend-executable-build-spec-update.md`](legacy/phase-3-frontend-executable-build-spec-update.md) | Frontend executable build spec update | Historical |
| [`legacy/phase-3-production-deployment.md`](legacy/phase-3-production-deployment.md) | Production deployment phase plan | Historical |
| [`legacy/phase-4-testing-verification.md`](legacy/phase-4-testing-verification.md) | Testing verification phase plan | Historical |
| [`legacy/resumable-export-cursor-persistence-plan.md`](legacy/resumable-export-cursor-persistence-plan.md) | Resumable export cursor persistence | Historical |
| [`legacy/search_filter_plan.md`](legacy/search_filter_plan.md) | Search/filter plan | Historical |
```

- [x] **Step 7: Verify moves**

Run:

```bash
test ! -e docs/plans
test ! -e dev-docs/plans/done
test ! -e docs/superpowers/plans/superseded
find dev-docs/exec-plans/completed -maxdepth 2 -type f -name "*.md" | sort
```

Expected: moved files are present under `dev-docs/exec-plans/completed/`; old plan directories are gone.

- [x] **Step 8: Commit**

```bash
git add -A docs dev-docs
git commit -m "docs: consolidate completed execution plans"
```

---

## Task 3: Rewrite References to Moved Plans

**Files:**
- Modify: `dev-docs/backlog/TO_DO.md`
- Modify: `dev-docs/architecture/design-decisions/resumable-export-cursors.md`
- Modify: `dev-docs/plans/reccobeats-wiring.md`
- Modify: `dev-docs/agent-first-retrofit-guide.md`
- Modify: `docs/index.md`
- Modify: any additional files found by `rg`

- [x] **Step 1: Find stale references**

Run:

```bash
rg -n "docs/plans|dev-docs/plans/done|docs/superpowers/plans|plans/done|../plans/" AGENTS.md ARCHITECTURE.md docs dev-docs .github
```

Expected: shows references that need path rewrites or historical context labels.

- [x] **Step 2: Apply these known path replacements**

Use exact replacements:

| Old | New |
|---|---|
| `../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md` | `../dev-docs/exec-plans/completed/superpowers/2026-06-19-main-screen-refactor-completion-plan.md` |
| `docs/plans/resumable-export-cursor-persistence-plan.md` | `dev-docs/exec-plans/completed/legacy/resumable-export-cursor-persistence-plan.md` |
| `../plans/resumable-export-cursor-persistence-plan.md` | `../exec-plans/completed/legacy/resumable-export-cursor-persistence-plan.md` |
| `plans/done/analysis-queue-hardening.md` | `../dev-docs/exec-plans/completed/dev-docs/analysis-queue-hardening.md` when referenced from `dev-docs/backlog/TO_DO.md` |
| `dev-docs/plans/done/analysis-queue-hardening.md` | `dev-docs/exec-plans/completed/dev-docs/analysis-queue-hardening.md` |
| `dev-docs/plans/done/fix-analysis-403-spotify-api-migration.md` | `dev-docs/exec-plans/completed/dev-docs/fix-analysis-403-spotify-api-migration.md` |
| `docs/plans/` | `dev-docs/exec-plans/completed/legacy/` for historical plan references |
| `docs/superpowers/plans/2026-06-16-main-screen-refactor-V3.md` | `dev-docs/exec-plans/completed/superseded/2026-06-16-main-screen-refactor-V3.md` |

Do not rewrite references that intentionally describe old paths as historical audit findings inside completed plans unless the sentence would confuse future agents.

- [x] **Step 3: Update `docs/index.md` plan section**

Replace the `Plans & Execution` table with:

```md
## Plans & Execution

| Path | Content |
|------|---------|
| [`exec-plans/active/`](exec-plans/active/) | Currently active execution plans |
| [`exec-plans/completed/`](exec-plans/completed/) | Completed and superseded execution plans |
| [`old-docs-backup/`](old-docs-backup/) | Historical phase docs kept for reference only |
```

- [x] **Step 4: Re-scan stale references**

Run:

```bash
rg -n "docs/plans|dev-docs/plans/done|docs/superpowers/plans|plans/done|../plans/" AGENTS.md ARCHITECTURE.md docs dev-docs .github
```

Expected: no stale active references. Remaining hits are acceptable only when they appear inside historical completed plans and clearly describe past state.

- [x] **Step 5: Commit**

```bash
git add AGENTS.md ARCHITECTURE.md docs dev-docs .github
git commit -m "docs: update references after plan consolidation"
```

---

## Task 4: Add Documentation Conventions to Agent Guidance

**Files:**
- Modify: `AGENTS.md`
- Modify: `.github/copilot-instructions.md`
- Create: `dev-docs/README.md`

- [x] **Step 1: Add AGENTS.md section**

Add this section after `Navigation` in `AGENTS.md`:

```md
## Plans and Documentation Conventions

- New implementation plans go in `dev-docs/exec-plans/active/YYYY-MM-DD-topic.md`.
- Plans must use checkbox steps (`- [ ]`) and executors must mark steps complete (`- [x]`) as work is completed.
- If a plan comes from `dev-docs/backlog/TO_DO.md`, keep that TODO linked while active and mark it complete when the plan is finished.
- Completed or superseded plans move to `dev-docs/exec-plans/completed/` and must be indexed in `dev-docs/exec-plans/completed/README.md`.
- Design decisions that should remain durable go in `dev-docs/architecture/design-decisions/`.
- Third-party API/platform reference notes go in `dev-docs/references/`.
- Short-lived investigations, audits, and working notes go in `dev-docs/`.
- Before creating a new doc, check `docs/index.md`, `dev-docs/README.md`, and `rg` for an existing page to update.
- Do not leave completed plans in `active/`, and do not create new root-level `plans/` files.
```

- [x] **Step 2: Add Copilot instructions section**

Add this section before `PR Conventions` in `.github/copilot-instructions.md`:

```md
## Documentation Conventions

- Use `dev-docs/exec-plans/active/YYYY-MM-DD-topic.md` for new executable plans.
- Executable plans must use checkbox steps (`- [ ]`), and completed steps must be checked off in the plan as implementation proceeds.
- If a plan is tied to `dev-docs/backlog/TO_DO.md`, keep the TODO linked while active and mark it complete when the plan moves to completed.
- Move finished plans to `dev-docs/exec-plans/completed/` and update that directory's README index.
- Use `dev-docs/architecture/design-decisions/` for durable architecture/design decisions and `dev-docs/references/` for third-party API notes.
- Use `dev-docs/` for temporary audits, analysis notes, and implementation context that may later be consolidated.
- Read `docs/index.md` and `dev-docs/README.md` before adding new docs so existing pages are updated instead of duplicated.
- Do not create new root-level `plans/` files.
```

- [x] **Step 3: Create `dev-docs/README.md`**

Create `dev-docs/README.md`:

```md
# Developer Notes

`dev-docs/` holds working notes for maintainers and coding agents. These files can be more tactical than the durable docs in `docs/`.

Use this directory for:

- audits and codebase maps
- temporary implementation context
- investigation notes
- active backend/frontend analysis notes that are not yet stable design docs

Do not use this directory for:

- executable implementation plans; use `dev-docs/exec-plans/active/`
- completed plans; use `dev-docs/exec-plans/completed/`
- durable architecture decisions; use `dev-docs/architecture/design-decisions/`
- third-party API references; use `dev-docs/references/`

Before adding a new file here, run:

```bash
rg -n "<topic keyword>" dev-docs docs
```

Update an existing note when it already covers the same topic. If a note becomes durable guidance, move or summarize it under `docs/` and update `docs/index.md`.
```

- [x] **Step 4: Verify guidance references**

Run:

```bash
rg -n "Plans and Documentation Conventions|Documentation Conventions|Do not create new root-level `plans/` files|dev-docs/exec-plans/active|dev-docs/README" AGENTS.md .github/copilot-instructions.md dev-docs/README.md
```

Expected: new guidance appears in all three files.

- [x] **Step 5: Commit**

```bash
git add AGENTS.md .github/copilot-instructions.md dev-docs/README.md
git commit -m "docs: add documentation placement guidance"
```

---

## Task 5: Resolve Documentation Debt Tracker and TODO

**Files:**
- Modify: `dev-docs/backlog/tech-debt-tracker.md`
- Modify: `dev-docs/backlog/TO_DO.md`
- Modify: `dev-docs/exec-plans/active/README.md`
- Modify: `dev-docs/exec-plans/completed/README.md`

- [x] **Step 1: Update tech debt item #10**

In `dev-docs/backlog/tech-debt-tracker.md`, move this row from the active/open section:

```md
| 10 | `docs/plans/` | Legacy plan files not migrated to `dev-docs/exec-plans/` structure; no index | Low | 2026-05 | Open |
```

to the done/resolved section with:

```md
| 10 | `docs/plans/` migrated | Legacy plan files consolidated under `dev-docs/exec-plans/completed/legacy/`; active/completed indexes updated | Low | 2026-06-19 | Done |
```

If the file uses a different done-section heading, preserve its existing structure and add the row there.

- [x] **Step 2: Mark the TODO item complete**

In `dev-docs/backlog/TO_DO.md`, change:

```md
- Clean up repo docs and plans, improve agent guidance for organization — [active execution plan](../dev-docs/exec-plans/active/2026-06-19-docs-cleanup.md)
```

to:

```md
- [x] Clean up repo docs and plans, improve agent guidance for organization — completed by [execution plan](../dev-docs/exec-plans/completed/superpowers/2026-06-19-docs-cleanup.md)
```

- [x] **Step 3: Move this plan to completed**

Run:

```bash
git mv dev-docs/exec-plans/active/2026-06-19-docs-cleanup.md dev-docs/exec-plans/completed/superpowers/2026-06-19-docs-cleanup.md
```

- [x] **Step 4: Update active/completed indexes**

Replace `dev-docs/exec-plans/active/README.md` with:

```md
# Active Execution Plans

> Plans currently in progress. Move a plan to `../completed/` when it is fully executed and all references are updated.

| Plan | Description | Started |
|------|-------------|---------|
| — | — | — |
```

Add this row under the `Superpowers Plans` table in `dev-docs/exec-plans/completed/README.md`:

```md
| [`superpowers/2026-06-19-docs-cleanup.md`](superpowers/2026-06-19-docs-cleanup.md) | Documentation cleanup and agent guidance | 2026-06-19 |
```

- [x] **Step 5: Verify final indexes**

Run:

```bash
rg -n "2026-06-19-docs-cleanup|docs/plans|dev-docs/plans/done|docs/superpowers/plans" docs/exec-plans docs/index.md dev-docs/backlog/tech-debt-tracker.md dev-docs/backlog/TO_DO.md
```

Expected:

- docs cleanup plan appears only in completed index and TO_DO completion link.
- `docs/plans`, `dev-docs/plans/done`, and `docs/superpowers/plans` do not appear as active paths.

- [x] **Step 6: Commit**

```bash
git add -A docs dev-docs
git commit -m "docs: resolve docs cleanup tracking"
```

---

## Task 6: Final Verification

**Files:**
- Verify: documentation tree and repository status

- [x] **Step 1: Check for stale directories**

Run:

```bash
test ! -e plans
test ! -e docs/plans
test ! -e dev-docs/plans/done
test ! -e docs/superpowers/plans/superseded
```

Expected: all commands exit 0.

- [x] **Step 2: Check for stale active references**

Run:

```bash
rg -n "docs/plans|dev-docs/plans/done|docs/superpowers/plans|plans/done|../plans/" AGENTS.md ARCHITECTURE.md docs dev-docs .github
```

Expected: no active references. Historical references inside completed plans are acceptable only if they clearly describe past state.

- [x] **Step 3: Check doc placement guidance**

Run:

```bash
rg -n "dev-docs/exec-plans/active|dev-docs/exec-plans/completed|dev-docs/README|root-level `plans/`" AGENTS.md .github/copilot-instructions.md docs/index.md dev-docs/README.md
```

Expected: placement guidance is discoverable from agent entry points.

- [x] **Step 4: Run repository verification**

Run:

```bash
./scripts/verify-all.sh
```

Expected: `All verifications passed.`

If sandbox blocks local frontend networking, rerun the same command with the normal project-approved escalation path and record that in the final summary.

- [x] **Step 5: Inspect final status**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected: branch has only intentional commits from this plan and no untracked root-level `plans/` directory.

---

## Acceptance Criteria

- [x] No root-level `plans/` directory remains.
- [x] No active docs reference `docs/plans/`, `dev-docs/plans/done/`, or `docs/superpowers/plans/superseded/`.
- [x] `dev-docs/exec-plans/active/README.md` accurately lists active plans.
- [x] `dev-docs/exec-plans/completed/README.md` indexes moved completed/superseded plans.
- [x] `docs/index.md` describes the current plan/documentation structure.
- [x] `AGENTS.md` and `.github/copilot-instructions.md` tell agents where to place plans, design docs, references, and dev notes.
- [x] `dev-docs/README.md` exists and explains what belongs in `dev-docs/`.
- [x] `dev-docs/backlog/tech-debt-tracker.md` item #10 is resolved.
- [x] `dev-docs/backlog/TO_DO.md` marks the docs cleanup item complete after implementation.
- [x] Completed steps in this plan are checked off before final handoff.
- [x] `./scripts/verify-all.sh` passes.

## Explicit Non-Goals

- Do not delete `docs/old-docs-backup/`; keep it as a historical archive.
- Do not rewrite old historical plans for accuracy beyond path/link maintenance.
- Do not refactor application code.
- Do not change product behavior.
- Do not move current reference docs from `dev-docs/references/` or current design docs from `dev-docs/architecture/design-decisions/`.

## Self-Review Notes

- The plan removes the ambiguous decision point about `docs/old-docs-backup/` by keeping it in tree.
- The plan avoids hard deleting old plans; it archives them under `dev-docs/exec-plans/completed/`.
- The plan handles the root-level `plans/` directory by moving this file first.
- The plan includes both agent guidance files requested in the TODO.
- The plan includes final verification for stale paths and full repository verification.

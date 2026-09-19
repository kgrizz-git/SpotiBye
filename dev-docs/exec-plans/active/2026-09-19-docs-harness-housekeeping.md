# Docs Harness Housekeeping — TO_DO lifecycle, maintenance log, same-PR gardening

**Date:** 2026-09-19
**Branch:** `chore/docs-harness-housekeeping`
**Status:** draft v3 — kilo reviewer feedback incorporated; entry-point canonicalization (Phase 6) added
**Backlog link:** `dev-docs/backlog/TO_DO.md` → "Docs harness housekeeping" entry under Repo Cleanup & DevOps (added 2026-09-19; this plan satisfies its own asymmetric plan↔TODO rule)

## Goal

Make `TO_DO.md` active-only, give internal-only work a durable home other than `CHANGELOG.md`, and make housekeeping part of the completing PR — not a follow-up pass.

Two owner constraints (normative for this plan):

1. **Same-PR housekeeping:** the PR that completes work also archives its plan, removes/updates its TODO entry, and writes the changelog/maintenance-log entry. No "will garden later" PRs.
2. **Plan ↔ TODO linkage (asymmetric):** every `exec-plans/active/*.md` plan MUST have a TO_DO entry linking to it. Not every TO_DO entry needs a plan (small items stay as one-liners).

## Non-goals

- No behavior/code changes to frontend/backend. Docs, guidance, and mechanical guardrail scripts only.
- No retroactive rewrite of released CHANGELOG sections (`[0.1.x]`). Only squash/dedupe `Unreleased`.

## Bootstrap exemption

This PR introduces the same-PR housekeeping contract, so it cannot itself fully satisfy it (the rule did not exist when the work started). This one bootstrap PR is explicitly exempt from the "housekeeping in the same PR that introduces the rule" circularity: it creates the TO_DO entry, the plan, and the guidance + enforcement in a single PR, and records the exemption here. All subsequent PRs follow the contract.

## Phase 0 — Baseline (evidence, persisted)

- [ ] Write baseline to `dev-docs/investigations/2026-09-19-docs-harness-baseline.md`: count `[x] done` lines in `TO_DO.md`, duplicate `###` sections in `CHANGELOG.md` Unreleased (`CHANGELOG.md:7-173` has Added x2, Fixed x3, Changed x3), stale `tech-debt-tracker.md` Opens, unindexed `dev-docs/*.md` root files.
- [ ] Include the plan↔TODO↔index cross-reference table in the baseline note (known mismatches at plan creation: `2026-09-15-self-host` in TO_DO but missing from `active/README.md`; `2026-07-22-reduce-minutes` in README but no TO_DO backlink; `2026-07-05`/`2026-07-06` in README but already completed/moved).
- [ ] Confirm `scripts/check-repo-structure.sh` current checks as the enforcement baseline.

## Phase 1 — TO_DO becomes active-only + plan-linkage rule

- [ ] Rewrite `dev-docs/backlog/TO_DO.md` header: active work only, no completed items retained; every active plan linked from a TODO line; small items may exist without a plan.
- [ ] Define done = log + delete: user-visible → `CHANGELOG.md` Unreleased; internal-only → new `maintenance-log.md` (Phase 2); plan-backed items → also move plan to `completed/` + index, same PR.
- [ ] Define `in progress YYYY-MM-DD` / `NEEDS REVIEW` semantics: date = last confirmed state; `in progress` >14d without a commit link is triageable.
- [ ] Migrate existing `[x] done` lines out of `TO_DO.md` (to CHANGELOG if missing, else to maintenance-log seed) and delete them from the file.

## Phase 2 — Maintenance log for under-the-hood work

- [ ] Create `dev-docs/backlog/maintenance-log.md` (append-only). Schema per entry: `## YYYY-MM-DD — <short outcome>` + `PR: #NN` + `Scope: <area>` + one-line outcome. Start the file with one seed entry in that exact format so executors copy it.
- [ ] Audit `CLAUDE.md` Plans/Changelog sections before amending (it currently duplicates `AGENTS.md` wording with drift); then amend Changelog Rule in `AGENTS.md` / `CLAUDE.md`: internal-only changes MUST log in `maintenance-log.md` and MUST NOT go in `CHANGELOG.md`.
- [ ] Seed maintenance-log with the internal-only subset of the migrated TO_DO done-lines + tech-debt Done rows.
- [ ] Index maintenance-log in `dev-docs/README.md` backlog table.

## Phase 3 — Same-PR housekeeping contract

- [ ] Add "Definition of Done (same PR)" checklist to `AGENTS.md` Plans section + `dev-docs/README.md` Plan rules: code/tests + CHANGELOG or maintenance-log entry + TODO line removed/updated + plan moved to `completed/` + both README indexes updated.
- [ ] State the asymmetric linkage explicitly: active plan without a TODO link = violation; TODO without a plan = allowed.
- [ ] Update `dev-docs/exec-plans/active/README.md` intro to point at the TODO-backlink requirement.

## Phase 4 — Mechanical enforcement in `check-repo-structure.sh`

- [ ] Warn (then error after transition): `[x].*done` lingering in `TO_DO.md`; `active/*.md` fully-checked but not moved; `active/README.md` disagreeing with `active/*.md`; duplicate `###` headings in CHANGELOG Unreleased; active plan with no backlink in `TO_DO.md`.
- [ ] Warn: active plan untouched >30d; `in progress` TODO >14d without update; `dev-docs` file unindexed; `investigations/` note >60d without triage decision.
- [ ] Keep new checks warn-only until the next release tag after merge (concrete gate, not an open "transition window"); record the tag in the plan when flipped to error.
- [ ] Rule carve-out: a plan may create its own TO_DO entry as its first step (as this plan did) — that satisfies the asymmetric linkage from creation, not retroactively.

## Phase 6 — Entry-point canonicalization (AGENTS canonical, others point)

Owner decision 2026-09-19: `CLAUDE.md` etc. mostly point to `AGENTS.md` instead of duplicating it. Execute with the Phases 1–3 guidance batch (numbered last only to avoid renumber churn).

- [ ] Add precedence line to `AGENTS.md`: on any conflict between entry-point guidance files, `AGENTS.md` wins.
- [ ] Fix known drifts once, in `AGENTS.md` only: basedpyright scope gains `scripts` (match `.pre-commit-config.yaml:192`); keep localhost/`require_escalated` retry note; full Changelog Rule with internal-only exemption; TODO-removal + asymmetric plan↔TODO rule.
- [ ] Strip `CLAUDE.md` duplicates → keep Claude-specific deltas only (sub-agent dir paths, invocation mechanism) + pointer to `AGENTS.md` for verification, principles, plans, changelog, deploy, PR conventions. Record an explicit keep-or-drop decision for the quick-verify snippet (highest-frequency need; either verbatim or pure pointer, not a paraphrase).
- [ ] `dev-docs/README.md` Plan rules block → pointer to the canonical `AGENTS.md` wording, not a paraphrase. `TO_DO.md` header → same one-liner.
- [ ] Add skills + sub-agents pointer block to both entry points (dir path + when to use); surface golden-principles 7–10 titles in entry points with details behind the link; `CLAUDE.md` gets pointers (not copies) for backend-deploy check and PR conventions.
- [ ] Enforcement simplification: `check-repo-structure.sh` checks the canonical `AGENTS.md` block only, not cross-file consistency.

## Phase 5 — One-time garden pass (same branch, separate commits)

- [ ] Squash `CHANGELOG.md` Unreleased duplicate sections into single Added/Changed/Fixed/Security/Removed (merge strategy: concatenate bullets under one heading each, preserving order Added → Changed → Fixed → Security → Removed; no bullet text rewritten, only heading dedupe). Verify with `grep -c '^### ' CHANGELOG.md` before/after on the Unreleased block.
- [ ] Sync `exec-plans/active/README.md` with actual `active/*.md` (remove completed 2026-07-05/2026-07-06 entries; add missing 2026-07-07, 2026-07-09, 2026-09-15 or move them if done).
- [ ] Triage `tech-debt-tracker.md` Opens (close `#8 No CI`, re-verify `#9 reccobeats mock`, etc.); move resolutions to Done + maintenance-log.
- [ ] Triage root `dev-docs/*.md` strays: index, move, or archive. Triage >60d investigations: promote to guides/references/design-decisions, archive, or delete.
- [ ] Verify: `./scripts/verify-all.sh` + `scripts/check-repo-structure.sh` clean (warnings triaged or recorded).

## Acceptance

- [ ] `TO_DO.md` contains zero `[x]` completed items; header states active-only + log-then-delete.
- [ ] `maintenance-log.md` exists, indexed, and seeded; guidance forbids internal entries in CHANGELOG.
- [ ] Same-PR DoD + asymmetric plan↔TODO rule present in `AGENTS.md`, `CLAUDE.md` (short form), and `dev-docs/README.md`.
- [ ] Structure script enforces (or warns with release-tagged flip) the new rules; garden pass clears baseline drift.
- [ ] Entry-point canonicalization done: no paraphrased duplicates of plan/changelog/verify rules across `AGENTS.md` / `CLAUDE.md` / `dev-docs/README.md`; `CLAUDE.md` diff vs `AGENTS.md` shows only deltas + pointers; precedence line present.
- [ ] Kilo reviewer feedback addressed: (1) self-violation fixed via TO_DO entry + first-step carve-out, (2) bootstrap exemption recorded, (3) Phase 0 persists to a baseline note with cross-reference table, (4) CHANGELOG merge strategy specified, (5) `check-repo-structure.sh` gaps enumerated against current lines, (6) CLAUDE.md audit step added, (7) maintenance-log schema + seed specified, (8) warn→error gate tied to next release tag.

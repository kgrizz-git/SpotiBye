# Docs Harness Housekeeping — TO_DO lifecycle, maintenance log, same-PR gardening

**Date:** 2026-09-19
**Branch:** `chore/docs-harness-housekeeping`
**Status:** draft v4 — kilo + agy reviewer feedback incorporated; Phase 6 rewritten as generate-don't-point
**Backlog link:** `dev-docs/backlog/TO_DO.md` → "Docs harness housekeeping" entry under Repo Cleanup & DevOps (added 2026-09-19; this plan satisfies its own asymmetric plan↔TODO rule)

## Goal

Make `TO_DO.md` active-only, give internal-only work a durable home other than `CHANGELOG.md`, and make housekeeping part of the completing PR — not a follow-up pass.

Two owner constraints (normative for this plan):

1. **Same-PR housekeeping:** the PR that completes work also archives its plan, removes/updates its TODO entry, and writes the changelog/maintenance-log entry. No "will garden later" PRs.
2. **Plan ↔ TODO linkage (asymmetric):** every `exec-plans/active/*.md` plan MUST have a TO_DO entry linking to it. Not every TO_DO entry needs a plan (small items stay as one-liners).

## Non-goals

- No behavior/code changes to frontend/backend. Docs, guidance, and mechanical guardrail scripts only.
- No retroactive rewrite of released CHANGELOG sections (`[0.1.x]`). Only squash/dedupe `Unreleased`.

## Bootstrap exemption (one-time authorship ordering, not a recurring mechanism)

This PR introduces the same-PR housekeeping contract, so the contract cannot have governed its own authorship: the TO_DO entry, the plan draft, and the reviewer rounds were necessarily written before the rule text existed. This is recorded here once as authorship ordering within a single bootstrap PR — not as a "first step" exemption CI could ever evaluate (pre-commit only sees the final tree). All subsequent PRs follow the contract with no exemption.

## Phase 0 — Baseline (evidence, persisted)

- [x] Write baseline to `dev-docs/investigations/2026-09-19-docs-harness-baseline.md`: count `[x] done` lines in `TO_DO.md`, duplicate `###` sections in `CHANGELOG.md` Unreleased (`CHANGELOG.md:7-173` has Added x2, Fixed x4, Changed x3 — Fixed count corrected from x3 during the garden pass), stale `tech-debt-tracker.md` Opens, unindexed `dev-docs/*.md` root files.
- [x] Include the plan↔TODO↔index cross-reference table in the baseline note (known mismatches at plan creation: `2026-09-15-self-host` in TO_DO but missing from `active/README.md`; `2026-07-22` backlink verified present in TO_DO:118 — plan text was stale, see baseline note §5; `2026-07-05`/`2026-07-06` in README but already completed/moved).
- [x] Confirm `scripts/check-repo-structure.sh` current checks as the enforcement baseline.

## Phase 1 — TO_DO becomes active-only + plan-linkage rule

- [x] Rewrite `dev-docs/backlog/TO_DO.md` header: active work only, no completed items retained; every active plan linked from a TODO line; small items may exist without a plan.
- [x] Define done = log + delete: user-visible → `CHANGELOG.md` Unreleased; internal-only → new `maintenance-log.md` (Phase 2); plan-backed items → also move plan to `completed/` + index, same PR.
- [x] Define `in progress YYYY-MM-DD` / `NEEDS REVIEW` semantics: date = last confirmed state; `in progress` >14d without a commit link is triageable.
- [x] Migrate existing `[x] done` lines out of `TO_DO.md` (to CHANGELOG if missing, else to maintenance-log seed) and delete them from the file.

## Phase 2 — Maintenance log for under-the-hood work

- [x] Create `dev-docs/backlog/maintenance-log.md` (append-only). Schema per entry: `## YYYY-MM-DD — <short outcome>` + `PR: #NN` + `Scope: <area>` + one-line outcome. Start the file with one seed entry in that exact format so executors copy it.
- [x] Audit `CLAUDE.md` drift vs `AGENTS.md` (known: basedpyright scope, localhost note, changelog exemption, plan-linkage rule), then amend the Changelog Rule in the `AGENTS.md` source: internal-only changes MUST log in `maintenance-log.md` and MUST NOT go in `CHANGELOG.md`. `CLAUDE.md` inherits via the Phase 6 generator — never hand-edit generated content.
- [x] Seed maintenance-log with the internal-only subset of the migrated TO_DO done-lines + tech-debt Done rows.
- [x] Index maintenance-log in `dev-docs/README.md` backlog table.

## Phase 3 — Same-PR housekeeping contract

- [x] Add "Definition of Done (same PR)" checklist with canonical wording in `AGENTS.md` Plans section: code/tests + CHANGELOG or maintenance-log entry + TODO line removed/updated + plan moved to `completed/` + both README indexes updated. `dev-docs/README.md` points at it; `CLAUDE.md` inherits it via the Phase 6 generator.
- [x] State the asymmetric linkage explicitly: active plan without a TODO link = violation; TODO without a plan = allowed.
- [x] Update `dev-docs/exec-plans/active/README.md` intro to point at the TODO-backlink requirement.

## Phase 4 — Mechanical enforcement (Python for new cross-file checks)

Bash stays for the existing `check-repo-structure.sh` checks. All new cross-file checks go in a Python script following the `scripts/check_file_lengths.py` precedent (`pathlib` + `re` — bash markdown parsing is too brittle for index/backlink validation).

- [x] New Python check warns (then errors after transition): `[x].*done` lingering in `TO_DO.md`; `active/*.md` fully-checked but not moved; `active/README.md` disagreeing with `active/*.md`; duplicate `###` headings in CHANGELOG Unreleased; active plan with no backlink in `TO_DO.md`; generated `CLAUDE.md` out of sync with its source (see Phase 6).
- [x] New Python check warns: active plan untouched >30d; `in progress` TODO >14d without update; `dev-docs` file unindexed; `investigations/` note >60d without triage decision.
- [ ] Record the release tag in the plan when the warn-only gate flips to error (future: next release tag after merge).
- [ ] Rule carve-out: a plan satisfies the asymmetric linkage if its TO_DO entry is authored anywhere inside the same bootstrap PR that creates it (as this plan did) — authorship ordering, not a CI-evaluated sequence.

## Phase 6 — Entry-point canonicalization (generate, don't point)

Agy review overturned the v3 pointer model: Claude auto-loads `CLAUDE.md` but does not traverse markdown links, so pointer-stripped entry points lose their guardrails and an `AGENTS.md`-side precedence line is unenforceable from outside the context window. Execute with the Phases 1–3 guidance batch (numbered last only to avoid renumber churn).

- [x] `AGENTS.md` is the single source of truth. Fix known drifts once, there: basedpyright scope gains `scripts` (match `.pre-commit-config.yaml:212`); keep localhost/`require_escalated` retry note; full Changelog Rule with internal-only exemption; TODO-removal + asymmetric plan↔TODO rule; precedence line as a backstop (not the primary mechanism).
- [x] Add a pre-commit hook that compiles `CLAUDE.md` from the `AGENTS.md` source, injecting the Claude-specific deltas at the top (sub-agent dir paths, invocation mechanism). Zero human drift plus full eager context loading — no link traversal required.
- [x] Mark `CLAUDE.md` as generated (header marker: do not hand-edit; edit the source + template instead). The hook fails the commit when the generated file is out of sync, the same way formatting hooks do.
- [x] Decide the generator's content policy explicitly and record it: full-fidelity compile vs trimmed subset. Default to full-fidelity unless the compiled size forces a trim; any trim is an allowlist recorded in the hook config, never ad-hoc paraphrase.
- [x] `dev-docs/README.md` Plan rules block → pointer to the canonical `AGENTS.md` wording (READMEs are not auto-loaded agent context, so a pointer is safe there). `TO_DO.md` header → same one-liner.
- [x] Fold into the compile: skills + sub-agents pointer block (dir path + when to use), golden-principles 7–10 titles with details behind the link, backend-deploy check, PR conventions.

## Phase 5 — One-time garden pass (same branch, separate commits)

- [x] Squash `CHANGELOG.md` Unreleased duplicate sections into single Added/Changed/Fixed/Security/Removed (merge strategy: concatenate bullets under one heading each, preserving order Added → Changed → Fixed → Security → Removed; no bullet text rewritten, only heading dedupe). Verify with `grep -c '^### ' CHANGELOG.md` before/after on the Unreleased block.
- [x] Sync `exec-plans/active/README.md` with actual `active/*.md` (remove completed 2026-07-05/2026-07-06 entries; add missing 2026-07-07, 2026-07-09, 2026-09-15 or move them if done).
- [x] Triage `tech-debt-tracker.md` Opens (close `#8 No CI`, re-verify `#9 reccobeats mock`, etc.); move resolutions to Done + maintenance-log.
- [x] Triage root `dev-docs/*.md` strays: index, move, or archive. Triage >60d investigations: promote to guides/references/design-decisions, archive, or delete.
- [x] Verify: `./scripts/verify-all.sh` + `scripts/check-repo-structure.sh` clean (warnings triaged or recorded).

## Acceptance

- [ ] `TO_DO.md` contains zero `[x]` completed items; header states active-only + log-then-delete.
- [ ] `maintenance-log.md` exists, indexed, and seeded; guidance forbids internal entries in CHANGELOG.
- [ ] Same-PR DoD + asymmetric plan↔TODO rule present in `AGENTS.md`, the hook-compiled full-fidelity `CLAUDE.md`, and `dev-docs/README.md` (pointer).
- [ ] Structure script enforces (or warns with release-tagged flip) the new rules; garden pass clears baseline drift.
- [ ] Entry-point canonicalization done: `CLAUDE.md` carries a generated-file marker and is byte-identical to hook output (in-sync check green); no hand-maintained paraphrased duplicates of plan/changelog/verify rules; generator trim policy (if any) recorded in hook config.
- [ ] Kilo reviewer feedback addressed: (1) self-violation fixed via TO_DO entry + authorship-ordering carve-out, (2) bootstrap exemption recorded as one-time ordering, (3) Phase 0 persists to a baseline note with cross-reference table, (4) CHANGELOG merge strategy specified, (5) enforcement gaps enumerated against current script lines, (6) CLAUDE.md audit step added, (7) maintenance-log schema + seed specified, (8) warn→error gate tied to next release tag.
- [ ] Agy reviewer feedback addressed: (1) pointer model replaced with hook-compiled generation (eager context preserved), (2) new cross-file checks assigned to Python not bash, (3) bootstrap carve-out reworded as authorship ordering, not a CI-evaluated sequence.

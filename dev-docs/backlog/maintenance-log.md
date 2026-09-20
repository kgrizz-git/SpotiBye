# Maintenance Log

> Append-only log for internal-only work. User-visible changes go in `CHANGELOG.md`.
> One entry per completed PR or internal housekeeping action. Schema:
>
>     ## YYYY-MM-DD — <short outcome>
>     PR: #NN (or `PR: n/a` with a reason for bootstrap/predated entries)
>     Scope: <area>
>     <one-line outcome>

---

## 2026-09-19 — Docs harness baseline captured

PR: n/a (bootstrap entry; landed via docs-harness housekeeping branch)
Scope: docs-harness

Captured baseline evidence for docs harness housekeeping: 39 `[x]` done lines in TO_DO.md, duplicate `###` headings in CHANGELOG Unreleased (Added×2, Changed×3, Fixed×4), 9 stale Open rows in tech-debt-tracker.md, 2 unindexed root `dev-docs/*.md` files, and the plan↔TODO↔index cross-reference mismatches. Persisted to `dev-docs/investigations/2026-09-19-docs-harness-baseline.md`.

## 2026-06-19 — Legacy plans migrated to exec-plans/completed/legacy

PR: n/a (predates PR-linking; date from tech-debt Done row)
Scope: docs-organization

Consolidated legacy plan files under `dev-docs/exec-plans/completed/legacy/`; active/completed indexes updated.

## 2026-06-27 — basedpyright pre-push hook and pyright triage

PR: n/a (predates PR-linking; migrated from TO_DO 2026-09-19)
Scope: `src/frontend/`, `.pre-commit-config.yaml`

Added basedpyright as a pre-push hook and resolved all frontend pyright errors to 0. The open follow-up ("larger type-safety work") was dropped as stale: nothing remains beyond the enforced hook.

## 2026-06-29 — CI Node version bumped to 24 LTS

PR: n/a (predates PR-linking; migrated from TO_DO 2026-09-19)
Scope: `.github/workflows`, `.nvmrc`

Bumped CI Node version from past-EOL 20 to 24 LTS (`.nvmrc` single source of truth, `@types/node@^24`).

## 2026-07-07 — Backend auth test coverage for token expiration

PR: n/a (predates PR-linking; migrated from TO_DO 2026-09-19)
Scope: `src/backend/tests/`

Added backend unit/integration tests for Spotify token expiration handling (`invalid_grant` → 401 `AUTH_REQUIRED`, KV session deletion, refresh dedup, `REFRESH_FAILED` cache, `safeParseSession`, `/auth/me` shape, queue auth-failure behavior). Test-only; the user-visible re-auth prompt itself is logged in CHANGELOG.

## 2026-07-07 — Frontend auth test coverage for token expiration

PR: n/a (predates PR-linking; migrated from TO_DO 2026-09-19)
Scope: `src/frontend/tests/`

Added frontend tests for token expiration handling (`BackendAPIError` error_code, cache wipes, `_format_backend_api_error`, `_download_file`, `_try_auto_login` branches). Test-only; the user-visible behavior is logged in CHANGELOG.

## 2026-09-19 — Triage 5 stale tech-debt rows closed

PR: #11
Scope: `dev-docs/backlog/tech-debt-tracker.md`

Closed 5 stale Open rows with verified tree evidence: #4 bare `except:` (absent in `src/frontend/`), #5 legacy directories (absent from tree), #6 no-restricted-imports (migrated to flat `eslint.config.mjs`), #8 No CI (`.github/workflows/` present), #9 reccobeats mock (`reccobeats.ts` removed; real integration via `reccobeats-track-cache.ts` + `analysis.ts`). Moved to Done table with resolution date 2026-09-19.

## 2026-09-19 — Changelog Unreleased duplicate-heading squash

PR: #11
Scope: `CHANGELOG.md`

Squashed 11 duplicate `### ` headings in `[Unreleased]` into single Added/Changed/Fixed/Security/Removed sections (order: Added → Changed → Fixed → Security → Removed). Concatenated all bullets under each surviving heading without rewriting bullet text, then removed 15 exact-duplicate bullet lines (pre-existing repeats across the old duplicate sections, e.g. the GitHub Actions optimization block). Verified zero remaining intra-section duplicate bullets and `### ` count 11 to 5 in the Unreleased block.

## 2026-09-19 — Active plan index sync in exec-plans/active/README.md

PR: #11
Scope: `dev-docs/exec-plans/active/README.md`

Removed completed 2026-07-05/2026-07-06 rows; added missing active rows for 2026-07-07-file-length, 2026-07-09-split-dependabot, 2026-09-15-self-host, 2026-09-19-docs-harness-housekeeping. Descriptions copied from plan file titles/intros.

## 2026-09-19 — Verified alleged unindexed root dev-docs files

PR: #11
Scope: `dev-docs/README.md`

Baseline §4 had listed `bug-fix-plan-2026-06-15.md` and `bug-review-2026-06-15-112416.md` as unindexed strays; verification showed both were already indexed in the current-notes table. No change needed; baseline §4 corrected.

## 2026-09-19 — Record aging-investigation triage recommendations

PR: #11
Scope: `dev-docs/investigations/2026-09-19-docs-harness-baseline.md`

Appended §6 to baseline note with per-note triage recommendations for root `dev-docs/*.md` files older than 60 days (`2026-06-22-backend-deployment-tracking.md`, `2026-06-26-reccobeats-wiring-assessment.md`). Did not mass-move files.

## 2026-09-19 — Retired stale PR#20 split-dependabot plan

PR: #12
Scope: `dev-docs/backlog/TO_DO.md`, `dev-docs/exec-plans/`

Retired the PR#20 dev-dependency split item (PR never existed post-migration; goal landed piecemeal via PRs #2, #3, #7 + flat-config migration). Kept 2 verified residuals as plain TO_DO one-liners (npm overrides watch, `index.ts` wiring decision); moved plan to `completed/` with index updates.

## 2026-09-19 — Scoped dev-docs README link check to top-level files

PR: #13
Scope: `scripts/check-repo-structure.sh`

Narrowed the dev-docs README linkage check from `maxdepth 2` to `maxdepth 1`: subdir notes are indexed at directory level with a curated selection (per `dev-docs/README.md`), matching `check_docs_hygiene.py`. Silenced 17 false-positive unlinked-note warnings.

## 2026-09-19 — Progress-bar plan close-out pass

PR: #14
Scope: `dev-docs/exec-plans/active/2026-07-11-backend-playlist-analysis-progress-bar.md`, `dev-docs/backlog/TO_DO.md`

Re-ran all runnable verifications green (backend 855 tests, lint 0 errors; frontend 257 passed; pyright clean); checked 2 verification + 4 acceptance boxes with tree evidence; re-dated TO_DO to `in progress 2026-09-19`. Left: live dev-worker trace, NPR diagnostic run-or-drop, optional cancellation.

Follow-up on PR #14: added `scripts/trace-analysis-progress.sh` (one-command live trace: fresh job + 2s status poll to `tmp/*.jsonl` + results/genre summary) and an owner runbook in the plan step; the NPR run is folded into the same command (trace `5X8lN5fZSrLnXzFtDEUwb9`, check `genre buckets > 0`). Cancellation logged as a TO_DO follow-up instead of implemented.

Live-trace result 2026-09-19 (dev `e96f00a`, NPR `5X8lN5fZSrLnXzFtDEUwb9`): status advanced `queued:0 → processing:50 → processing:75 → completed:100` (DO-backed reads confirmed, no staleness); genres present (15 buckets, 24/40 artists, tolerant-404 fix confirmed live). Live finding: ReccoBeats enrichment hit the Workers subrequest limit on this large playlist — feeds the existing fan-out TO_DO item. Remaining plan box: optional cancellation only.

CodeRabbit hardening on PR #14: trace script takes the bearer token via env/pipe/prompt only (curl `-K` 0600 config + trap cleanup, never argv); BACKEND_URL must be https except loopback; per-run `mktemp -d` dir under `tmp/`; plan claim narrowed to backend payload (rendering covered by popup tests).

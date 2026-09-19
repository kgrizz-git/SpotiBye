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

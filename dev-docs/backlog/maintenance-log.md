# Maintenance Log

> Append-only log for internal-only work. User-visible changes go in `CHANGELOG.md`.
> One entry per completed PR or internal housekeeping action. Schema:
>
>     ## YYYY-MM-DD — <short outcome>
>     PR: #NN
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

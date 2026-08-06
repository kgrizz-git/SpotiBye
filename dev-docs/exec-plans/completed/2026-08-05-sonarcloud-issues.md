# Fix SonarCloud Bug & Top Issues

**Created:** 2026-08-05
**Status:** Complete
**Estimated debt:** 2,474 min (~41 hours) total, this plan targets ~60 min

---

## Context

Last SonarCloud scan: 2026-08-05 19:28 UTC (revision `43a90a6`).
Quality Gate: **PASSED** (new code meets all thresholds).
Open issues: 254 total — 1 bug, 28 vulnerabilities, 225 code smells.

This plan fixes the 1 bug, suppresses 3 false-positive vulnerabilities, hardens 13 CI supply-chain warnings, extracts 4 complex nested ternaries, and migrates 41 logging calls to use proper exception handling.

---

## Steps

- [x] **1. Fix the bug in `check-dependencies.py`**
  - File: `scripts/check-dependencies.py:155`
  - Change: `return 0 if all_passed else 0` → `return 0`
  - The `--ci` case is already handled by `sys.exit(1)` on line 152–153.
  - Verify: `python scripts/check-dependencies.py --security` still exits 0.

- [x] **2. Suppress HTTP false positives (4 issues — plan amended)**
  - Files:
    - `src/frontend/auth/backend_auth.py:163` — OAuth loopback callback, required by Spotify PKCE flow
    - `src/frontend/services/backend_client.py:39` — HTTP default for local dev
    - `src/frontend/services/backend_client.py:75` — HTTP adapter mount for localhost dev
    - `src/frontend/config/backend_config.py:73` — loopback default URL
  - Change: Added `# NOSONAR: python:S5332` with justification comment.

- [x] **3. CI supply-chain hardening (13 issues)**
  - Files: `.github/workflows/ci.yml`, `build.yml`, `deploy-production.yml`
  - Specific fixes:
    - Added `"typecheck": "tsc --noEmit"` to `src/backend/package.json`
    - `ci.yml:40` — Replaced `npx tsc --noEmit` with `npm run typecheck`
    - `build.yml` — Moved top-level `contents: write` to `release` job level; top-level set to `contents: read`
    - `deploy-production.yml` — Removed top-level `actions: write`; `deploy-prod` job retains only `contents: read` + `deployments: write`
    - `deploy-production.yml` — Restored `npm run lint` (was incorrectly commented out; ESLint is functional)
  - Note: Did NOT add `--only-binary=:all:` for Kivy/KivyMD (source fallback builds needed on Linux)
  - Note: `deploy-backend.yml` was correctly scoped already — plan was wrong to target it

- [x] **4. Extract nested ternaries (4 high-value sites)**
  - `src/backend/routes/export/helpers/format.ts` (`resolveStepSize`) — Flattened internal nested ternary to `if/else`
  - `src/backend/routes/export/jobs.ts` (`keyChecks`) — Refactored to `if/else if/else` block inline
  - `src/backend/routes/export/jobs.ts` (`resolvedMode`) — Refactored to `if/else if/else` block inline
  - `src/backend/middleware/error.ts` (status→code mapping) — Extracted to `httpStatusCodes` lookup object
  - Note: Helpers were kept inline in `jobs.ts` rather than extracted to `format.ts` to avoid cross-layer dependency (cache key builders do not belong in format.ts)

- [x] **5. Logger migration — split by intent (41 issues)**
  - **Converted to `logger.exception()`** (unexpected `except Exception as e:` blocks):
    - `backend_auth.py`: Error handling OAuth callback, open browser, login flow, callback server start/stop, logout, token refresh error
  - **Kept `logger.error` with lazy `%s`** (expected typed catches or non-except calls):
    - `backend_auth.py`: OAuth error string, BackendAPIError exchange, auth failed string, BackendAPIError token refresh
    - `network_utils.py`: All network decorators (re-raise pattern), progress callbacks, health check
    - `backend_login_screen.py`: All 6 error calls
    - `reccobeats_backend.py`: All 3 error calls + unknown status warning
    - `caching/backend_cache.py`: All 9 error calls
    - `services/backend_client.py`: All 4 error calls
    - `app/backend_app.py`: All 5 error/warning calls
    - `screens/adapter_mixins/exports.py`: 4 calls
    - `screens/adapter_mixins/tracks.py`: 3 calls
    - `screens/adapter_mixins/analysis.py`: 4 calls
    - `screens/adapter_mixins/playlists.py`: 1 call
    - `screens/adapter_mixins/utilities.py`: 2 calls
    - `screens/adapter_mixins/exports_download.py`: 1 call
    - `screens/adapter_mixins/exports_resumable.py`: 1 call

- [x] **6. Verification**
  - Backend typecheck: `npm run typecheck` — clean
  - Backend tests: `npm run test:run` — 848 passed
  - Python typecheck: `.venv/bin/basedpyright src/frontend src/shared --level error` — 0 errors
  - Frontend tests: `.venv/bin/pytest src/frontend/tests/ -v` — 257 passed, 7 skipped

---

## Not in scope

- `console.*` in backend — already wrapped by `utils/logger.ts`, not flagged by SonarCloud (S2228 returns 0)
- S3457 (f-string logging) — 0 issues from SonarCloud
- S3776 (cognitive complexity) — 33 issues but large refactor, out of scope for this PR

---

## References

- SonarCloud project: `kgrizz-git_SpotiBye` (org: `kgrizz-git`)
- Token: `.sonar_cloud_token` at repo root
- Dashboard: https://sonarcloud.io/dashboard?id=kgrizz-git_SpotiBye

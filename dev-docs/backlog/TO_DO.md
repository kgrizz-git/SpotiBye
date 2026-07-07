# To-Do List

Each top-level checkbox should be one shippable outcome. Use nested checkboxes for acceptance criteria or required follow-up steps. Move anything that needs more than about one day of work to `dev-docs/exec-plans/active/`.

## Auth & Token Lifecycle

- [x] Handle Spotify refresh token expiration before July 20, 2026 ([plan](../exec-plans/completed/2026-07-06-spotify-token-expiration-handling.md)) — **done 2026-07-06**
- [ ] Add backend unit/integration tests for Spotify token expiration handling
  - [ ] Mock Spotify token endpoint returning `{ error: "invalid_grant" }` → verify middleware deletes KV session and returns `401` with `code: 'AUTH_REQUIRED'`
  - [ ] Verify `errorHandler` preserves explicit `AUTH_REQUIRED` code without mapping to `UNAUTHORIZED`
  - [ ] Verify `refreshPromises` Map and `REFRESH_FAILED` negative cache prevent concurrent refresh race conditions
  - [ ] Verify `REFRESH_FAILED` check fires **before** `refreshPromises` lookup — not after
  - [ ] Verify that on successful refresh, the `REFRESH_FAILED:<session_id>` KV key is deleted
  - [ ] Verify `REFRESH_FAILED:<session_id>` TTL is ≥ 60 seconds (Cloudflare KV minimum)
  - [ ] Verify `/spotify/refresh` route no longer calls `spotifyAuth.refreshAccessToken()` directly
  - [ ] Verify `AnalysisJobService` and `queue()` consumer fail immediately on `AUTH_REQUIRED` without retrying
  - [ ] Verify `safeParseSession` returns `null` for malformed JSON, missing required fields, and schema violations
  - [ ] Verify `GET /auth/me` returns shape `{ data: { id, email, name, session_id } }` for authenticated requests
- [ ] Add frontend tests for Spotify token expiration handling
  - [ ] Verify `BackendAPIError` correctly extracts and sets `error_code='AUTH_REQUIRED'`
  - [ ] Verify `BackendAuthenticator.refresh_token()` wipes **both** in-memory and disk cache on `AUTH_REQUIRED` and returns `False`
  - [ ] Verify `handle_session_expired` wipes the disk cache (design reversal from implementation)
  - [ ] Verify `_format_backend_api_error` output contains `code=AUTH_REQUIRED` so `main_screen.py` detects it
  - [ ] Verify `_download_file` 401 `AUTH_REQUIRED` responses surface `error_code='AUTH_REQUIRED'` on the raised `BackendAPIError`
  - [ ] Verify `_try_auto_login` with a transport error (`BackendAPIError(status_code=None)`) proceeds to main screen without wiping cache
  - [ ] Verify `_try_auto_login` with a 401 `AUTH_REQUIRED` wipes disk cache and keeps user on login screen

## Playlist Analysis — End-to-End

- [ ] Add visual progress indicator for playlist analysis
  - [ ] Wire `analysis_task` progress into the frontend state
  - [ ] Render in-progress, completed, and failed states in the UI
  - [ ] Add focused frontend tests for progress rendering
- [ ] Refactor playlist analysis to fan-out queue architecture for large playlists
  - [ ] Preserve existing Track D queue behavior
  - [ ] Split work into distributed batches for playlists with more than 40 artists per Worker invocation
  - [ ] Add backend tests for batch fan-out and aggregation
- [ ] Close ReccoBeats enrichment gaps in playlist analysis popup
  - [ ] Display missing audio features (instrumentalness, liveness, loudness, speechiness) and key/mode
  - [ ] Optionally fetch `GET /v1/track` for ISRC and ReccoBeats popularity metadata
  - [ ] Investigate `GET /v1/track/recommendation` for mood/energy-based track recommendations
  - [ ] Reconcile or remove unimplemented `recommendations` / `energy_score` fields from OpenAPI spec and docs
  - [ ] Translate "Mood (Valence)" into human-readable labels (e.g., "Melancholic", "Cheerful") or add a scale explanation, because a raw percentage (e.g., "45%") does not communicate that lower = sadder and higher = happier
  - **Investigation:** [2026-07-05-reccobeats-enrichment-gaps.md](../investigations/2026-07-05-reccobeats-enrichment-gaps.md) — we retrieve 9 audio features but only display 5, ignore key/mode, skip the track-metadata endpoint entirely, and do not use the ReccoBeats track-recommendation endpoint; our OpenAPI spec also documents a `recommendations` feature that is not implemented in the backend.

**Related notes:** [API enrichment](spotify-api-enrichment.md) · [ReccoBeats contract](reccobeats-api-contract.md) · [ReccoBeats enrichment gaps](../investigations/2026-07-05-reccobeats-enrichment-gaps.md)



## Code Quality / Tech Debt

- [ ] Fix deprecated `AsyncImage` properties (`allow_stretch`, `keep_ratio`)
- [x] Add basedpyright as a pre-push hook in `.pre-commit-config.yaml` ([plan](../exec-plans/completed/2026-06-27-basedpyright-prepush-hook.md)) — **done 2026-06-27**
- [x] Run pyright and triage type issues **NEEDS REVIEW**
  - [x] Document the exact command and current issue count
    - [`dev-docs/assessments/pyright-utils.md`](../assessments/pyright-utils.md) — `src/frontend/utils/` (16 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-config.md`](../assessments/pyright-config.md) — `src/frontend/config/` (1 error) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-caching.md`](../assessments/pyright-caching.md) — `src/frontend/caching/` (2 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-app.md`](../assessments/pyright-app.md) — `src/frontend/app/` (4 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-auth.md`](../assessments/pyright-auth.md) — `src/frontend/auth/` (14 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-services.md`](../assessments/pyright-services.md) — `src/frontend/services/` (3 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-ui.md`](../assessments/pyright-ui.md) — `src/frontend/ui/` (110 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-screens.md`](../assessments/pyright-screens.md) — `src/frontend/screens/` (~160 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-adapter-mixins.md`](../assessments/pyright-adapter-mixins.md) — `src/frontend/screens/adapter_mixins/` (147 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-tests.md`](../assessments/pyright-tests.md) — `src/frontend/tests/` (49 errors) — **fixed 2026-06-27**
    - [`dev-docs/assessments/pyright-root.md`](../assessments/pyright-root.md) — `src/frontend/` root files (0 errors)
  - [x] Fix straightforward issues (all pyright errors resolved — verified `basedpyright src/frontend src/shared --level error` returns 0 errors)
  - [ ] Create follow-up backlog items or an execution plan for larger type-safety work
- [ ] Track/remove `esbuild` and `uuid` npm overrides in `src/backend/package.json` once upstream ships patched releases

## Repo Cleanup & DevOps

- [ ] Remove unused tracked backup and generated files
- [ ] Remove stale references to `src/spotify_playlist_exporter_v2/`
- [ ] Audit duplicate code candidates and create focused follow-up plans
- [ ] Review outdated docs now that `docs/` and `dev-docs/` are split
- [ ] Audit `.gitignore` vs tracked files (venv, node_modules, caches, IDE, `.DS_Store`; verify `.github/` and `.skills/` tracking)
- [ ] Decide on default window size and placement
- [ ] Verify release build pipeline
  - [ ] Confirm frontend packaging command and output artifact
  - [ ] Confirm backend deployment workflow and required secrets
  - [ ] Confirm CI runs the expected frontend, backend, and structure checks
- [x] Bump CI Node version from 20 (EOL Apr 2026) to 24 LTS ([plan](../exec-plans/completed/2026-06-28-bump-ci-node-24.md)) — **done 2026-06-29**
- [ ] Check GitHub Actions minutes usage and see if any can be trimmed
- [ ] Decide whether to start a new repository before wider release-readiness work
  - [ ] Complete repository cleanup prerequisites
  - [ ] Decide what history, issues, and release artifacts must be retained
  - [ ] Document the migration decision before creating a new repository

See also: agent-first-retrofit, quality review/assessment

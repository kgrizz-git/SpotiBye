# To-Do List

## Major Tasks

- [ ] **High Priority: Complete main screen refactor** — [completion plan](../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md). Most extraction work is complete; remaining work is cleanup, cancellation branch coverage, and full verification.
  - [x] Task 0: Cleanup dead code (_show_error_dialog, _log_error, _update_export_status)
  - [x] Task 1: Extract filename and format helpers -> `main_screen_filenames.py` + tests
  - [x] Task 1.5: Extract sort and filter helpers -> `main_screen_sort_filter.py` + tests
  - [x] Task 2: Fix export cancellation state in `state.py` + tests
  - [x] Task 3: Make playlist widget factory hook real in `MainScreen` / `BackendMainScreen`
  - [x] Task 4: Extract cache and logout flows -> `main_screen_cache.py`, `main_screen_logout.py`
  - [x] Task 5: Extract backend error popup -> `main_screen_error_popup.py`
  - [x] Task 6: Extract export orchestration -> `main_screen_export.py`, `main_screen_scheduler.py`
  - [ ] Completion Task A: Remove stale imports from `main_screen.py`
  - [ ] Completion Task B: Add export cancellation branch coverage
  - [ ] Completion Task C: Run full verification and update this item

- Track backend npm security overrides
    Remove the `esbuild` and `uuid` overrides in `src/backend/package.json` once Wrangler and ExcelJS publish versions that depend on patched releases directly. Keep `npm audit --audit-level=moderate`, `npm run build`, `npm run test:run`, and `npx wrangler deploy --dry-run` green when removing them.

- Refactor Code and Extract Necessary Sections
    Extract and refactor necessary sections from the old `src/spotify_playlist_exporter_v2/` codebase. Identify reusable components, utilities, and logic that should be migrated to the new project structure.

- Clean Up Repository
    Perform a comprehensive cleanup of the repository, removing:
    - Unused files and directories
    - Backup copies and duplicate code
    - Outdated documentation
    - Temporary or cache files that shouldn't be in version control

- Check for pyright issues and fix them

- start new repo, after cleaning, before widespread release-readiness

- update / check build etc

- decide on default size, see if can better place it

* see [backend analysis routes](backend-analysis-routes.md) and [playlist analysis popup notes](playlist-analysis-popup.md)
* [fix ReccoBeats pipeline and wire to backend route](plans/reccobeats-wiring.md)
* [Spotify API enrichment — available data for playlist details](spotify-api-enrichment.md)
* restore reccobeats analysis functionality

* see agent-first-retrofit, quality review/assessment md

- fix issues with RECOCOBEATS vs RECCOBEATS

- Fix playlist analysis 403 error — Spotify API February 2026 migration removed `GET /artists` batch endpoint
    * [Fix plan](plans/fix-analysis-403-spotify-api-migration.md)

- Handle Spotify refresh token expiration (6-month limit) — announced June 18, 2026, enforced July 20, 2026 for existing apps
    * Handle `invalid_grant` error on token refresh: discard stored tokens, redirect user to re-sign-in
    * Do not assume refresh tokens are permanent — audit all token storage/refresh logic
    * Test reauthorization flow — users must be able to sign in again smoothly
    * Consider storing authorization timestamp to track expiration proactively

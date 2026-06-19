# To-Do List

## Major Tasks

- [x] **High Priority: Complete main screen refactor** — [completion plan](../docs/superpowers/plans/2026-06-19-main-screen-refactor-completion-plan.md). Completed after cleanup, cancellation branch coverage, and full verification.
  - [x] Task 0: Cleanup dead code (_show_error_dialog, _log_error, _update_export_status)
  - [x] Task 1: Extract filename and format helpers -> `main_screen_filenames.py` + tests
  - [x] Task 1.5: Extract sort and filter helpers -> `main_screen_sort_filter.py` + tests
  - [x] Task 2: Fix export cancellation state in `state.py` + tests
  - [x] Task 3: Make playlist widget factory hook real in `MainScreen` / `BackendMainScreen`
  - [x] Task 4: Extract cache and logout flows -> `main_screen_cache.py`, `main_screen_logout.py`
  - [x] Task 5: Extract backend error popup -> `main_screen_error_popup.py`
  - [x] Task 6: Extract export orchestration -> `main_screen_export.py`, `main_screen_scheduler.py`
  - [x] Completion Task A: Remove stale imports from `main_screen.py`
  - [x] Completion Task B: Add export cancellation branch coverage
  - [x] Completion Task C: Run full verification and update this item

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

* see [backend analysis routes](backend-analysis-routes.md) and [playlist analysis popup notes](playlist-analysis-popup.md); related implementation plans: [ReccoBeats wiring](plans/reccobeats-wiring.md), [Spotify 403 analysis fix](plans/fix-analysis-403-spotify-api-migration.md)
* [fix ReccoBeats pipeline and wire to backend route](plans/reccobeats-wiring.md)
* [Spotify API enrichment — available data for playlist details](spotify-api-enrichment.md)
* restore reccobeats analysis functionality — see [ReccoBeats wiring plan](plans/reccobeats-wiring.md) and [Spotify 403 analysis fix](plans/fix-analysis-403-spotify-api-migration.md)

* see agent-first-retrofit, quality review/assessment md

- fix issues with RECOCOBEATS vs RECCOBEATS — see [ReccoBeats wiring plan](plans/reccobeats-wiring.md)

- Fix playlist analysis 403 error — Spotify API February 2026 migration removed `GET /artists` batch endpoint
    * [Fix plan](plans/fix-analysis-403-spotify-api-migration.md)

- Handle Spotify refresh token expiration (6-month limit) — announced June 18, 2026, enforced July 20, 2026 for existing apps
    * Handle `invalid_grant` error on token refresh: discard stored tokens, redirect user to re-sign-in
    * Do not assume refresh tokens are permanent — audit all token storage/refresh logic
    * Test reauthorization flow — users must be able to sign in again smoothly
    * Consider storing authorization timestamp to track expiration proactively

- Clean up repo docs and plans, improve agent guidance for organization
    * Audit `docs/`, `dev-docs/`, and `plans/` for stale/outdated content (superseded plans, old phase docs in `docs/old-docs-backup/`, completed plans in `dev-docs/plans/done/`)
    * Consolidate or archive old phase plans that are no longer actionable
    * Improve `AGENTS.md` and `.github/copilot-instructions.md` with guidance on where to place new plans/docs and how to keep them organized
    * Consider adding a `dev-docs/README.md` or similar to guide agent behavior around documentation

- Audit gitignore vs tracked files
    * Verify `.gitignore` covers all generated/local artifacts (venv, node_modules, caches, IDE, logs)
    * Check that no sensitive or build artifacts are tracked (e.g., `.venv/` contents, `node_modules/`, `__pycache__/`, `.DS_Store`)
    * Review `.github/` directory — security instruction files are tracked but tooling dirs like `.claude/`, `.windsurf/`, `.kilo/` are gitignored — confirm this is intentional
    * Ensure `.skills/` directory is appropriately tracked (it is — these are project skills, not IDE-local config)

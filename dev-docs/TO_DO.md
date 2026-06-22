# To-Do List

## Major Tasks

- [x] Fix medium and low findings from 2026-06-21 bug review — see [fix plan](../docs/exec-plans/completed/2026-06-21-bug-fix-medium-low.md) and [bug assessment](bug-review-2026-06-21-183947.md). 26 of 36 findings implemented across 7 atomic commits (4d0b985, 09212d3, f7a2e84, 2a31bac, 8d11128, 4ea7b50, 003f758) plus the CHANGELOG (dfabf4c). 10 items deferred — see "Deferred from 2026-06-21 medium/low plan" below.

- Fix critical/high bugs from 2026-06-21 audit — see [fix plan](../docs/exec-plans/active/2026-06-21-bug-fix-critical-high.md) and [bug assessment](bug-review-2026-06-21-183947.md). 14 findings: 4 critical (JWT bypass, rate-limit busy spin, hardcoded test data, exposed dev URL), 10 high.

- [x] Fix medium/low bugs from 2026-06-21 audit — see [fix plan](../docs/exec-plans/completed/2026-06-21-bug-fix-medium-low.md) and [bug assessment](bug-review-2026-06-21-183947.md). 26 of 36 findings implemented. 10 deferred (see follow-up section). Coordinates with the export.ts refactor.

## Deferred from 2026-06-21 medium/low plan

Ten items from the [medium/low fix plan](../docs/exec-plans/completed/2026-06-21-bug-fix-medium-low.md) were intentionally deferred during the 2026-06-22 implementation pass. The plan itself documents the original 36 findings and lists these as no-ops or as "apply during the refactor." Group by reason below.

### Blocked on the export.ts refactor plan (awaiting refactor)

The following five items require the [active refactor-export-ts plan](../docs/exec-plans/active/2026-06-21-refactor-export-ts.md) to land first. **Reason for deferral:** applying them in-place on the monolithic `export.ts` would create immediate merge conflicts when the refactor splits the file, and the per-finding plan body explicitly says "apply during the refactor" for each. Do them in the new module structure.

- [ ] **BM-4** — Remove pervasive `any` from `services/export.ts` (buildPlaylistMetadata, buildExportTracks, calculateTotalDurationMs, and 4+ other locations). Apply type tightening in `export-*.ts` after the refactor splits the file.
- [ ] **BM-5** — Remove pervasive `any` from `routes/export.ts` (resolveStepSize, resolveRequestedFormat, resolveIncludeAudioFeatures, 5+ other locations). Use hand-rolled type guards; no Zod in this PR. Apply at new module boundaries after the refactor.
- [ ] **BL-2** — Guard `undefined` playlist in `buildPlaylistMetadata` (`services/export.ts` ~lines 522-528). Change signature to `playlist: Playlist` (non-nullable) and add a call-site test. Apply during the refactor split.
- [ ] **BL-3** — Reconcile `Buffer` detection in `arrayBufferToBase64` (`services/export.ts` ~line 1105-1116). Either leave the inline `typeof Buffer !== 'undefined'` check or extract `isNodeBuffer` to `utils/buffer.ts` for testability. Apply to `export-xlsx-lite.ts` if the refactor moves the function.
- [ ] **BL-10** — Remove misleading playlist-fetch guard in `services/export.ts` (~lines 522-524). The current guard `existingExportData ? undefined : await spotifyService.getPlaylist(playlistId)` is unreachable because `existingExportData` is always set on the retry path. **This is a pre-requirement for the refactor-export-ts plan** — the call must be simplified BEFORE the refactor moves `generatePlaylistExportSlice` to `export-collect.ts`. Add it to the refactor plan's "Pre-requirements" section before opening that PR.

### Lint hardening (deferred to its own PR — out of scope for bug fixes)

- [ ] **BM-11** — Promote `@typescript-eslint/no-explicit-any` from `warn` to `error` in `.eslintrc.json`. **Reason for deferral:** this is linter-config hardening, not a bug fix. Today there are 157 warnings; bulk are in route boundary `body: any` parameters that BM-4/BM-5 are removing. After BM-4/5/BM-6 and the refactor-export-ts plan land, run `rg "@typescript-eslint/no-explicit-any" src/backend/` to get the new count, file a follow-up PR, and add targeted `// eslint-disable-next-line` comments with justification for any remaining `any` usages.

### Cosmetic / non-bug (deferred — no follow-up needed unless revisited)

**Reason for deferral:** these are pure cleanups with no behavioral change. They were skipped to keep the 7 atomic commits focused on the high-impact bug fixes. Revisit if any of them cause future confusion or hit a regression.

- [ ] **FM-2** — Decorate `_update_analysis_ui` with `@mainthread` and drop the three `Clock.schedule_once` wrappers in `_load_analysis_worker` (`src/frontend/ui/backend_playlist_card.py:530-555, 557`). Thread-safety fix; not blocking.
- [ ] **FL-3** — Simplify redundant checks in `_format_backend_api_error` (`src/frontend/services/backend_client.py`). Pure cleanup; no behavioral change.
- [ ] **FL-4** — Avoid re-importing `LabelBase` inside the inner loop in `src/frontend/ui/backend_cache_explorer.py`. Hoist the import to module scope. Cosmetic.
- [ ] **FL-8** — Log diagnostics on `ImportError` in `src/frontend/ui/backend_cache_explorer.py:21-29` and update `backend_status_label.text` in `initialize_backend_client` (line 122) to include the error message. Surface what's missing so dev environments can debug.

### No-op (already covered, nothing to do)

- [x] **BL-1** — local-only-track pagination edge case. **Reason for deferral:** no-op. Existing test `continues paginating by raw Spotify page count when normalized items are filtered out` at `tests/analysis.test.ts:117-151` already covers the case. Marked no-op in the plan.

- [x] **High Priority: Complete main screen refactor** — [completion plan](../docs/exec-plans/completed/superpowers/2026-06-19-main-screen-refactor-completion-plan.md). Completed after cleanup, cancellation branch coverage, and full verification.
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

- [x] Refactor Code and Extract Necessary Sections — completed by [v2 extraction plan](../docs/exec-plans/completed/dev-docs/v2-extraction.md).
    Extracted reusable components, utilities, and logic from the old `src/spotify_playlist_exporter_v2/` codebase into the current frontend/shared structure.

- Clean Up Repository
    Perform a comprehensive cleanup of the repository, removing:
    - Unused files and directories
    - Backup copies and duplicate code
    - Outdated documentation
    - Temporary or cache files that shouldn't be in version control
    - Update stale docs/config references to the removed `src/spotify_playlist_exporter_v2/` package (for example `dev-docs/code-map.md`, `dev-docs/dependency-graph.json`, `.github/CODEOWNERS`, and old distribution/build docs)

- Check for pyright issues and fix them

- start new repo, after cleaning, before widespread release-readiness

- update / check build etc

- decide on default size, see if can better place it

* see [backend analysis routes](backend-analysis-routes.md) and [playlist analysis popup notes](playlist-analysis-popup.md); related implementation plans: [ReccoBeats wiring](../docs/exec-plans/active/2026-06-21-reccobeats-wiring.md), [Spotify 403 analysis fix](../docs/exec-plans/completed/dev-docs/fix-analysis-403-spotify-api-migration.md)
* [fix ReccoBeats pipeline and wire to backend route](../docs/exec-plans/active/2026-06-21-reccobeats-wiring.md)
* [Spotify API enrichment — available data for playlist details](spotify-api-enrichment.md)
* restore reccobeats analysis functionality — see [ReccoBeats wiring plan](../docs/exec-plans/active/2026-06-21-reccobeats-wiring.md) and [Spotify 403 analysis fix](../docs/exec-plans/completed/dev-docs/fix-analysis-403-spotify-api-migration.md)

- [x] Queue-harden backend playlist analysis for large playlists — implemented in the queue hardening commit; see [completed analysis queue hardening plan](../docs/exec-plans/completed/dev-docs/analysis-queue-hardening.md)
    * Worker/queue topology, `ANALYSIS_QUEUE` binding, message type, token refresh strategy, status transitions, idempotency, and retry behavior are implemented.
    * Verified with backend tests/build, Wrangler dry-run, and full `./scripts/verify-all.sh`.

* see agent-first-retrofit, quality review/assessment md

- [x] Fix issues with RECOCOBEATS vs RECCOBEATS — active backend config/docs no longer require either key; see [ReccoBeats wiring plan](../docs/exec-plans/active/2026-06-21-reccobeats-wiring.md)

- [x] Fix playlist analysis 403 error — Spotify API February 2026 migration removed `GET /artists` batch endpoint
    * [Fix plan](../docs/exec-plans/completed/dev-docs/fix-analysis-403-spotify-api-migration.md)

- Refactor the 4 files over 1,000 lines — `src/backend/services/export.ts` (1,220), `src/frontend/screens/backend_main_screen_adapter.py` (1,116), `src/backend/routes/export.ts` (1,045), `src/frontend/screens/main_screen.py` (1,041). Extract focused modules, reduce cohesion, improve testability.

- Handle Spotify refresh token expiration (6-month limit) — announced June 18, 2026, enforced July 20, 2026 for existing apps
    * Handle `invalid_grant` error on token refresh: discard stored tokens, redirect user to re-sign-in
    * Do not assume refresh tokens are permanent — audit all token storage/refresh logic
    * Test reauthorization flow — users must be able to sign in again smoothly
    * Consider storing authorization timestamp to track expiration proactively

- [x] Clean up repo docs and plans, improve agent guidance for organization — completed by [execution plan](../docs/exec-plans/completed/superpowers/2026-06-19-docs-cleanup.md)
    * Audit `docs/`, `dev-docs/`, and `docs/exec-plans/` for stale/outdated content (superseded plans, old phase docs in `docs/old-docs-backup/`, completed plans in `docs/exec-plans/completed/`)
    * Consolidate or archive old phase plans that are no longer actionable
    * Improve `AGENTS.md` and `.github/copilot-instructions.md` with guidance on where to place new plans/docs and how to keep them organized
    * Consider adding a `dev-docs/README.md` or similar to guide agent behavior around documentation

- Audit gitignore vs tracked files
    * Verify `.gitignore` covers all generated/local artifacts (venv, node_modules, caches, IDE, logs)
    * Check that no sensitive or build artifacts are tracked (e.g., `.venv/` contents, `node_modules/`, `__pycache__/`, `.DS_Store`)
    * Review `.github/` directory — security instruction files are tracked but tooling dirs like `.claude/`, `.windsurf/`, `.kilo/` are gitignored — confirm this is intentional
    * Ensure `.skills/` directory is appropriately tracked (it is — these are project skills, not IDE-local config)

- Fix deprecated AsyncImage properties
    * Remove or replace usage of deprecated `allow_stretch` and `keep_ratio` properties on `kivy.uix.image.AsyncImage` objects in frontend UI code to resolve deprecation warnings.

- [x] Fix 403 Forbidden error on backend playlist analysis
    * Playlist analysis returns a 403 Forbidden error during polling of the status route (status transitions to "failed" with HTTP 403). Fixed by deploying updated backend code.

- Fix UI handling of queued analysis jobs and missing ReccoBeats data
    * Frontend logs `[WARNING] [Unknown analysis status] queued` and skips incremental progress tracking. Update frontend analysis polling to recognize `queued` and `processing` states.
    * ReccoBeats audio feature data is not displaying in the UI (only top artists). Investigate if backend is returning ReccoBeats data successfully and verify frontend UI data binding for audio features. Add clarity in backend terminal logs about when requests via Spotify vs. ReccoBeats are being made.

- Add visual progress indicator for playlist analysis
    * The frontend adapter currently doesn't pass an `analysis_task` object into the backend service, so the 0-100% progress updates from the backend are ignored. Wire up a progress bar or text indicator in the UI to display these updates.

- Refactor playlist analysis to use a fan-out queue architecture
    * Currently, we cap the Spotify artist metadata fetches at 40 artists to avoid hitting the hard limit of 50 subrequests per Cloudflare Worker invocation. To analyze all artists in massive playlists, we need to transition from a single synchronous job to a distributed fan-out model (e.g., spawning smaller worker jobs for batches of artists and aggregating the results).

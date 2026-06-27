# Completed Execution Plans

> Plans that have been fully executed or superseded. Kept for historical reference; do not add new active work here.

## Superpowers Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`superpowers/2026-06-19-main-screen-refactor-completion-plan.md`](superpowers/2026-06-19-main-screen-refactor-completion-plan.md) | Main screen refactor completion and verification | 2026-06-19 |
| [`superpowers/2026-06-19-docs-cleanup.md`](superpowers/2026-06-19-docs-cleanup.md) | Documentation cleanup and agent guidance | 2026-06-19 |

## Superseded Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`superseded/2026-06-16-main-screen-refactor.md`](superseded/2026-06-16-main-screen-refactor.md) | Superseded main screen refactor plan | Superseded |
| [`superseded/2026-06-16-main-screen-refactor-V2.md`](superseded/2026-06-16-main-screen-refactor-V2.md) | Superseded main screen refactor V2 plan | Superseded |
| [`superseded/2026-06-16-main-screen-refactor-V3.md`](superseded/2026-06-16-main-screen-refactor-V3.md) | Superseded by 2026-06-19 completion plan | Superseded |
| [`superseded/2026-06-16-main-screen-refactor-review.md`](superseded/2026-06-16-main-screen-refactor-review.md) | Main screen refactor review artifact | Superseded |
| [`superseded/2026-06-21-bug-review-medium-low-fixes.md`](superseded/2026-06-21-bug-review-medium-low-fixes.md) | Superseded by [`2026-06-21-bug-fix-medium-low.md`](2026-06-21-bug-fix-medium-low.md) (used non-existent test paths and unsupported `logger` syntax) | Superseded |

## Bug Fix Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`2026-06-21-bug-fix-critical-high.md`](2026-06-21-bug-fix-critical-high.md) | Critical and high severity bug fixes from 2026-06-21 audit (BT-1–8, FT-1–6): JWT bypass, Retry-After busy spin, OAuth redirect validation, silent catch blocks, queue consumer ack, PII in KV, context type loss, hardcoded test data, exposed dev URL, playlist track crash, filename corruption, cache path dedup, dead cache stats | 2026-06-24 |
| [`2026-06-21-bug-fix-medium-low.md`](2026-06-21-bug-fix-medium-low.md) | Medium and low severity bug fixes from 2026-06-21 audit (BM-1–10, BL-1–10, FM-1–6, FL-1–9): type safety, auth hardening, stale-snapshot writes, concurrent refresh dedup, error classification, cache clearing, thread safety, import diagnostics. BM-11 deferred to lint-hardening follow-up. | 2026-06-24 |
| [`2026-06-26-analysis-popup-e2e.md`](2026-06-26-analysis-popup-e2e.md) | End-to-end playlist analysis popup wiring: chunked ReccoBeats audio feature track fetching to prevent HTTP 414 error, rendered audio features averages in the popup UI, updated loading status message, and audited legacy compatibility methods. | 2026-06-26 |

## Refactor Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`2026-06-21-refactor-export-ts.md`](2026-06-21-refactor-export-ts.md) | Split `services/export.ts` (1,186 lines) into 12 focused modules (`export-types`, `export-cursor`, `export-job-state`, `export-assemble`, `export-collect`, `export-assembly`, `export-xlsx`, `export-xlsx-lite`, `export-csv`, `export-json`, `export-tracks`, `export-format-helpers`). `ExportService` is now a thin facade; 8 new unit test files added; no API or output format changes. | 2026-06-24 |
| [`2026-06-24-refactor-routes-export-ts.md`](2026-06-24-refactor-routes-export-ts.md) | Split `routes/export.ts` (1,050 lines) into a Hono sub-app composition at `routes/export/` with helper modules under `routes/export/helpers/` (types, cache-keys, format, errors, request-id, file-bytes). Facade preserved; no public API changes; ESLint and architecture test expanded; 3 new unit test files added. | 2026-06-24 |
| [`2026-06-24-refactor-backend-main-screen-adapter.md`](2026-06-24-refactor-backend-main-screen-adapter.md) | Split `backend_main_screen_adapter.py` (~1,100 lines) into a facade composing 9 mixin modules under `adapter_mixins/` (core, playlists, tracks, analysis, exports, exports_resumable, exports_download, jobs, utilities). No caller changes; all public names preserved. Fixed `get_playlist_tracks` copy-paste error message. | 2026-06-24 |
| [`2026-06-24-refactor-main-screen.md`](2026-06-24-refactor-main-screen.md) | Split `main_screen.py` (1,041 lines) into coordinator (494 lines) plus `main_screen_ui.py`, `main_screen_selection.py`, and `main_screen_search_sort_ui.py`. Property facades preserve `BackendMainScreen` compatibility; 3 new unit test files added. | 2026-06-24 |
| [`2026-06-26-split-xlsx-render-modes.md`](2026-06-26-split-xlsx-render-modes.md) | Split `buildExportFileKey` conflated `mode` parameter into dedicated functions (`buildXlsxVariantKey`, `buildPrebuiltFormatKey`) to separate XLSX render variants from prebuilt format slots. | 2026-06-27 |

## Infrastructure Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`2026-06-21-repo-organization-guardrails.md`](2026-06-21-repo-organization-guardrails.md) | Consolidated plan/docs placement, removed duplicate agent config, added CLAUDE.md and structural guardrails. | 2026-06-21 |
| [`2026-06-22-backend-deployment-tracking.md`](2026-06-22-backend-deployment-tracking.md) | Added live backend deployment metadata, metadata-aware deploy wrappers, status checks, and deployment docs. | 2026-06-22 |
| [`2026-06-26-docs-taxonomy-migration.md`](2026-06-26-docs-taxonomy-migration.md) | Split user-facing docs from developer and agent-facing docs, updated guidance, and strengthened structure guardrails. | 2026-06-26 |
| [`2026-06-27-basedpyright-prepush-hook.md`](2026-06-27-basedpyright-prepush-hook.md) | Added `basedpyright` as a pre-push hook in `.pre-commit-config.yaml` (targets `src/frontend` + `src/shared` at `--level error`), added it to dev dependencies, configured `[tool.basedpyright]` excludes for backup/build dirs, removed 6 redundant `reportAttributeAccessIssue` suppressions, and documented the type-check command in AGENTS/CLAUDE. | 2026-06-27 |

## Dev Docs Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`dev-docs/agent-first-retrofit.md`](dev-docs/agent-first-retrofit.md) | Agent-first repository retrofit | 2026-06 |
| [`dev-docs/analysis-queue-hardening.md`](dev-docs/analysis-queue-hardening.md) | Queue-backed playlist analysis hardening | 2026-06-19 |
| [`dev-docs/ci-fix-plan.md`](dev-docs/ci-fix-plan.md) | CI workflow fixes | 2026-06 |
| [`dev-docs/dead-code-cleanup.md`](dev-docs/dead-code-cleanup.md) | Dead code cleanup | 2026-06 |
| [`dev-docs/fix-analysis-403-spotify-api-migration.md`](dev-docs/fix-analysis-403-spotify-api-migration.md) | Spotify artist endpoint migration fix | 2026-06 |
| [`dev-docs/v2-extraction.md`](dev-docs/v2-extraction.md) | v2 extraction plan | 2026-06 |

## Legacy Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`legacy/backend-selector-gui-patch-plan.md`](legacy/backend-selector-gui-patch-plan.md) | Backend selector GUI patch | Historical |
| [`legacy/phase-1-cloudflare-backend.md`](legacy/phase-1-cloudflare-backend.md) | Cloudflare backend phase plan | Historical |
| [`legacy/phase-1-files.md`](legacy/phase-1-files.md) | Phase 1 file list | Historical |
| [`legacy/phase-2-files.md`](legacy/phase-2-files.md) | Phase 2 file list | Historical |
| [`legacy/phase-2-frontend-cloudflare-integration.md`](legacy/phase-2-frontend-cloudflare-integration.md) | Frontend/Cloudflare integration phase plan | Historical |
| [`legacy/phase-2-real-integration-testing.md`](legacy/phase-2-real-integration-testing.md) | Real integration testing phase plan | Historical |
| [`legacy/phase-3-frontend-executable-build-spec-update.md`](legacy/phase-3-frontend-executable-build-spec-update.md) | Frontend executable build spec update | Historical |
| [`legacy/phase-3-production-deployment.md`](legacy/phase-3-production-deployment.md) | Production deployment phase plan | Historical |
| [`legacy/phase-4-testing-verification.md`](legacy/phase-4-testing-verification.md) | Testing verification phase plan | Historical |
| [`legacy/resumable-export-cursor-persistence-plan.md`](legacy/resumable-export-cursor-persistence-plan.md) | Resumable export cursor persistence | Historical |
| [`legacy/search_filter_plan.md`](legacy/search_filter_plan.md) | Search/filter plan | Historical |

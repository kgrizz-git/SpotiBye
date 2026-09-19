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
| [`2026-08-05-cloudflare-dev-url-config.md`](2026-08-05-cloudflare-dev-url-config.md) | Removed the shipped Cloudflare Dev fallback and automatic localhost connection. The selector now starts unconfigured when necessary, preserves explicit saved/custom selections, and displays cloud presets only when configured. | 2026-08-05 |
| [`2026-06-21-bug-fix-critical-high.md`](2026-06-21-bug-fix-critical-high.md) | Critical and high severity bug fixes from 2026-06-21 audit (BT-1–8, FT-1–6): JWT bypass, Retry-After busy spin, OAuth redirect validation, silent catch blocks, queue consumer ack, PII in KV, context type loss, hardcoded test data, exposed dev URL, playlist track crash, filename corruption, cache path dedup, dead cache stats | 2026-06-24 |
| [`2026-06-21-bug-fix-medium-low.md`](2026-06-21-bug-fix-medium-low.md) | Medium and low severity bug fixes from 2026-06-21 audit (BM-1–10, BL-1–10, FM-1–6, FL-1–9): type safety, auth hardening, stale-snapshot writes, concurrent refresh dedup, error classification, cache clearing, thread safety, import diagnostics. BM-11 deferred to lint-hardening follow-up. | 2026-06-24 |
| [`2026-06-26-analysis-popup-e2e.md`](2026-06-26-analysis-popup-e2e.md) | End-to-end playlist analysis popup wiring: chunked ReccoBeats audio feature track fetching to prevent HTTP 414 error, rendered audio features averages in the popup UI, updated loading status message, and audited legacy compatibility methods. | 2026-06-26 |
| [`2026-06-28-fix-ci-type-errors.md`](2026-06-28-fix-ci-type-errors.md) | Fixed 4 TypeScript compilation errors from Zod v4 upgrade (CI Run #62): structural-type fix for `formatZodMessage` in `z-validator.ts` (the plan's v3-style `import type { ZodError }` recommendation was wrong — `@hono/zod-validator` returns the internal `$ZodError` base, not the public extended `ZodError`), inline-wrapper refactor for `getPlaylistItemsHandler` in `routes/spotify.ts`, and `z.any().optional()` declarations on `ExportBatchChunkBodySchema`. Added 4 `formatZodMessage` path-formatting subtests. Added pre-push `tsc --noEmit` hook and `vitest.config.ts` `typecheck.enabled: true` to prevent recurrence. | 2026-06-29 |
| [`2026-07-05-backend-url-defaulting-fix.md`](2026-07-05-backend-url-defaulting-fix.md) | Fixed the "Cloudflare Dev" preset in the startup backend selector being a no-op and silently losing the saved preset choice across relaunches — both caused by `BACKEND_PRESETS["Cloudflare Dev"]` aliasing the same URL as `"Localhost"` after FT-2's shipped-binary safety default change. Added a dedicated `DEV_BACKEND_URL` constant (override via `SPOTIBYE_DEV_BACKEND_URL`) so the two concepts are decoupled. | 2026-07-06 |
| [`2026-07-06-spotify-token-expiration-handling.md`](2026-07-06-spotify-token-expiration-handling.md) | Handle Spotify refresh token expiration by parsing `invalid_grant` errors, responding with `AUTH_REQUIRED` code, cleaning up stale KV sessions, preventing queue retries on auth failure, validating cached tokens on startup via `GET /auth/me`, and wiping persisted cache when tokens expire permanently. | 2026-07-06 |

## Feature Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`2026-07-07-reccobeats-enrichment-integration.md`](2026-07-07-reccobeats-enrichment-integration.md) | Full ReccoBeats enrichment for playlist analysis: all 9 audio features + key/mode aggregation, ReccoBeats track-metadata fetch (ISRC/popularity), best-effort `errors[]` + `schema_version` with stale-result purge/re-enqueue, a shared 24h raw-enrichment KV cache, an expanded analysis popup UI (mood labels, key/mode, partial-failure banner), and OpenAPI/docs reconciliation (removed unimplemented recommendation/BPM fields, documented the status/results endpoints). | 2026-07-09 |
| [`2026-07-09-reccobeats-egress-diagnosis-and-frontend-fetch.md`](2026-07-09-reccobeats-egress-diagnosis-and-frontend-fetch.md) | Diagnosed ReccoBeats playlist-analysis failures: ruled out universal Cloudflare/IPv6 egress blocking for the known-good sample, identified ReccoBeats' 40-ID request cap as the concrete failure behind 50-ID batches, reduced backend batches to 30, added stale ReccoBeats-error retry behavior, exposed backend error messages in the popup, added body-preview logging, and deferred frontend-direct fetch as an optional user-choice enhancement. | 2026-07-10 |

## Refactor Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`2026-06-21-refactor-export-ts.md`](2026-06-21-refactor-export-ts.md) | Split `services/export.ts` (1,186 lines) into 12 focused modules (`export-types`, `export-cursor`, `export-job-state`, `export-assemble`, `export-collect`, `export-assembly`, `export-xlsx`, `export-xlsx-lite`, `export-csv`, `export-json`, `export-tracks`, `export-format-helpers`). `ExportService` is now a thin facade; 8 new unit test files added; no API or output format changes. | 2026-06-24 |
| [`2026-06-24-refactor-routes-export-ts.md`](2026-06-24-refactor-routes-export-ts.md) | Split `routes/export.ts` (1,050 lines) into a Hono sub-app composition at `routes/export/` with helper modules under `routes/export/helpers/` (types, cache-keys, format, errors, request-id, file-bytes). Facade preserved; no public API changes; ESLint and architecture test expanded; 3 new unit test files added. | 2026-06-24 |
| [`2026-06-24-refactor-backend-main-screen-adapter.md`](2026-06-24-refactor-backend-main-screen-adapter.md) | Split `backend_main_screen_adapter.py` (~1,100 lines) into a facade composing 9 mixin modules under `adapter_mixins/` (core, playlists, tracks, analysis, exports, exports_resumable, exports_download, jobs, utilities). No caller changes; all public names preserved. Fixed `get_playlist_tracks` copy-paste error message. | 2026-06-24 |
| [`2026-06-24-refactor-main-screen.md`](2026-06-24-refactor-main-screen.md) | Split `main_screen.py` (1,041 lines) into coordinator (494 lines) plus `main_screen_ui.py`, `main_screen_selection.py`, and `main_screen_search_sort_ui.py`. Property facades preserve `BackendMainScreen` compatibility; 3 new unit test files added. | 2026-06-24 |
| [`2026-06-26-split-xlsx-render-modes.md`](2026-06-26-split-xlsx-render-modes.md) | Split `buildExportFileKey` conflated `mode` parameter into dedicated functions (`buildXlsxVariantKey`, `buildPrebuiltFormatKey`) to separate XLSX render variants from prebuilt format slots. | 2026-06-27 |
| [`2026-07-09-refactor-backend-playlist-card.md`](2026-07-09-refactor-backend-playlist-card.md) | Split `src/frontend/ui/backend_playlist_card.py` into a thin orchestrator plus five focused helper modules (`utils`, `ui`, `interaction`, `analysis_popup`, `tracks_popup`), removed its file-length exemption, updated architecture/dev-docs metadata, and verified frontend tests plus manual GUI behavior. | 2026-07-09 |

## Infrastructure Plans

| Plan | Description | Completed |
|------|-------------|-----------|
| [`2026-06-21-repo-organization-guardrails.md`](2026-06-21-repo-organization-guardrails.md) | Consolidated plan/docs placement, removed duplicate agent config, added CLAUDE.md and structural guardrails. | 2026-06-21 |
| [`2026-06-22-backend-deployment-tracking.md`](2026-06-22-backend-deployment-tracking.md) | Added live backend deployment metadata, metadata-aware deploy wrappers, status checks, and deployment docs. | 2026-06-22 |
| [`2026-06-26-docs-taxonomy-migration.md`](2026-06-26-docs-taxonomy-migration.md) | Split user-facing docs from developer and agent-facing docs, updated guidance, and strengthened structure guardrails. | 2026-06-26 |
| [`2026-06-27-basedpyright-prepush-hook.md`](2026-06-27-basedpyright-prepush-hook.md) | Added `basedpyright` as a pre-push hook in `.pre-commit-config.yaml` (targets `src/frontend` + `src/shared` at `--level error`), added it to dev dependencies, configured `[tool.basedpyright]` excludes for backup/build dirs, removed 6 redundant `reportAttributeAccessIssue` suppressions, and documented the type-check command in AGENTS/CLAUDE. | 2026-06-27 |
| [`2026-06-28-bump-ci-node-24.md`](2026-06-28-bump-ci-node-24.md) | Bumped CI Node version from past-EOL Node 20 to Node 24 LTS. Switched all 6 `actions/setup-node` calls to `node-version-file: ".nvmrc"` so `.nvmrc` is the single source of truth (next bump is one file). Added `.nvmrc` with `24`, bumped `@types/node` to `^24.0.0` in `src/backend/package.json`, regenerated lockfile under Node 24, added Node-version one-liners to `AGENTS.md` and `CLAUDE.md`. | 2026-06-29 |
| [`2026-06-27-add-security-tooling.md`](2026-06-27-add-security-tooling.md) | Added Zod boundary validation to the TypeScript backend, integrated OSV-Scanner (CI + pre-push), hardened Bandit (blocking CI + full-tree pre-push), bumped Dependabot to weekly, and updated SECURITY.md / CHANGELOG. | 2026-06-27 |
| [`2026-07-06-align-eslint-typescript-versions.md`](2026-07-06-align-eslint-typescript-versions.md) | Aligned `.pre-commit-config.yaml` eslint hook's `additional_dependencies` with `src/backend/package-lock.json` resolved versions (ESLint `8.57.1`, `@typescript-eslint/*@8.61.0`) to match workspace resolutions and eliminate lint/check environment divergence. | 2026-07-06 |
| [`2026-08-05-sonarcloud-issues.md`](2026-08-05-sonarcloud-issues.md) | SonarCloud remediation: fixed dead-code bug in `check-dependencies.py`, suppressed 4 loopback-HTTP false positives (NOSONAR), hardened CI/CD workflow permissions (build.yml, deploy-production.yml), extracted 4 nested ternaries to if/else blocks, migrated 41 logger f-string calls to lazy `%s`/`exception()`, added tests for error middleware HTTPException branch, export download paths, and `check-dependencies.py`. | 2026-08-05 |
| [`2026-07-09-split-dependabot-dev-deps-pr20.md`](2026-07-09-split-dependabot-dev-deps-pr20.md) | Dependabot dev-dependency bundle split (PR #20 framing from the pre-migration repo; PR never existed here). Goal achieved piecemeal: safe bumps via PRs #2, #3, #7, ESLint v10 flat-config migration, Node 24 LTS. Residuals (npm overrides watch, `index.ts` wiring decision) kept as plain TO_DO one-liners. | 2026-09-19 |

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

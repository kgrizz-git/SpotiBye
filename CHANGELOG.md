# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Added
- Playlist analysis popups now show live progress with a progress bar and status text while backend analysis runs, including bounded activity feedback when Cloudflare KV status reads are stale.
- Backend playlist analysis status now uses a Durable Object for live progress reads, while completed analysis results remain in KV.
- Added a file-length pre-commit hook (`scripts/check_file_lengths.py`) to warn when Python or Markdown files exceed line count thresholds (700 lines for code, 1000 lines for tests, 300 lines for docs), with configurable glob exemptions in `scripts/file-length-exemptions.json`. Initially runs in `--warn` mode for a 14-day transition period before enforcement.
- Automatic re-authentication prompt when Spotify refresh tokens expire (handles Spotify's June 2026 6-month refresh token expiration policy)
- Added Zod request and boundary validation to the TypeScript backend: invalid inputs return the app's `{ error: { code, message } }` envelope. Existing route-specific codes are preserved where they already existed (`MISSING_REDIRECT_URI`, `INVALID_PLAYLISTS`); newly validated path and query parameters use `VALIDATION_ERROR`. KV sessions, queue messages, and Worker env bindings are schema-validated at boundaries.
- Integrated OSV-Scanner for unified Python + Node.js dependency vulnerability scanning in CI and as a pre-push hook; Bandit now enforces the project `pyproject.toml` policy on pre-push (full tree) and in CI (blocking).
- Bumped Dependabot version-update cadence from monthly to weekly for all ecosystems.
- Expanded the playlist analysis popup's "Audio Features" section from 5 to all 9 ReccoBeats audio features (adds instrumentalness, liveness, speechiness, loudness), plus a musical key/mode row (e.g. "C major") when at least 2 tracks have a valid key/mode. Valence is now shown as a human-readable mood label (Melancholic/Somber/Neutral/Cheerful/Euphoric) instead of a raw percentage. Added a "ReccoBeats Metadata" section (ISRC coverage count, popularity range) from a new `GET /v1/track` fetch, and a partial-failure banner listing which enrichment sources (Spotify artists, ReccoBeats audio features, ReccoBeats track metadata) failed for a given analysis, since ReccoBeats enrichment is always best-effort and analysis still completes without it.
- Backend analysis results now include `errors` (always present; empty on full success) and `schema_version`, and a 24h raw-ReccoBeats-enrichment cache shared across users for the same playlist (namespaced by playlist only, not user, since the data is playlist-derived) to avoid duplicate fetches. Cached analysis results whose `schema_version` is missing or older than the server's are treated as stale: `GET .../results` purges them and returns 404, and a subsequent `POST` enqueues a fresh job automatically.

### Changed
- Reconciled `docs/openapi.yaml` and `docs/api-examples.md` with the real analysis API: documented the previously-undocumented `GET /analysis/playlist/{id}/status` and `GET /analysis/playlist/{id}/results` endpoints, removed schema fields for never-implemented features (`duration_minutes`, `average_bpm`, `bpm_distribution`, `energy_score`, `recommendations`/`SimilarPlaylist`, `include_recommendations`), and added the real response shape (`overview`, `artists`, `genre_distribution`, `audio_features` with `key_mode_distribution`, `insights`, `reccobeats_metadata`, `errors`, `schema_version`).
- Backend now validates path parameters (`:id`, `:jobId`) and Spotify pagination query params (`limit`, `offset`), returning HTTP 400 with `VALIDATION_ERROR` when they are missing or out of range. Previously these were not schema-checked at the HTTP boundary.
- Refactored `buildExportFileKey` to split its conflated `mode` parameter into dedicated `buildXlsxVariantKey` (for XLSX render variants `rich` and `lite`) and `buildPrebuiltFormatKey` (for prebuilt format slots like `csv`) functions. Cache key strings are unchanged; no in-flight cache entries are invalidated. Avoided one redundant cache write for the `default` XLSX render variant during download fallback regeneration.
- Changed playlist analysis loading text from "Retrieving analysis from ReccoBeats API..." to "Analyzing playlist..." to accurately reflect that the analysis is Spotify-backed.
- Refactored `main_screen.py` (1,041 lines) into a coordinator (494 lines) plus `main_screen_ui.py` (`MainScreenUIBuilder`), `main_screen_selection.py` (`SelectionManager`), and `main_screen_search_sort_ui.py` (`SearchSortUIHandler`). Property facades preserve `BackendMainScreen` compatibility; no caller changes required. Added unit tests for selection, search/sort, and facade round-trips.
- Refactored `backend_main_screen_adapter.py` (~1,100 lines) into a facade composing 9 mixin modules under `adapter_mixins/` (core, playlists, tracks, analysis, exports, exports_resumable, exports_download, jobs, utilities). All public names (`BackendMainScreenAdapter`, `create_backend_adapter`, `get_reccobeats_api`, `create_spotify_client_with_refresh`) are preserved at the same import path; no caller changes required.
- Fixed a copy-paste error message in `get_playlist_tracks` that emitted `"Export generation failed"` instead of the correct `"Failed to load playlist tracks"`.
- Refactored `routes/export.ts` (1,050 lines) into a Hono sub-app composition at `routes/export/` with helper modules under `routes/export/helpers/` (types, cache-keys, format, errors, request-id, file-bytes). The public `exportRoutes` export is preserved; no call-site or test-assertion changes. The local `ResumableExportJobStatus` alias is removed in favor of the service-layer `ResumableExportJobState`; both name and shape are now sourced from `services/export-types.ts`.
- Promoted `@typescript-eslint/no-explicit-any` from `warn` to `error` in `.eslintrc.json`; added `warn` override for test files. All `any` usages in non-test backend source files are now either properly typed (`ApiResponse<T = unknown>`, `ExportTrack` index signature, `get<ExportData[]>`, `ResumableExportConflictError` cast) or carry a justified `eslint-disable-next-line` comment (raw JSON boundary in `normalizePlaylistItemsResponse`, ExcelJS table type gap, backward-compat KV reads).
- Added `[key: string]: string | number` index signature to `ExportTrack` so dynamic header-keyed access in CSV, XLSX, and lite-XLSX renderers no longer requires unsafe casts.
- Refactored `services/export.ts` (1,186 lines) into focused modules: `export-types`, `export-cursor`, `export-job-state`, `export-assemble`, `export-collect`, `export-assembly`, `export-xlsx`, `export-xlsx-lite`, `export-csv`, `export-json`, `export-tracks`, `export-format-helpers`. The `ExportService` class is now a thin facade with static and instance delegating methods — no change to the public API, call sites, or output formats. Added unit tests for all extracted pure functions.

### Fixed
- Playlist analysis now has a manual "Retry enrichment" action that clears stale analysis and raw ReccoBeats enrichment before re-running, while ReccoBeats coverage-only warnings no longer trigger full automatic reanalysis loops. Known limitation: complete omission/completeness status for permanent ReccoBeats misses arrives with the follow-up per-track cache work.
- Playlist analysis now preserves Spotify genre data from artists that resolve successfully even when another artist metadata lookup returns 404, filters blank/null top-artist names, and shows a ReccoBeats coverage note when audio features are available for only part of a playlist.
- Playlist analysis partial-data banners now simplify nested Spotify API errors, so artist-genre 404s show a readable message instead of raw JSON.
- Playlist analysis now forces a fresh backend analysis when cached results contain ReccoBeats partial-failure errors, so playlists analyzed before an enrichment fix can retry instead of permanently showing stale missing-data banners.
- Reduced ReccoBeats playlist-analysis request batches below the upstream 40-ID cap so larger playlists no longer lose enrichment because 50-ID batches are rejected.
- Playlist analysis partial-data banners now include the backend's diagnostic error message, making ReccoBeats failures such as rate limits, timeouts, and invalid response shapes visible in the popup.
- Backend now parses Spotify `invalid_grant` errors and responds with `AUTH_REQUIRED` instead of a generic 401
- Stale KV sessions are deleted immediately on `invalid_grant` to prevent repeated auth failures
- Queue analysis jobs now fail permanently on auth errors instead of retrying up to the retry limit
- Frontend startup no longer accepts a locally valid JWT without verifying it against the backend
- `handle_session_expired` now clears the persisted token file, preventing infinite auto-login loops on next launch
- Fixed the "Cloudflare Dev" preset in the startup backend selector being a no-op and silently losing the saved preset choice across relaunches — both were caused by `BACKEND_PRESETS["Cloudflare Dev"]` aliasing the same URL as `"Localhost"` after FT-2's shipped-binary safety default change. Added a dedicated `DEV_BACKEND_URL` constant (override via `SPOTIBYE_DEV_BACKEND_URL`) so the two concepts are decoupled.
- Bumped minimum dependency versions to clear OSV-Scanner findings: Python (`spotipy>=2.25.2`, `pillow>=12.2.0`, `idna>=3.15`, `pygments>=2.20.0`) and Node.js dev-toolchain overrides (`undici`, `ws`, `js-yaml`).
- Fixed OSV-Scanner pre-push hook configuration: use the native `osv-scanner` hook (pre-commit bootstraps Go) instead of the unavailable `osv-scanner-docker` id at `v2.3.5`, and removed invalid `--skip-dirs` flags (OSV honours `.gitignore` by default).
- Fixed backend ReccoBeats audio features fetching by batching track IDs (50 per batch, concurrency 3) to prevent HTTP 414 URL too long errors on playlists with 300+ tracks.
- Restored backend ReccoBeats audio-feature enrichment using the verified public no-auth API and removed stale ReccoBeats secret requirements from active backend config/docs.
- Fixed backend playlist analysis failures caused by Spotify rejecting the removed batch artist endpoint by fetching artist metadata individually and continuing without genre data when artist enrichment fails.
- Fixed export cancellation state so the frontend records active backend exports and can mark them cancelled during user cancellation or app shutdown.
- Fixed filename extension handling in the export screen so incremental suffixes (e.g., _2) work correctly for all formats (CSV, JSON), not just Excel (.xlsx).
- Fixed JWT expiration bypass where a forged token with `exp: 0` was accepted because the falsy check skipped expiration validation.
- Fixed Spotify rate-limit busy spin by parsing `Retry-After` as both integer seconds and HTTP-date format, with a 1-second fallback.
- Fixed playlist tracks fetch to no longer crash with `AttributeError` when the backend returns a list-shaped payload.
- Fixed filename suffix increment so digit-ending basenames (e.g. `song_14.xlsx`) get a safe `_2` suffix instead of being silently corrupted.
- Fixed OAuth `redirect_uri` open redirect by validating against a configured `ALLOWED_REDIRECT_URIS` allowlist (fail-closed when unset).
- Fixed OAuth error handling so silent `catch {}` blocks log the underlying error for OAuth init, callback state parse fallback, logout, and user info.
- Stopped storing raw PII (`email`, `country`, etc.) in the KV session record under the unread `spotify_data` field.
- Fixed queue consumer infinite-retry loop when `markFailed` throws by wrapping the call in its own try/catch and always acking the message.
- Preserved non-429 Spotify error response bodies in thrown error messages so diagnostic details are not lost.
- Removed hardcoded ReccoBeats test data (`cached_track_1`/`cached_track_2`) that returned fabricated audio features in production.
- Changed default `BACKEND_URL` from the developer's exposed Cloudflare Worker to `http://localhost:8787`; the worker URL remains available via the `SPOTIBYE_BACKEND_URL` env var override.
- Deduplicated cache file path hashing in `BackendCacheManager` by extracting a private `_cache_file_path` helper used by all read/write/clear methods.
- Removed dead `_get_basic_cache_stats` method that always reported zero items because of an incorrect format check.
- Fixed backend token rotation drop: `SpotifyAuthService.refreshAccessToken` now returns the rotated `refresh_token` from Spotify and the route persists it back to KV; previously the rotated token was silently lost.
- Fixed analysis-job stale-snapshot progress writes: progress, completion, and retry writes now re-read the latest KV status before merging, so intermediate progress callbacks are no longer clobbered. Added `updated_at` to every status write.
- Fixed JSON.parse on KV session data being unprotected — both the auth middleware and refresh route now use a `safeParseSession` helper that validates the schema (user_id, access_token, expires_at) and treats malformed data as a 401.
- Fixed concurrent token refresh issuing multiple `refreshAccessToken` calls for the same session by deduplicating in-flight refreshes in the auth middleware.
- Fixed analysis-job KV replication race by raising the post-write settle window to 30s and emitting a `console.warn` with the job id and age when the wait triggers.
- Fixed `OAuth callback` catch block losing diagnostic context by classifying the error and returning a structured error code (`OAUTH_TOKEN_EXPIRED`, `OAUTH_BAD_REQUEST`, or fallback `OAUTH_CALLBACK_FAILED` with the reason in `details`).
- Fixed `SpotifyAuthService` accepting empty `clientId`/`clientSecret` and silently producing broken requests — the constructor now throws if either credential is empty.
- Fixed health-check response being inconsistent with the rest of the API by wrapping it in a `data` envelope (`{ data: { status, service, timestamp } }`).
- Fixed duplicate `token` field in the refresh-token response; only the canonical `access_token` and `token_type` are now returned.
- Fixed `errorHandler` silently mapping 3rd-party errors (e.g., `pg`/`mongoose` `ValidationError`) to the wrong HTTP status by adding a required discriminator (`code` or `statusCode`) to each named-error branch.
- Fixed playlist items with a missing `id` or `name` crashing the entire `/me/playlists` response — malformed items are now dropped with a `console.warn` instead of throwing.
- Fixed `is_valid_backend_url` accepting obviously-invalid URLs like `https://x` or `http:///path`; it now parses the URL and requires a non-empty hostname containing a dot or equal to `localhost`.
- Removed residual local `RefreshedToken` interface and `as RefreshedToken` cast from `analysis-job.ts`; `refreshAccessToken` already returns `AuthTokenResponse` so no cast is needed.
- Removed `body: any` parameters from `resolveStepSize`, `resolveRequestedFormat`, `resolveIncludeAudioFeatures`, and `generateFileBytes` in `routes/export.ts`; parameters are now typed as `Record<string, unknown>` or `ExportData[]`.
- Fixed `_update_analysis_ui` in `BackendPlaylistCard` being called from a background thread without main-thread dispatch; it is now decorated with `@mainthread` and the three `Clock.schedule_once` wrappers at call sites are removed.
- Removed redundant `isinstance(details_payload, dict)` guards in `_format_backend_api_error`; `details_payload` is always a `dict` at that point.
- Fixed `LabelBase` being re-imported on every iteration of the system-fonts fallback loop in `_setup_fonts`; the import is now done once outside the loop.
- Fixed `ImportError` in `backend_cache_explorer.py` losing the diagnostic message; `as exc` is now captured, logged with the message, and stored in `_BACKEND_IMPORT_ERROR` so `initialize_backend_client` can surface it in the status label.
- Fixed `download_export` accepting an unused `export_id` parameter in both `BackendClient` and `BackendMainScreenAdapter`; the parameter was dropped from the signatures and call sites.
- Fixed tkinter screen-size detection leaking a hidden root window on exception by using try/finally to always call `root.destroy()`.
- Fixed `clear_all_cache` showing a "Cache Cleared" popup without actually clearing the cache — the function now delegates to `screen.backend_adapter.cache_manager.clear_cache(None)`.
- Fixed default `clear_cache()` glob (`*.json`) deleting the user's auth token and backend-selection config; the default pattern is now `{env_hash}_*.json` (env-hash-prefixed data files only). Auth tokens and selection are preserved.

### Added
- Added live backend deployment metadata to `/health`, metadata-aware Wrangler deploy wrappers, and a `scripts/backend-deploy-status.sh` helper so agents and developers can tell whether backend changes need deployment.
- `BackendCacheManager.clear_file(filename)` and `clear_cache_glob(pattern)` helpers that automatically apply the env-hash prefix; these replace the previous pattern of passing raw globs to `clear_cache`.
- Backend tests: `tests/analysis-job.test.ts` (3 cases for stale-snapshot prevention), `tests/auth-middleware.test.ts` (concurrent refresh deduplication), `tests/error-middleware.test.ts` (9 cases for error discriminator strengthening), `tests/spotify-validation.test.ts` (10 cases for `parsePlaylistItems` and typed wrappers).
- Frontend tests: `tests/test_main_screen_logout.py` (7 cases for download signature and missing-logout logging), `tests/test_main_screen_cache.py` (7 cases for env-hash-scoped cache clearing), 11 new `TestIsValidBackendUrl` cases in `test_configuration.py`.
- Test helper: `src/backend/tests/helpers/kv.ts` (`kvNamespace` + `envWithKv` factories) shared by `analysis-queue.test.ts`, `auth-middleware.test.ts`, and `analysis-job.test.ts`.

### Changed
- Hardened backend playlist analysis by queueing large analysis jobs with retry-safe status updates instead of relying on request-scoped background work.
- Refactored `MainScreen` to extract pure logic (filenames, sort/filter) and stabilize job state, reducing technical debt and improving testability.
- Hardened backend npm dependencies by upgrading Wrangler, Workers types, and TypeScript ESLint, replacing SheetJS `xlsx` usage with ExcelJS, and overriding vulnerable transitive `esbuild` and `uuid` releases until upstream packages publish patched dependency ranges.
- Optimized GitHub Actions workflows to reduce redundant CI runs by 40-60% while maintaining full test coverage on protected branches
  - CI now runs only on main/develop/WIP branches instead of all branches
  - Security scans run only on PRs (not duplicate push events) with weekly baseline scans
  - Language-specific security jobs (Bandit, npm audit) skip when irrelevant files change
  - Deployment workflows skip redundant test runs when CI already validated the code
  - Streamlined dependency review to single job, removing duplicates
- `BackendClient.health_check` now catches `Exception` (in addition to `BackendAPIError`) and returns a documented three-state `status` value: `healthy` | `unhealthy` | `error`. Callers should branch on `result.get("status") == "healthy"`.
- Renamed the custom `TimeoutError` to `NetworkTimeoutError` to avoid shadowing the Python builtin.
- `BackendClient.download_export`, `download_batch_export`, and `download_export_job` now share a single `_download_file(endpoint, timeout, failure_prefix)` helper for auth/trace/error-parse logic.
- `export-tracks.ts` functions (`buildPlaylistMetadata`, `calculateTotalDurationMs`, `mapTrackForExport`, `buildExportTracks`, `loadAudioFeaturesMap`) are now fully typed — all `any` parameters replaced with `SpotifyPlaylist | undefined`, `SpotifyPlaylistTrackItem[]`, `SpotifyTrack`, `SpotifyAudioFeatures | null | undefined`, and `Map<string, SpotifyAudioFeatures>`. Added `followers?: { total: number }` to `SpotifyPlaylist` (present on `GET /playlists/{id}` responses).
- `perform_logout` now logs an error and returns gracefully when the running App lacks a `logout` method (instead of silently no-oping). Dev/test app mocks are no longer broken.
- `Optional[callable]` annotations in `BackendMainScreenAdapter` upgraded to `Optional[Callable[..., Any]]` with the `Callable` import added.
- Replaced `'as unknown as T'` casts in `spotify.ts` (`getAudioFeatures`, `getArtist`, `getMultipleAudioFeatures`) with typed wrappers that perform runtime shape checks and throw on invalid input.

### Fixed
- Fixed frontend verification so the script recognizes the repo-level `.venv` and no longer emits a misleading missing-virtualenv warning.
- Fixed backend authentication integration tests to match the current OAuth redirect/state flow used by the frontend client and authenticator.
- Fixed backend cache explorer startup to use the current backend URL configuration API instead of the removed `BackendConfig` class.
- Fixed backend cache statistics in frontend mode so playlist and file counts reflect environment-scoped cache files instead of incorrectly reporting zero items.
- Fixed cache explorer playlist inspection so expired cache entries no longer crash detailed cache loading with `dictionary changed size during iteration`.
- Fixed the visible cache explorer Close button in backend mode so it dismisses the popup that is actually open.

### Removed
- Dead `calculateAverageAudioFeatures` from `services/analysis.ts` (no callers).
- Unused `export_id` parameter from `BackendClient.download_export`, `BackendMainScreenAdapter.download_export`, and the call site at `main_screen_export.py:496`.
- Unused `playlist` parameter from `_build_backend_output_path` (orchestrator + `MainScreen` delegation).

### Changed
- Hardened backend playlist analysis by queueing large analysis jobs with retry-safe status updates instead of relying on request-scoped background work.
- Refactored `MainScreen` to extract pure logic (filenames, sort/filter) and stabilize job state, reducing technical debt and improving testability.
- Hardened backend npm dependencies by upgrading Wrangler, Workers types, and TypeScript ESLint, replacing SheetJS `xlsx` usage with ExcelJS, and overriding vulnerable transitive `esbuild` and `uuid` releases until upstream packages publish patched dependency ranges.
- Optimized GitHub Actions workflows to reduce redundant CI runs by 40-60% while maintaining full test coverage on protected branches
  - CI now runs only on main/develop/WIP branches instead of all branches
  - Security scans run only on PRs (not duplicate push events) with weekly baseline scans
  - Language-specific security jobs (Bandit, npm audit) skip when irrelevant files change
  - Deployment workflows skip redundant test runs when CI already validated the code
  - Streamlined dependency review to single job, removing duplicates

### Fixed
- Fixed frontend verification so the script recognizes the repo-level `.venv` and no longer emits a misleading missing-virtualenv warning.
- Fixed backend authentication integration tests to match the current OAuth redirect/state flow used by the frontend client and authenticator.
- Fixed backend cache explorer startup to use the current backend URL configuration API instead of the removed `BackendConfig` class.
- Fixed backend cache statistics in frontend mode so playlist and file counts reflect environment-scoped cache files instead of incorrectly reporting zero items.
- Fixed cache explorer playlist inspection so expired cache entries no longer crash detailed cache loading with `dictionary changed size during iteration`.
- Fixed the visible cache explorer Close button in backend mode so it dismisses the popup that is actually open.

## [0.1.5] - 2026-03-19

### Changed
- Desktop packaging now uses icon assets from `resources/` across all build targets (`.ico` for Windows, `.icns` for macOS, and `.png` for Linux) so artifacts consistently include the intended app icons.
- Build CI now validates the required per-platform icon file before running PyInstaller, failing fast with a clear error if an icon asset is missing.
- Linux release archives now include a desktop entry template and installer helper script so launcher integrations can use the packaged SpotiBye icon reliably.

## [0.1.4] - 2026-03-19

### Fixed
- Fixed backend cache explorer fallback in packaged builds by resolving the adapter import using the launcher runtime module path first (`src.frontend...`), preventing silent fallback to the legacy explorer.
- Fixed legacy WebP image cache persistence by rejecting `.webp` entries at image lookup time and forcing a fresh JPEG/PNG re-download.
- Fixed cached image loader state reset so future image reload attempts are not blocked after a prior local-load attempt.

## [0.1.3] - 2026-03-18

### Fixed
- Fixed playlist cover images still showing red X after 0.1.2: on startup the app now purges leftover `.webp` image cache files (cached by older builds) so fresh JPEG downloads are triggered instead of Kivy attempting to decode an unsupported format.
- Fixed Cache Explorer still showing "No cached playlists found" after 0.1.2: resolved a race condition where the legacy `PersistentCache` background load thread was overwriting backend playlist data; also added a TTL-bypass read so playlists are displayed even after the 1-hour cache window expires.

## [0.1.2] - 2026-03-18

### Fixed
- Fixed backend cache explorer fallback wiring so backend cache status refresh and playlist population use valid background tasks.
- Fixed cache explorer consistency in backend mode by ensuring local backend cache playlists are surfaced when legacy playlist metadata is empty.
- Fixed playlist cover cache compatibility by avoiding WebP-only cached image output in packaged desktop builds.

## [0.1.1] - 2026-03-17

### Fixed
- Hardened GitHub Actions desktop release workflow for permissions, release creation, and artifact packaging across platforms.
- Fixed backend resumable export route regressions that caused CI test failures after recent changes.
- Fixed packaged desktop startup failures by including missing runtime dependency `kivymd` in build manifests.
- Fixed packaged macOS playlist cover rendering by bundling CA certificates and using a pinned cert bundle for HTTPS image downloads.
- Fixed backend-mode cache explorer mismatch so cached playlist visibility matches cache status reporting.

## [0.1.0] - 2026-03-15

### Added
- Initial semantic version baseline for the desktop app at 0.1.0.
- Cross-platform desktop build pipeline via GitHub Actions for Windows, macOS, and Linux executables.
- Versioned build artifact naming in CI release outputs.

### Changed
- Desktop executable metadata now uses the project version from pyproject.toml for Windows and macOS packaging.
- Release process now includes explicit changelog maintenance and semantic version tracking.

### Fixed
- Removed hardcoded executable version values from the PyInstaller spec to reduce release drift.
- Fixed GitHub release publishing permissions by granting workflow `contents: write` access.
- Fixed release creation race conditions by moving GitHub release publishing to a single post-build job.
- Added explicit Node.js 24 action runtime opt-in for GitHub Actions compatibility.
- Reduced Windows CI packaging time by switching artifact compression to `tar -a` instead of `Compress-Archive`.
- Improved CI dependency install reliability and speed with pip cache and `--prefer-binary` package resolution.
- Fixed Windows CI Kivy/OpenGL initialization failures by deferring `Window` imports until runtime and forcing ANGLE-backed Kivy settings during PyInstaller builds.
- Fixed Windows CI packaging to support both PyInstaller output modes (`dist/SpotiBye/` onedir and `dist/SpotiBye.exe` onefile).
- Fixed packaged desktop startup crash (`ModuleNotFoundError: kivymd`) by including `kivymd` in project and CI build dependencies.
- Fixed packaged macOS playlist cover rendering by bundling CA certificates (`certifi`) and using the certificate bundle for HTTPS image downloads.
- Fixed cache explorer mismatch in backend mode so backend-cached playlists are visible instead of incorrectly showing "No cached playlists found" while file counts are present.

### Known Issues
- macOS bundle identifier and company metadata still use placeholder values and should be finalized before public distribution.

# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog and this project uses Semantic Versioning.

## [Unreleased]

### Changed
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

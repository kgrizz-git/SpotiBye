# Changelog

All notable changes to this project are documented in this file.

The format follows Keep a Changelog and this project uses Semantic Versioning.

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

### Known Issues
- macOS bundle identifier and company metadata still use placeholder values and should be finalized before public distribution.

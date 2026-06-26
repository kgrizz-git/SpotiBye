# Phase 3 Plan: Frontend Executable Build Spec Update

## Goal
Build a desktop executable that packages the frontend application only, while communicating with the backend exclusively over HTTP APIs (Cloudflare Worker or custom URL).

## Scope
- Update frontend executable entrypoint and PyInstaller spec.
- Keep frontend/backend separation explicit in packaging.
- Keep `src/backend` out of Python executable packaging.
- Preserve existing backend selector behavior (Localhost, Cloudflare Dev, Cloudflare Prod, Custom).

## Non-Goals
- Do not bundle backend runtime into the desktop app.
- Do not change Cloudflare Worker deployment process in this plan.
- Do not edit `SpotifyPlaylistExporterV2-BACKUP-COPY-READ-ONLY/`.

## Current State (Observed)
- Runtime launch for split architecture uses `run_frontend_backend.py`.
- `spotibye.spec` currently points to `main.py`.
- `main.py` still imports legacy package entry (`spotify_playlist_exporter_v2.app`).
- `spotibye.spec` includes `src/frontend` and `src/spotify_playlist_exporter_v2` as data.

## Required Updates

### 1) Entrypoint Alignment
Use a frontend-specific entrypoint for packaged builds.

Option A (preferred):
- Update `spotibye.spec` to use `run_frontend_backend.py` as `Analysis` script input.

Option B:
- Create `main_frontend.py` that imports `src.frontend.app.SpotifyExporterApp` and use that in `spotibye.spec`.

Rationale:
- Packaging should mirror runtime architecture used in Phase 2+.

### 2) `spotibye.spec` Packaging Rules
Update `spotibye.spec` with frontend-separation intent:
- `Analysis([...])` script should target frontend entrypoint (see section above).
- Keep `datas` minimal and explicit:
  - include `src/frontend` resources/assets
  - include only required compatibility modules from `src/spotify_playlist_exporter_v2` (or remove once adapters are migrated)
- Ensure backend TypeScript tree is not included:
  - do not add `src/backend/**` to `datas`.
- Keep signing behavior environment-driven (`SPOTIBYE_CODESIGN_IDENTITY`).
- Continue building from spec without makespec-only flags:
  - allowed: `pyinstaller spotibye.spec --noconfirm --clean`
  - avoid: `--onefile`, `--noconsole` when using `.spec`.

### 3) Backend URL Configuration for Packaged App
Ensure packaged app can target external backend:
- Verify startup backend selector remains enabled by default.
- Verify env-based overrides still work:
  - `SPOTIBYE_BACKEND_URL`
  - `SPOTIBYE_PRODUCTION_BACKEND_URL`
  - `SPOTIBYE_USE_PRODUCTION`
  - `SPOTIBYE_ENABLE_BACKEND_SELECTOR`
- Add explicit production fallback URL policy in frontend config docs.

### 4) CI Build Workflow Consistency
Update any workflow/docs still building via legacy entrypoint:
- Replace commands that imply legacy startup path with spec-driven build.
- Use a single canonical command:
  - `pyinstaller spotibye.spec --noconfirm --clean`
- Ensure release artifacts are frontend executable artifacts only.

### 5) Documentation Consistency
Update docs that still imply monolithic or legacy startup:
- `dev-docs/guides/build-and-deploy-guide.md`
- `docs/plans/phase-3-production-deployment.md` (distribution snippet currently shows `pyinstaller --onefile main.py`)
- Any debug docs that assume `python main.py` as the default split-arch launcher.

## Proposed File Change List

Must update:
- `spotibye.spec` (entrypoint + packaging boundaries)
- `dev-docs/guides/build-and-deploy-guide.md` (canonical build command and architecture note)
- `docs/plans/phase-3-production-deployment.md` (fix outdated distribution command snippet)

Likely update:
- `main.py` (either deprecate for packaging path or add note that split-arch packaging uses frontend entrypoint)
- `.github/workflows/build.yml` (if any command diverges from spec-based build)

Optional (cleanest long-term):
- Create `main_frontend.py` and make it the packaging entrypoint.

## Implementation Steps
1. Patch `spotibye.spec` to point at frontend entrypoint.
2. Build locally on macOS using spec command.
3. Launch packaged app and verify backend selector + API calls.
4. Run backend smoke tests separately (`src/backend`) to keep deployment independence.
5. Update docs/workflows to remove stale commands.
6. Record all touched files in `docs/phase-3-files.md`.

## Validation Checklist
- App launches from packaged artifact without Python source checkout.
- Backend selector appears and can connect to Cloudflare Dev/Prod endpoints.
- Spotify login and at least one export flow complete through remote backend.
- No backend source/runtime is bundled in desktop artifact.
- Build command and docs are consistent across local + CI.

## Risks and Mitigations
- Risk: Legacy adapter imports from `src/spotify_playlist_exporter_v2` force extra bundled files.
  - Mitigation: Keep only required compatibility modules now; plan a follow-up migration to `src/frontend` equivalents.
- Risk: Docs drift causes incorrect release commands.
  - Mitigation: Define one canonical command (spec-based) and reference it everywhere.
- Risk: Environment mismatch between local and packaged app backend URL behavior.
  - Mitigation: Add explicit startup/backend selection smoke tests to release checklist.

## Rollback Plan
- Revert `spotibye.spec` entrypoint to previous script.
- Rebuild with prior known-good spec.
- Keep previous release artifacts available in GitHub Releases.

## Done Definition
- Frontend executable builds from spec using split-architecture entrypoint.
- Packaged app communicates with separate backend over HTTP only.
- Docs and CI use consistent, current build commands.
- `docs/phase-3-files.md` updated with all file edits for this phase.

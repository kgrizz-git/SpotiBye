# Build and Deploy Guide

This project has two deployment tracks:
- Python desktop app build (PyInstaller)
- Cloudflare Workers backend deployment (`src/backend`)

## 1) Python Desktop App

### Prerequisites
- Python 3.10 recommended for release builds (matches CI)
- Virtual environment at project root (`.venv`)

### Install dependencies
```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Build locally (unsigned, default)
```bash
source .venv/bin/activate
pyinstaller spotibye.spec --noconfirm --clean
```

Output is written to `dist/`.

### Choose backend in GUI (startup)

The backend-integrated frontend now prompts for backend target at startup.

Options in the popup:
- `Localhost` (`http://localhost:8787`)
- `Cloudflare Dev` (only when `SPOTIBYE_DEV_BACKEND_URL` is configured)
- `Cloudflare Prod` (only when `SPOTIBYE_PRODUCTION_BACKEND_URL` is configured)
- `Custom` URL

Flow:
1. Select target backend.
2. Review the automatic connection status, or click `Test Connection` to verify manually.
3. Click `Continue`.
4. If the backend is unavailable, the app blocks the actual Spotify connect/login step and shows an error there.

The selected backend URL is saved to `~/.spotibye_cache/backend_selection.json` and restored on next launch. With no saved or configured URL, the app opens with an empty Custom selection and does not connect until you choose a valid endpoint. Cancelling at that point leaves it unconfigured; it never silently connects to localhost.

Notes:
- You can configure a startup URL or named cloud presets with env vars:
  - `SPOTIBYE_BACKEND_URL`
  - `SPOTIBYE_DEV_BACKEND_URL`
  - `SPOTIBYE_PRODUCTION_BACKEND_URL`
  - `SPOTIBYE_USE_PRODUCTION`
- Feature flag to disable startup selector:
  - `SPOTIBYE_ENABLE_BACKEND_SELECTOR=false`

### macOS DMG packaging
```bash
cd dist
hdiutil create -volname "SpotiBye" -srcfolder SpotiBye.app -ov -format UDZO SpotiBye-macOS.dmg
cd ..
```

## 2) Code Signing

### Local/dev builds
- Signing is disabled by default in `spotibye.spec`.
- This avoids keychain errors when no Apple certificate is installed.

### Release builds (signed)
1. Install a valid Apple code-signing certificate in Keychain.
2. Check available identities:
```bash
security find-identity -v -p codesigning
```
3. Set the signing identity for the build:
```bash
export SPOTIBYE_CODESIGN_IDENTITY="Apple Development: Your Name (TEAMID)"
pyinstaller spotibye.spec --noconfirm --clean
```

Notes:
- `SPOTIBYE_CODESIGN_IDENTITY` is read by `spotibye.spec`.
- Do not pass `--onefile` or `--noconsole` when building from a `.spec` file.

## 3) GitHub Workflows

### Desktop executable workflow
- File: `.github/workflows/build.yml`
- Triggered by:
  - tag push matching `v*`, when the tagged commit is on `main`
  - manual run (`workflow_dispatch`)
- Builds on `windows-latest`, `macos-latest`, `ubuntu-latest`
- Produces artifacts:
  - Windows: `SpotiBye-Windows-vX.Y.Z.zip`
  - macOS: `dist/SpotiBye-macOS-vX.Y.Z.dmg`
  - Linux: `dist/SpotiBye-Linux-vX.Y.Z.tar.gz`

Linux artifact contents:
- `SpotiBye/` (PyInstaller app folder)
- `resources/SpotiBye black edited 1-modified.png` (launcher icon)
- `SpotiBye.desktop.template` (desktop entry template)
- `install-desktop-entry.sh` (installs a launcher entry in `~/.local/share/applications`)

After extracting the Linux archive, install a launcher entry:
```bash
cd SpotiBye-Linux-vX.Y.Z
./install-desktop-entry.sh
```

### Backend deployment workflows
- `.github/workflows/deploy-backend.yml`
  - Runs tests for changes under `src/backend/**`
  - Deploys development worker on `main` pushes
  - Deploys production worker on `v*` tags
- `.github/workflows/deploy-production.yml`
  - Manual production deployment path

## 4) Cloudflare Workers Backend (`src/backend`)

### Local backend dev
```bash
cd src/backend
npm ci
npm run dev
```

### Backend test/build
```bash
cd src/backend
npm run test:run
npm run build
```

### Deploy backend
```bash
cd src/backend
npm run deploy:dev
npm run deploy:prod
```

Required CI/CD secrets:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Worker runtime secrets (set with Wrangler):
```bash
cd src/backend
wrangler secret put SPOTIFY_CLIENT_ID
wrangler secret put SPOTIFY_CLIENT_SECRET
wrangler secret put JWT_SECRET
```

## 5) Versioning and Changelog

- Canonical desktop app version source: `pyproject.toml` (`[project].version`)
- Runtime package version: `src/spotify_playlist_exporter_v2/__init__.py`
- Release notes history: `CHANGELOG.md`

Rule:
- For any user-visible change, update `CHANGELOG.md` in the same pull request.

## 6) Recommended Release Flow

1. Verify backend tests pass (`src/backend`).
2. Bump desktop version in `pyproject.toml` and `src/spotify_playlist_exporter_v2/__init__.py`.
3. Update `CHANGELOG.md` for all user-visible changes.
4. **Build the desktop app locally and smoke-test before tagging** (see checklist below).
5. Tag release (`vX.Y.Z`) and push tag only after the smoke-test passes.
6. Let GitHub Actions build desktop artifacts and deploy production backend.

### Local smoke-test checklist (run before every tag)

```bash
source .venv/bin/activate
pyinstaller spotibye.spec --noconfirm --clean
```

Then launch the built executable (`dist/SpotiBye.app` on macOS, `dist/SpotiBye/SpotiBye` on Linux/Windows) and verify:

- [ ] App launches without a crash dialog or console traceback.
- [ ] Backend selector popup appears and `Test Connection` succeeds against your chosen backend.
- [ ] Playlist grid loads and all cover images render (no red X placeholders).
- [ ] Scroll through a few playlist cards — covers should appear within a few seconds.
- [ ] Open **Cache Explorer** — the playlist list should not be empty (should match the count shown in the status bar).
- [ ] Select a playlist in Cache Explorer and confirm tracks appear in the tracks column.
- [ ] Export at least one playlist to CSV or XLSX and confirm the file is written to Downloads.
- [ ] Quit and relaunch — backend selection is restored automatically (no selector popup on second launch unless explicitly cleared).

Only push the version tag once all checklist items pass on your local macOS build.

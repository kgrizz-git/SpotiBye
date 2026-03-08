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
- `Cloudflare Dev`
- `Cloudflare Prod`
- `Custom` URL

Flow:
1. Select target backend.
2. Click `Test Connection`.
3. Click `Continue`.

The selected backend URL is saved to `~/.spotibye_cache/backend_selection.json` and restored on next launch.

Notes:
- You can still force defaults with env vars:
  - `SPOTIBYE_BACKEND_URL`
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
  - tag push matching `v*`
  - manual run (`workflow_dispatch`)
- Builds on `windows-latest`, `macos-latest`, `ubuntu-latest`
- Produces artifacts:
  - Windows: `SpotiBye-Windows.zip`
  - macOS: `dist/SpotiBye-macOS.dmg`
  - Linux: `dist/SpotiBye-Linux.tar.gz`

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
wrangler secret put RECOCOBEATS_API_KEY
```

## 5) Recommended Release Flow

1. Verify backend tests pass (`src/backend`).
2. Build desktop app locally.
3. Tag release (`vX.Y.Z`) and push tag.
4. Let GitHub Actions build desktop artifacts and deploy production backend.

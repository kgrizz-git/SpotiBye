# Backend Selector GUI Patch Plan

## Objective

Add an in-app GUI flow that lets users choose which backend to use before the frontend attempts authentication or API calls.

Targets:
- `localhost` backend for local development
- Cloudflare development worker
- Cloudflare production worker
- Custom backend URL

## Why This Patch

Current behavior initializes backend URL and client at app startup, then immediately checks backend connection in the login screen. This forces users to preconfigure environment variables before launch.

This patch moves backend selection into the GUI startup flow and keeps env vars as fallback defaults.

## Scope

### In Scope
- Startup backend-selection popup/screen in the backend-integrated app path
- Connection test button (`/health`) before login
- Persisting last selected backend in local cache/config file
- Safe fallback to existing env-based defaults if no saved selection exists

### Out of Scope
- Replacing legacy `src/spotify_playlist_exporter_v2` app launch path
- Changing Cloudflare backend implementation
- OAuth protocol changes

## Current State (Reference)

- `src/frontend/config/backend_config.py`
  - Computes `CURRENT_BACKEND_URL` from env at import time.
- `src/frontend/app/backend_app.py`
  - Creates `BackendClient(CURRENT_BACKEND_URL)` in `_initialize_backend()`.
- `src/frontend/auth/backend_login_screen.py`
  - Calls `check_backend_connection()` from `__init__`, so connection checks happen immediately.

## Proposed UX

1. App starts and shows a `Backend Selection` modal (or first screen).
2. User picks one option:
   - `Localhost (http://localhost:8787)`
   - `Cloudflare Dev`
   - `Cloudflare Prod`
   - `Custom URL`
3. User clicks `Test Connection`.
4. If healthy, user clicks `Continue`.
5. App initializes login screen using selected backend URL.
6. Selection is saved for next launch; user can change selection from login screen.

## Patch Design

### 1) Add Runtime Backend Selection Helpers

File: `src/frontend/config/backend_config.py`

Add:
- Backend presets dictionary for display labels + URLs
- `get_default_backend_url()`
- `get_saved_backend_url()` / `save_backend_url(url)`
- `resolve_startup_backend_url()` that chooses:
  1. saved user selection
  2. env-based `CURRENT_BACKEND_URL`

Notes:
- Save file under `~/.spotibye_cache/backend_selection.json`
- Validate URL format (`http://` or `https://`)

### 2) Add Backend Selector UI Component

New file: `src/frontend/ui/backend_selector_popup.py`

Component responsibilities:
- Render preset choices and custom URL input
- Validate URL format
- `Test Connection` button using a temporary `BackendClient(url)` and `/health`
- Return selected URL via callback to app

### 3) Defer Client Initialization Until Selection

File: `src/frontend/app/backend_app.py`

Changes:
- Do not fully initialize backend client in `__init__`
- During `build()`, open selector popup before login actions
- Add method `apply_backend_url(url: str)` that:
  - creates/updates `BackendClient(url)`
  - updates global client via `set_backend_url(url)`
  - initializes cache/adapter safely
  - stores selected URL
- Add graceful fallback if selector is canceled (use resolved default)

### 4) Update Login Screen to Use Selected URL

File: `src/frontend/auth/backend_login_screen.py`

Changes:
- Remove unconditional connection check during `__init__`
- Add method `set_backend_client(client: BackendClient)`
- Trigger `check_backend_connection()` only after client assignment
- Show active backend URL in small label for clarity
- Optional button: `Change Backend` to reopen selector popup

### 5) Export and Wiring Updates

File: `src/frontend/ui/__init__.py` (if needed)
- Export selector popup component.

File: `src/frontend/app/__init__.py` (if needed)
- Keep app exports unchanged unless new app helper is added.

## Implementation Steps

- [x] Add backend selection persistence + resolver helpers in config module.
- [x] Create selector popup UI and test connection callback path.
- [x] Refactor backend app startup order to defer backend initialization.
- [x] Update login screen behavior to avoid auto-connection before selection.
- [x] Add active-backend indicator and optional change-backend action.
- [ ] Add/adjust tests for configuration and startup flow.
- [x] Update docs with launch and selection behavior.

## Test Plan

### Unit/Integration
- [ ] `backend_config`: saved URL read/write
- [ ] `backend_config`: invalid URL rejection
- [ ] `backend_config`: startup resolution priority
- [ ] selector popup: preset selection
- [ ] selector popup: custom URL validation
- [ ] selector popup: connection test pass/fail state
- [ ] backend app: no backend calls before selection
- [ ] backend app: selected URL applied to `BackendClient`

### Manual
- [ ] Launch app with no env vars set and select each preset.
- [ ] Launch app with saved selection and verify auto-restore.
- [ ] Switch backend from login screen and retry login.
- [ ] Verify offline/error messaging for unreachable backend.

## Acceptance Criteria

- [ ] User can choose backend in GUI before first connection attempt.
- [ ] App can connect to localhost, Cloudflare dev, and production URLs.
- [ ] Selected backend persists across restarts.
- [ ] Existing env var method still works as default/fallback.
- [ ] Login/auth flow works unchanged after backend selection.

## Risks and Mitigations

- Risk: startup complexity causes regressions in login flow.
  - Mitigation: keep selector isolated and default fallback path simple.
- Risk: stale saved URL points to dead backend.
  - Mitigation: require successful `Test Connection` before `Continue` (or warn clearly).
- Risk: mismatch between global and local backend client instances.
  - Mitigation: enforce single `apply_backend_url()` path in app bootstrap.

## Rollout Strategy

- Phase A: Implement selector and persistence behind a feature flag:
  - `SPOTIBYE_ENABLE_BACKEND_SELECTOR=true` (default true for dev)
- Phase B: Remove flag after validation in integration testing.

## Documentation Updates Required

- [x] `dev-docs/guides/build-and-deploy-guide.md`: Add section for selecting backend in GUI vs env vars.
- [x] `docs/plans/phase-2-real-integration-testing.md`: Add startup step to select backend target before auth tests.

## Definition of Done

- [ ] Code merged for files listed in this plan.
- [ ] Automated tests pass for modified modules.
- [ ] Manual smoke test confirms selection + login on at least one Cloudflare URL and localhost.
- [x] Docs updated to reflect new startup behavior.

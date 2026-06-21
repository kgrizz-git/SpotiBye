# Bug Review Medium and Low Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the medium and low severity issues from the 2026-06-21 bug review without broad refactors.

**Architecture:** Keep the scope tight: backend fixes should harden validation, error handling, and race-prone flows at the service and middleware boundaries; frontend fixes should correct API usage, thread safety, and cache behavior in the existing screen and service modules. Prefer small helper extraction only where it removes duplication or makes a boundary testable.

**Tech Stack:** TypeScript, Hono, Cloudflare Workers, Python, Kivy/KivyMD, pytest, Vitest

---

### Task 1: Harden backend auth and middleware edges

**Files:**
- Modify: `src/backend/routes/auth.ts`
- Modify: `src/backend/middleware/auth.ts`
- Modify: `src/backend/services/spotify-auth.ts`
- Test: `src/backend/tests/routes/auth.test.ts`
- Test: `src/backend/tests/middleware/auth.test.ts`

- [ ] **Step 1: Write failing tests for auth edge cases**

```ts
import { describe, expect, it } from "vitest";

describe("auth flow hardening", () => {
  it("rejects invalid redirect URIs", () => {});
  it("preserves refresh tokens when Spotify returns a rotated token", () => {});
  it("returns a clear callback error when OAuth exchange fails", () => {});
  it("handles corrupted session JSON without throwing", () => {});
  it("rejects empty Spotify credentials at service construction", () => {});
});
```

- [ ] **Step 2: Run the focused backend auth tests and confirm the current failures**

Run: `cd src/backend && npm run test:run -- tests/routes/auth.test.ts tests/middleware/auth.test.ts`
Expected: failures for redirect validation, corrupted session parsing, refresh token rotation, and empty credential construction.

- [ ] **Step 3: Implement the minimal auth and middleware fixes**

```ts
// src/backend/routes/auth.ts
const allowedRedirectUris = new Set([env.APP_URL, env.FRONTEND_URL]);
if (!allowedRedirectUris.has(redirect_uri)) {
  return c.json({ error: "Invalid redirect_uri" }, 400);
}

try {
  // OAuth callback exchange
} catch (error) {
  logger.error({ error }, "OAuth callback failed");
  return c.json({ error: "OAuth callback failed" }, 500);
}

// src/backend/middleware/auth.ts
try {
  const parsed = JSON.parse(sessionData);
  // validate parsed shape before use
} catch (error) {
  logger.warn({ error }, "Invalid session data in KV");
  return null;
}

// src/backend/services/spotify-auth.ts
if (!clientId || !clientSecret) {
  throw new Error("Spotify auth credentials are required");
}
if (newTokens.refresh_token) {
  tokenData.refresh_token = newTokens.refresh_token;
}
```

- [ ] **Step 4: Run the backend auth tests again**

Run: `cd src/backend && npm run test:run -- tests/routes/auth.test.ts tests/middleware/auth.test.ts`
Expected: pass.

- [ ] **Step 5: Commit the auth hardening changes**

```bash
git add src/backend/routes/auth.ts src/backend/middleware/auth.ts src/backend/services/spotify-auth.ts src/backend/tests/routes/auth.test.ts src/backend/tests/middleware/auth.test.ts
git commit -m "fix: harden backend auth boundaries"
```

### Task 2: Tighten backend service error handling and low-risk logic

**Files:**
- Modify: `src/backend/services/export.ts`
- Modify: `src/backend/services/analysis.ts`
- Modify: `src/backend/services/analysis-job.ts`
- Modify: `src/backend/index.ts`
- Modify: `src/backend/middleware/error.ts`
- Test: `src/backend/tests/services/export.test.ts`
- Test: `src/backend/tests/services/analysis.test.ts`
- Test: `src/backend/tests/services/analysis-job.test.ts`

- [ ] **Step 1: Write failing tests for export and analysis edge cases**

```ts
import { describe, expect, it } from "vitest";

describe("service edge cases", () => {
  it("keeps playlist metadata stable when playlist is missing", () => {});
  it("does not treat local-only playlists as a pagination failure", () => {});
  it("updates analysis job progress without losing concurrent fields", () => {});
  it("records failed queue messages even if the KV write throws", () => {});
});
```

- [ ] **Step 2: Run the focused service tests and confirm current failures**

Run: `cd src/backend && npm run test:run -- tests/services/export.test.ts tests/services/analysis.test.ts tests/services/analysis-job.test.ts`
Expected: failures around missing playlist metadata, local-track pagination, and stale job writes.

- [ ] **Step 3: Implement the backend service fixes**

```ts
// src/backend/services/export.ts
const playlistName = playlist?.name ?? "Unknown playlist";
const totalTracks = playlist?.tracks?.total ?? allTracks.length;

// src/backend/services/analysis.ts
if (items.every((item) => item.is_local)) {
  return { tracks: [], nextPageUrl: null };
}

// src/backend/services/analysis-job.ts
const updated = {
  ...currentJob,
  progress,
  updated_at: new Date().toISOString(),
};

// src/backend/index.ts
try {
  await markFailed(message, "queue processing failed");
} catch (error) {
  logger.error({ error }, "Failed to persist queue failure");
}
```

- [ ] **Step 4: Remove or simplify dead error branches that are never reached**

```ts
// src/backend/middleware/error.ts
// Keep only the branches that map to actual thrown error types.
```

- [ ] **Step 5: Run the backend service tests again**

Run: `cd src/backend && npm run test:run -- tests/services/export.test.ts tests/services/analysis.test.ts tests/services/analysis-job.test.ts`
Expected: pass.

- [ ] **Step 6: Commit the service hardening changes**

```bash
git add src/backend/services/export.ts src/backend/services/analysis.ts src/backend/services/analysis-job.ts src/backend/index.ts src/backend/middleware/error.ts src/backend/tests/services/export.test.ts src/backend/tests/services/analysis.test.ts src/backend/tests/services/analysis-job.test.ts
git commit -m "fix: harden backend service edge cases"
```

### Task 3: Repair frontend backend client and validation boundaries

**Files:**
- Modify: `src/frontend/services/backend_client.py`
- Modify: `src/frontend/config/backend_config.py`
- Modify: `src/frontend/utils/platform_utils.py`
- Modify: `src/frontend/services/reccobeats_backend.py`
- Test: `src/frontend/tests/services/test_backend_client.py`
- Test: `src/frontend/tests/config/test_backend_config.py`
- Test: `src/frontend/tests/utils/test_platform_utils.py`

- [ ] **Step 1: Write failing tests for client and config regressions**

```python
def test_download_export_uses_export_id(monkeypatch):
    ...

def test_health_check_wraps_non_backend_errors(monkeypatch):
    ...

def test_backend_url_validation_rejects_invalid_host():
    ...

def test_tk_root_is_destroyed_on_screen_size_error(monkeypatch):
    ...
```

- [ ] **Step 2: Run the focused frontend tests and confirm the current failures**

Run: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/services/test_backend_client.py src/frontend/tests/config/test_backend_config.py src/frontend/tests/utils/test_platform_utils.py -v`
Expected: failures for `download_export`, `health_check`, URL validation, and Tk cleanup.

- [ ] **Step 3: Implement the frontend boundary fixes**

```python
# src/frontend/services/backend_client.py
def download_export(self, export_id: str) -> Path:
    url = f"{self.base_url}/exports/{export_id}/download"
    return self._download_file(url)

def health_check(self) -> bool:
    try:
        return self._make_request("GET", "/health") is not None
    except Exception as exc:
        raise BackendAPIError("Health check failed") from exc

# src/frontend/config/backend_config.py
from urllib.parse import urlparse
def is_valid_backend_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

# src/frontend/utils/platform_utils.py
try:
    root = Tk()
    ...
finally:
    root.destroy()
```

- [ ] **Step 4: Run the frontend client tests again**

Run: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/services/test_backend_client.py src/frontend/tests/config/test_backend_config.py src/frontend/tests/utils/test_platform_utils.py -v`
Expected: pass.

- [ ] **Step 5: Commit the frontend boundary fixes**

```bash
git add src/frontend/services/backend_client.py src/frontend/config/backend_config.py src/frontend/utils/platform_utils.py src/frontend/services/reccobeats_backend.py src/frontend/tests/services/test_backend_client.py src/frontend/tests/config/test_backend_config.py src/frontend/tests/utils/test_platform_utils.py
git commit -m "fix: tighten frontend backend boundaries"
```

### Task 4: Clean up frontend screen and cache behavior

**Files:**
- Modify: `src/frontend/screens/backend_main_screen_adapter.py`
- Modify: `src/frontend/screens/main_screen_logout.py`
- Modify: `src/frontend/screens/main_screen_cache.py`
- Modify: `src/frontend/screens/main_screen_export.py`
- Modify: `src/frontend/app/backend_app.py`
- Modify: `src/frontend/ui/backend_cache_explorer.py`
- Modify: `src/frontend/ui/backend_playlist_card.py`
- Test: `src/frontend/tests/screens/test_backend_main_screen_adapter.py`
- Test: `src/frontend/tests/screens/test_main_screen_logout.py`
- Test: `src/frontend/tests/screens/test_main_screen_cache.py`

- [ ] **Step 1: Write failing tests for screen and cache regressions**

```python
def test_clear_cache_targets_hashed_files():
    ...

def test_logout_clears_credentials_when_app_has_no_logout_method():
    ...

def test_clear_all_cache_clears_cache_before_success_popup():
    ...

def test_update_analysis_ui_runs_on_main_thread():
    ...
```

- [ ] **Step 2: Run the focused screen tests and confirm the current failures**

Run: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/screens/test_backend_main_screen_adapter.py src/frontend/tests/screens/test_main_screen_logout.py src/frontend/tests/screens/test_main_screen_cache.py -v`
Expected: failures for cache clearing, logout fallback, and main-thread updates.

- [ ] **Step 3: Implement the screen and cache fixes**

```python
# src/frontend/screens/backend_main_screen_adapter.py
def clear_cache(self, filename: str) -> None:
    cache_key = self._cache_manager.build_cache_key(filename)
    self._cache_manager.clear(cache_key)

# src/frontend/screens/main_screen_logout.py
if hasattr(app, "logout"):
    app.logout()
else:
    self._clear_sensitive_state()

# src/frontend/screens/main_screen_cache.py
def clear_all_cache(self) -> None:
    self._cache_manager.clear_all()
    self._show_success_popup("Cache Cleared")

# src/frontend/ui/backend_playlist_card.py
@mainthread
def _update_analysis_ui(...):
    ...
```

- [ ] **Step 4: Remove the no-op or redundant code paths**

```python
# src/frontend/app/backend_app.py
# Keep LabelBase import at module scope instead of re-importing in the loop.

# src/frontend/screens/main_screen_export.py
# Remove the passthrough helper if multiple=True already returns the target path.

# src/frontend/ui/backend_cache_explorer.py
# Surface ImportError details in the UI state instead of swallowing them.
```

- [ ] **Step 5: Run the screen tests again**

Run: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/screens/test_backend_main_screen_adapter.py src/frontend/tests/screens/test_main_screen_logout.py src/frontend/tests/screens/test_main_screen_cache.py -v`
Expected: pass.

- [ ] **Step 6: Commit the screen cleanup**

```bash
git add src/frontend/screens/backend_main_screen_adapter.py src/frontend/screens/main_screen_logout.py src/frontend/screens/main_screen_cache.py src/frontend/screens/main_screen_export.py src/frontend/app/backend_app.py src/frontend/ui/backend_cache_explorer.py src/frontend/ui/backend_playlist_card.py src/frontend/tests/screens/test_backend_main_screen_adapter.py src/frontend/tests/screens/test_main_screen_logout.py src/frontend/tests/screens/test_main_screen_cache.py
git commit -m "fix: clean up frontend screen edge cases"
```

### Task 5: Verify the full medium and low fix set

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `dev-docs/TO_DO.md`

- [ ] **Step 1: Add a changelog entry for the user-visible fixes**

```md
## Unreleased

- Hardened auth, client validation, and screen cleanup paths from the 2026-06-21 bug review.
```

- [ ] **Step 2: Update the todo item when the plan is in progress**

```md
- [ ] Fix medium and low findings from 2026-06-21 bug review — see [fix plan](../docs/exec-plans/active/2026-06-21-bug-review-medium-low-fixes.md).
```

- [ ] **Step 3: Run the repo verification script**

Run: `./scripts/verify-all.sh`
Expected: exit 0 with no output on success.

- [ ] **Step 4: Commit the release-ready cleanup**

```bash
git add CHANGELOG.md dev-docs/TO_DO.md
git commit -m "docs: track medium and low bug review fixes"
```

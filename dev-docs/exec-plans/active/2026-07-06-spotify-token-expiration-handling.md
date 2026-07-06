# Handle Spotify Refresh Token Expiration

> **Source TODO:** [dev-docs/backlog/TO_DO.md#auth--token-lifecycle](../../../backlog/TO_DO.md)
>
> **status:** active (updated following architectural assessment)
>
> Spotify refresh tokens can expire for various reasons (user revoking access, extended inactivity, etc.). When this happens, the backend receives `invalid_grant` from Spotify's token endpoint and must gracefully handle re-authentication rather than leaving the user in a broken state. The July 20, 2026 deadline is referenced in Spotify's June 2026 developer policy update regarding the new 6-month refresh token expiration policy.

---

## Problem Analysis

When Spotify returns `invalid_grant` during token refresh:

1. **`services/spotify-auth.ts:refreshAccessToken`** (line 109-128): Throws a generic `Error('Failed to refresh token: <raw text>')` — the JSON response body (`{error: "invalid_grant"}`) is never parsed, so callers cannot distinguish `invalid_grant` from other failures.
2. **`middleware/auth.ts`**: Catches refresh errors (line 76) but doesn't delete the KV session, leaving stale tokens that will fail repeatedly on every subsequent request. In-memory deduplication (`refreshPromises` Map at line 29) needs careful ordering with negative caching to prevent race conditions.
3. **`middleware/error.ts`**: The error handler at line 36 maps **every** 401 to `code: 'UNAUTHORIZED'`, silently discarding any custom `code` set on the `HTTPException` (e.g., `AUTH_REQUIRED`). The frontend detection will never trigger unless this is fixed.
4. **`routes/auth.ts:/spotify/refresh`** (line 159-206):
   - The route is itself protected by `authMiddleware` — if the session is so invalid that even refresh fails, the middleware throws 401 and this handler never runs.
   - `authMiddleware` already performs token refresh before the route handler executes (lines 52-81 of `middleware/auth.ts`). The handler then redundantly calls `spotifyAuth.refreshAccessToken()` again at line 171 — a double-refresh. If that second call gets `invalid_grant`, the catch block (line 202) returns `TOKEN_REFRESH_FAILED` and never signals `AUTH_REQUIRED`.
5. **`frontend/services/backend_client.py`**: `BackendAPIError` stores `response_data` but callers have no structured attribute to inspect "re-auth required" vs other 401 causes without modifying exception attributes post-instantiation.
6. **`frontend/screens/main_screen.py`**: Relies on substring matching against stringified errors from `_format_backend_api_error` in `src/frontend/screens/adapter_mixins/core.py`.
7. **`frontend/app/backend_app.py:_try_auto_login`**: Only checks local JWT expiry (`_is_jwt_expired`), not whether the token is still valid against the backend. `health_check()` is an unauthenticated public endpoint that cannot validate a Spotify token. However, `GET /auth/me` (`routes/auth.ts:222`) exists and must be used for startup session validation.

---

## Implementation Steps

### 1. Backend: Add `AUTH_REQUIRED` error code to `types/api.ts`

- [ ] Add `AUTH_REQUIRED = 'AUTH_REQUIRED'` constant to `src/backend/types/api.ts` (or inline it as a string literal in the error response types).

### 2. Backend: Create `src/backend/types/errors.ts` with custom exception classes

- [ ] Create `src/backend/types/errors.ts` (currently missing) to house shared custom error definitions.
- [ ] Define a custom type-safe `AuthRequiredException` subclassing Hono's `HTTPException` (from `'hono/http-exception'`):
  ```ts
  import { HTTPException } from 'hono/http-exception';

  export class AuthRequiredException extends HTTPException {
    readonly code: string = 'AUTH_REQUIRED'; // set once here; do NOT repeat in constructor body
    constructor(message = 'Refresh token expired or revoked') {
      super(401, { message });
      // No re-assignment needed — the class-field initializer above already sets `code`.
    }
  }
  ```
- [ ] Define a standard `NonRetryableError` class extending `Error` for background task queues:
  ```ts
  export class NonRetryableError extends Error {
    readonly code = 'NON_RETRYABLE';
    constructor(message = 'Spotify session expired or revoked. Please sign in again.') {
      super(message);
      this.name = 'NonRetryableError';
    }
  }
  ```
- [ ] Do **not** introduce a custom `InvalidGrantError` class — if it escapes the middleware's inner catch block, `middleware/error.ts` would treat it as a 500. Throwing `AuthRequiredException` (which inherits from `HTTPException`) directly ensures it is caught by the middleware's `if (error instanceof HTTPException)` branch.
- [ ] Prefer `err instanceof AuthRequiredException` over `(err as { code?: string }).code === 'AUTH_REQUIRED'` property checks wherever the import is available (e.g. in `middleware/error.ts` and `middleware/auth.ts`). The property-cast approach still works but is less type-safe.

### 3. Backend: Fix `middleware/error.ts` to preserve `AUTH_REQUIRED` code

> **Critical:** The error handler at line 36 of `src/backend/middleware/error.ts` unconditionally overwrites `code = 'UNAUTHORIZED'` for every 401, discarding any custom `code` set on the exception.

- [ ] In `middleware/error.ts`, check for explicit error codes on `HTTPException` instances before applying status-based mapping defaults:
  ```ts
  if (err instanceof HTTPException) {
    status = err.status;
    message = err.message || message;
    const errAny = err as unknown as { code?: string };
    code = (status === 401 && errAny.code === 'AUTH_REQUIRED')
      ? 'AUTH_REQUIRED'
      : status === 401 ? 'UNAUTHORIZED'
      : status === 403 ? 'FORBIDDEN'
      : status === 404 ? 'NOT_FOUND'
      : 'HTTP_ERROR';
  }
  ```
- [ ] Because Hono passes the exact runtime exception instance to `errorHandler(err, c)`, checking `errAny.code === 'AUTH_REQUIRED'` (or `err instanceof AuthRequiredException` if imported) reliably preserves the custom error code without being lost during error serialization.

### 4. Backend: Update `SpotifyAuthService` token methods to throw `AuthRequiredException`

- [ ] Modify `services/spotify-auth.ts:refreshAccessToken` (line 122-125) and `exchangeCodeForTokens` (lines 76-107; actual start is 76, not 89) with defensive JSON parsing:
  - When `response.ok` is false, buffer the response body with `response.text()` **first**, then attempt to JSON-parse the buffered string. Do **not** call `response.text()` after `response.json()` — the Fetch body stream is already consumed and will return an empty string.
    ```ts
    if (!response.ok) {
      const raw = await response.text();
      try {
        const body = JSON.parse(raw) as { error?: string };
        if (body.error === 'invalid_grant') {
          throw new AuthRequiredException();
        }
        throw new Error(`Failed to refresh/exchange token: ${body.error || response.statusText}`);
      } catch (parseError) {
        // Re-throw AuthRequiredException so it is not swallowed.
        if (parseError instanceof AuthRequiredException) throw parseError;
        // Non-JSON body (e.g. HTML 502/503) — include raw text in message.
        throw new Error(`Failed to refresh/exchange token: ${raw || response.statusText}`);
      }
    }
    ```

### 5. Backend: Update `middleware/auth.ts` with session cleanup and atomic negative caching

> **Context on `refreshPromises` & Cooldown:** `middleware/auth.ts:29` maintains an in-memory `refreshPromises` Map to deduplicate concurrent refresh requests within the same Worker instance. To protect across **different Worker instances**, we use a short-lived negative cache key (`REFRESH_FAILED:<session_id>`).

- [ ] Before attempting a Spotify token refresh in `middleware/auth.ts`, check if `REFRESH_FAILED:<session_id>` exists in `SESSIONS_KV`. If set, skip refresh and immediately throw `new AuthRequiredException()`.
- [ ] In the catch block at line 76, check if the error is an `HTTPException` with `code === 'AUTH_REQUIRED'` (or `error instanceof AuthRequiredException`).
- [ ] If `AUTH_REQUIRED`, perform cleanup in the catch block **before** the `finally` block runs:
  - Set negative cache: `await c.env.SESSIONS_KV.put(\`REFRESH_FAILED:\${payload.session_id}\`, '1', { expirationTtl: 60 });` (minimum TTL enforced by Cloudflare Workers KV is 60 seconds; closes the timing window before `refreshPromises.delete` removes the promise in `finally`).
  - Delete session: `await c.env.SESSIONS_KV.delete(payload.session_id);`.
- [ ] Re-throw the exception as-is. On successful refresh, ensure any existing `REFRESH_FAILED:<session_id>` key is deleted immediately after the successful session KV put (`await c.env.SESSIONS_KV.put(...)` at line 75).

### 6. Backend: Clean up `/spotify/refresh` route

- [ ] Keep `authMiddleware` on `POST /spotify/refresh` (`routes/auth.ts:159`) to guarantee JWT authentication and transparent Spotify token refreshing when needed.
- [ ] Remove the redundant `spotifyAuth.refreshAccessToken(...)` call and database/KV update from the route handler body (lines 170-183) to prevent double-refreshes.
- [ ] Retain only JWT access token generation and return (lines 185-201). Note that returning only `access_token`, `token_type`, `expires_in`, and `spotify_access_expires_in` is safe and backward compatible because `backend_client.py:refresh_token()` only reads `token` / `access_token`.
- [ ] Compute `spotify_access_expires_in` dynamically using the session's **`expires_at` field** (the Spotify access-token expiry stored in milliseconds since epoch), converted to remaining seconds. Use a non-negative guard against clock skew:
  `spotify_access_expires_in: Math.max(0, Math.floor((session.expires_at - Date.now()) / 1000))`
  > **Note:** `session.expires_at` (milliseconds) is distinct from `SPOTIFY_SESSION_TTL_SECONDS` (the KV record lifetime in seconds). These are equal at session creation but diverge over time — always derive `spotify_access_expires_in` from `expires_at`, never from the constant.

### 7. Backend: Prevent Queue Retries on Auth Failure

- [ ] In `src/backend/services/analysis-job.ts:getAccessToken()`, ensure that missing sessions or missing refresh tokens throw `new AuthRequiredException('Analysis session expired')` rather than generic `Error`s.
- [ ] In `src/backend/services/analysis-job.ts:process()`, wrap `getAccessToken()` and Spotify API calls. If an error is caught where `error instanceof AuthRequiredException` (or `code === 'AUTH_REQUIRED'`), delete the KV session, set job status to `'failed'`, and throw `new NonRetryableError('Spotify session expired or revoked. Please sign in again.')`.
- [ ] Note that `jobService.markFailed(body, error)` (`analysis-job.ts:97`) persists the error message to cache (`status: 'failed'`), allowing frontend status polling (`GET /analysis/status`) to detect the failure and display the re-auth message.
- [ ] In `src/backend/index.ts:queue()`, add the `NonRetryableError` / `AUTH_REQUIRED` check **before** the existing `message.attempts >= 3` guard — not inside it. If added after, the first two `AUTH_REQUIRED` failures will incorrectly call `message.retry()`. The corrected structure is:
  ```ts
  try {
    await jobService.process(body);
    // Replace existing bare console.log (Rule #5 violation) with structured log:
    console.error(JSON.stringify({ event: 'QUEUE_JOB_COMPLETED', job_id: body.job_id }));
    message.ack();
  } catch (error) {
    const isNonRetryable =
      error instanceof NonRetryableError ||
      (error as { code?: string }).code === 'AUTH_REQUIRED' ||
      (error as { code?: string }).code === 'NON_RETRYABLE';

    if (isNonRetryable) {
      // Fail immediately — do not consume any retry budget.
      try { await jobService.markFailed(body, error); } catch { /* swallow KV failure */ }
      message.ack();
      continue;
    }

    console.error(JSON.stringify({ event: 'QUEUE_JOB_FAILED', job_id: body.job_id, attempt: message.attempts }));
    if (message.attempts >= 3) {
      try { await jobService.markFailed(body, error); } catch (markFailedError) { /* existing guard */ }
      message.ack();
      continue;
    }
    message.retry();
  }
  ```
- [ ] **Pre-existing Rule #5 violation:** `index.ts` line 97 contains a bare `console.log` for successful job processing. Replace it with a structured `console.error(JSON.stringify({...}))` call in the same PR (shown in the snippet above).

### 8. Frontend: Expose `error_code` in `BackendAPIError` safely

- [ ] In `src/frontend/services/backend_client.py`, update `BackendAPIError.__init__` (line 19) to accept an optional `error_code: Optional[str] = None` parameter without breaking existing callers:
  ```python
  def __init__(
      self,
      message: str,
      status_code: Optional[int] = None,
      response_data: Optional[Dict[str, Any]] = None,
      error_code: Optional[str] = None,
  ):
      super().__init__(message)
      self.status_code = status_code
      self.response_data = response_data or {}
      if error_code is None and isinstance(self.response_data, dict):
          error_payload = self.response_data.get("error", {})
          if isinstance(error_payload, dict):
              error_code = error_payload.get("code")
      self.error_code = error_code
  ```
- [ ] In `_make_request` (`backend_client.py:136`), pass `error_code` cleanly into constructor invocation when raising `BackendAPIError`.
- [ ] Also update `_download_file` (`backend_client.py:429`) to extract and pass `error_code` from the response payload when raising `BackendAPIError`. Download endpoints can also return `AUTH_REQUIRED`, and the current manual message-build in `_download_file` bypasses the new `error_code` extraction logic.

### 9. Frontend: Add `AUTH_REQUIRED` detection and `get_me` in `BackendClient`

- [ ] Create a helper method in `BackendClient` (e.g., `is_auth_required_error(exc)`) that returns `True` when `exc` is a `BackendAPIError` with `status_code == 401` and `error_code == 'AUTH_REQUIRED'`.
- [ ] Add a method `get_me(self) -> Dict[str, Any]` to `BackendClient` (`src/frontend/services/backend_client.py`) that makes an authenticated request: `self._make_request("GET", "/auth/me")`.
- [ ] The retry helper `_run_with_transient_retry` in `core.py` already excludes 401 from `retryable_statuses` — `AUTH_REQUIRED` errors will surface immediately without consuming retry budget. Add an inline comment to `retryable_statuses` explicitly noting that 401 is intentionally excluded so future maintainers do not add it.

### 10. Frontend: Wire `AUTH_REQUIRED` to re-login and wipe persisted cache

> **Reconciling Cache Clearing Policy:** When Spotify returns `invalid_grant` (`AUTH_REQUIRED`), the refresh token is permanently revoked or expired under Spotify's 6-month policy. Unlike transient network glitches, this state cannot recover silently. Therefore, we **must** clear both in-memory credentials and the persisted token file (`cache_manager.clear_auth_token()`) to prevent infinite auto-login loops on subsequent app launches.

- [ ] In Kivy frontend's `src/frontend/screens/main_screen.py:_on_backend_error()`, add `"auth_required"` and `"code=auth_required"` to `auth_related` substrings (lines 265-271) that trigger `app.prompt_reauthentication()` (alias for `handle_session_expired`).
- [ ] Verify that `_format_backend_api_error` in `src/frontend/screens/adapter_mixins/core.py` appends `code=AUTH_REQUIRED`, ensuring substring matching in `main_screen.py` functions reliably.
- [ ] **Fix `handle_session_expired` in `backend_app.py` (line 305–332):** The existing implementation only clears the in-memory token (`self.backend_client.clear_auth_token()`). It must **also** wipe the persisted disk cache to prevent the stale token file from being reloaded on next startup. Add:
  ```python
  if self.cache_manager:
      self.cache_manager.clear_auth_token()
  ```
  This is a bug fix in existing code, not just a new flow — the disk file survives today even when the session is expired.
- [ ] In `src/frontend/auth/backend_auth.py:BackendAuthenticator.refresh_token()` (line 343), when catching a `BackendAPIError`, inspect `exc.error_code == 'AUTH_REQUIRED'` directly (preferred over substring matching). If true:
  - Clear in-memory token (`self.backend_client.clear_auth_token()`).
  - Clear persisted disk cache if available via `cache_manager.clear_auth_token()`.
  - Trigger app-level re-login prompt if UI is running.
  - Return `False` (maintaining the existing `bool` return contract for callers in `backend_client.py` and tests, while ensuring auth caches are wiped).

### 11. Frontend: Validate cached tokens on startup via `GET /auth/me`

- [ ] In `src/frontend/app/backend_app.py:_try_auto_login`, after checking local `_is_jwt_expired`, call `self.backend_client.get_me()` to verify session validity against the backend.
  - **Do not use `health_check()`**, as it is an unauthenticated endpoint.
  - **Threading — Kivy main thread must not block:** `get_me()` makes a network call. Run it on a background thread (e.g. `threading.Thread(target=_validate_and_proceed, daemon=True).start()`) so the Kivy event loop is not blocked. Keep the user on the login screen showing a "Verifying session…" status until the background thread completes. Only call `self.switch_to_main()` (or clear-and-stay) from inside a `@mainthread`-decorated callback or via `Clock.schedule_once(lambda _: ..., 0)` to return to the UI thread.
  - **Prevent UI Race Condition:** Do not call `self.switch_to_main()` before `get_me()` returns. The login screen status label should show a connecting state during validation so the user is not presented with a blank login screen with no feedback.
- [ ] If `GET /auth/me` returns 401 / `AUTH_REQUIRED`:
  - Wipe persisted cache (`self.cache_manager.clear_auth_token()`).
  - Keep user on login screen with notice: `"Your Spotify session has expired. Please sign in again."`
- [ ] If `GET /auth/me` raises a **transport error** (non-401, `status_code is None` — e.g. backend offline, timeout, DNS failure):
  - Do **not** wipe the cached token — the session may still be valid.
  - Log a warning and proceed to the main screen as if validation succeeded (graceful degradation matching current offline behavior). The backend will enforce auth on the next real API call.
- [ ] If `GET /auth/me` succeeds (returning `{ data: user }`), complete the transition to the main screen.

### 12. Tests

- [ ] **Backend Unit/Integration Tests (`auth-flow.test.ts` & `auth-middleware.test.ts`)**:
  - Mock Spotify token endpoint returning `{ error: "invalid_grant" }` → verify middleware deletes KV session and returns `401` with `code: 'AUTH_REQUIRED'`.
  - Verify `errorHandler` preserves explicit `AUTH_REQUIRED` code without mapping to `UNAUTHORIZED`.
  - Verify `refreshPromises` Map and `REFRESH_FAILED` negative cache prevent concurrent refresh race conditions.
  - Verify `/spotify/refresh` route no longer calls `spotifyAuth.refreshAccessToken()` directly.
  - Verify `AnalysisJobService` and `queue()` consumer fail immediately on `AUTH_REQUIRED` without retrying.
- [ ] **Frontend Tests (`test_auth.py` & `test_main_screen_logout.py`)**:
  - Verify `BackendAPIError` correctly extracts and sets `error_code='AUTH_REQUIRED'`.
  - Verify `BackendAuthenticator.refresh_token()` wipes **both** in-memory and disk cache on `AUTH_REQUIRED` and returns `False`.
  - Verify `handle_session_expired` wipes the disk cache (new behavior after the fix in Step 10).
  - Verify `_format_backend_api_error` output contains `code=AUTH_REQUIRED` so `main_screen.py` detects it.
  - Verify `_download_file` 401 `AUTH_REQUIRED` responses surface `error_code='AUTH_REQUIRED'` on the raised `BackendAPIError`.
  - Verify `_try_auto_login` with a transport error (offline) proceeds to main screen without wiping cache.
  - Verify `_try_auto_login` with a 401 `AUTH_REQUIRED` wipes disk cache and keeps user on login screen.
- [ ] **Structured Verification Procedure (Manual E2E)**:
  - Document verification steps using `./scripts/verify-all.sh` and running local backend/frontend against simulated expired tokens to verify login UI redirection.

### 13. Backend & Frontend: Structured Logging & Observability

- [ ] In accordance with `AGENTS.md` Rule #5 (*"No `console.log` in non-test backend code — use structured logging"*), use structured error output (e.g. `console.error(JSON.stringify({ event: 'TOKEN_REFRESH_FAILED', session_id, code: 'AUTH_REQUIRED' }))` or project logger) for `invalid_grant` events and KV deletions in backend middleware and workers. Never use bare `console.log`.
- [ ] The pre-existing `console.log` at `index.ts:97` (successful queue job) must be converted to `console.error(JSON.stringify({...}))` in the same PR (see Step 7 snippet).
- [ ] On the frontend, log detection of `AUTH_REQUIRED` events using standard Python structured logging (`logger.error(...)` / `logger.warning(...)` with context).

### 14. Documentation & Changelog

- [ ] Update `CHANGELOG.md` under the unreleased section (in the same PR as required by project rules) describing the new Spotify 6-month refresh token expiration handling and automatic UI re-login prompt.

---

## Risks & Considerations

- **Race conditions & Cooldown**: The `refreshPromises` map handles in-memory deduplication for concurrent requests on the same Worker instance. The `REFRESH_FAILED:<session_id>` negative cache (with **60s TTL** — the Cloudflare KV minimum; any lower value is silently clamped to 60s) acts as a cross-instance circuit breaker before KV session deletion propagates globally.
- **User experience**: Clear messaging: `"Your Spotify session has expired. Please sign in again."` (avoiding technical jargon like "token invalid_grant").
- **PKCE State Ephemerality**: OAuth PKCE state (`oauth_state:${state}`) is stored in `CACHE_KV` with a 10-minute TTL and deleted immediately upon callback completion (`routes/auth.ts:102`). No orphaned PKCE state exists during mid-session token refresh failures.
- **Backward Compatibility**:
  - Existing backend KV sessions lacking newer fields will still fail safely with standard 401s.
  - Older frontend clients connecting to the updated backend will receive `code: 'AUTH_REQUIRED'`, but will safely fall back to generic 401 handling without crashing.
- **Startup validation gap**: Resolved in Step 11 by querying authenticated `GET /auth/me` on startup instead of unauthenticated `health_check()`. Transport errors (backend offline) are treated as graceful degradation — the cached token is preserved and the user is taken to the main screen.
- **Rollout window race (acceptable transient risk):** During the deployment window, old Worker instances that have not yet picked up the new code will throw a plain `HTTPException(401)` on `invalid_grant` without writing the `REFRESH_FAILED` negative cache key. This means cross-instance protection is absent for in-flight requests until all instances restart. This is acceptable given Cloudflare's fast Worker propagation, but it is worth noting so on-call teams are not surprised by brief `AUTH_REQUIRED` gaps during rollout.

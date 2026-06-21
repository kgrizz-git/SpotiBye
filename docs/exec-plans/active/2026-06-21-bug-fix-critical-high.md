# Fix Critical & High Bugs — 2026-06-21 Audit

> **Source audit:** [dev-docs/bug-review-2026-06-21-183947.md](../../dev-docs/bug-review-2026-06-21-183947.md)
> **Scope:** 14 findings (4 critical, 10 high) across backend TypeScript and frontend Python.
> **Verification:** `./scripts/verify-all.sh` after each step group.

---

## Backend — Critical

### BT-1: Fix JWT expiration bypass (BE-SEC-1)

- [ ] **File:** `src/backend/services/jwt.ts` ~line 65
  - Replace `if (decodedPayload.exp && decodedPayload.exp < now)` with explicit undefined check: `if (decodedPayload.exp === undefined || decodedPayload.exp < now)`
  - Ensures a forged JWT with `exp: 0` is rejected instead of accepted.
- [ ] **Test:** `src/backend/tests/spotify-auth.test.ts` — add a test case where `exp` is `0` and verify rejection.

### BT-2: Fix Retry-After NaN busy spin (BE-LOG-1)

- [ ] **File:** `src/backend/services/spotify.ts` ~line 149
  - Parse `Retry-After` header properly: if header is all digits, `parseInt`; if a date string, compute seconds until that date minus `Date.now()`.
  - Fallback to `1` second if parsing fails entirely.
- [ ] **Test:** `src/backend/tests/spotify-service.test.ts` — add cases for numeric delay, date-string delay, and missing header fallback.

---

## Backend — High

### BT-3: Close OAuth open redirect (BE-SEC-3)

- [ ] **File:** `src/backend/routes/auth.ts` ~line 14-16
  - Validate `redirect_uri` against a configured allowlist. Add `ALLOWED_REDIRECT_URIS` to `Env` bindings (comma-separated in `wrangler.toml`). Reject any URI not in the allowlist with 400.
- [ ] **File:** `src/backend/types/env.ts` — add `ALLOWED_REDIRECT_URIS: string`.
- [ ] **File:** `src/backend/wrangler.toml` — add `ALLOWED_REDIRECT_URIS` var (dev: `http://localhost:8080`, prod: actual domain).
- [ ] **File:** `src/backend/.env.test` — add test value.
- [ ] **Test:** `src/backend/tests/auth.test.ts` — verify disallowed URI is rejected, allowed URI proceeds.

### BT-4: Add structured error logging to silent catch blocks (BE-ERR-1)

- [ ] **File:** `src/backend/routes/auth.ts` ~lines 39, 181, 191
  - Change each `catch {` to `catch (err) {` so the error object is available.
  - Add `console.error('OAuth init error:', err)` in the OAuth init catch.
  - Add `console.error('Logout error:', err)` in the logout catch.
  - Add `console.error('User info error:', err)` in the user info catch.

### BT-5: Wrap markFailed in try/catch inside queue consumer (BE-LOG-5, BE-ERR-4)

- [ ] **File:** `src/backend/index.ts` ~lines 78-87
  - Wrap the `await jobService.markFailed(body, error)` call in its own try/catch. Log the error and always `message.ack()` so the queue doesn't retry past `max_retries`.
- [ ] **Test:** `src/backend/tests/analysis-queue.test.ts` — verify message is acked even when `markFailed` throws.

### BT-6: Preserve error response body on non-429 Spotify errors (BE-LOG-2)

- [ ] **File:** `src/backend/services/spotify.ts` ~lines 154-155
  - Read the response body before throwing: `const body = await response.text(); throw new Error(\`HTTP ${response.status}: ${body}\`);`
- [ ] **Test:** `src/backend/tests/spotify-service.test.ts` — verify non-429 error message includes body text.

### BT-7: Stop storing raw PII in KV session (BE-SEC-2)

> The `spotify_data` field is written to KV once in the OAuth callback but never read back anywhere — the auth middleware and `/auth/me` endpoint derive user context entirely from the JWT. Remove the field.

- [ ] **File:** `src/backend/routes/auth.ts` ~line 97 — remove the `spotify_data: userProfile` line from the `SESSIONS_KV.put` payload.
- [ ] **File:** `src/backend/types/auth.ts` ~line 26 — remove the `spotify_data: any;` field from `SessionData` (or keep as optional empty for backward compat with in-flight sessions).
- [ ] **File:** `src/backend/tests/` — remove `spotify_data` from session mock objects in `api-coverage.test.ts:41`, `export-performance.test.ts:36`, and any other test that populates it.

### BT-8: Fix `c: any` in shared playlist items handler (BE-TYPE-1)

- [ ] **File:** `src/backend/routes/spotify.ts` ~line 132
  - Replace `c: any` with `c: Context<{ Bindings: Env; Variables: Variables }>` (import `Context` from `'hono'` and `Variables` from `types/variables.ts`).
  - Ensure all `c.req.param`, `c.get`, and `c.env` access is type-checked after the change.

---

## Frontend — Critical

### FT-1: Remove hardcoded ReccoBeats test data and wire real backend cache (FE-CRIT-1)

- [ ] **File:** `src/frontend/services/reccobeats_backend.py` ~lines 207-209
  - Remove the hardcoded `if spotify_id in ["cached_track_1", "cached_track_2"]` block and its fake return values.
  - Either: implement actual backend cache lookup via `self.backend_client.get_track_audio_features(track_id)` in a loop, OR raise `NotImplementedError` and update callers to handle the absence gracefully.
- [ ] **Verify:** search for all callers of `get_multiple_track_audio_features` and `get_multiple_track_audio_features_safe` to confirm they handle empty/error results.

### FT-2: Replace hardcoded dev backend URL with localhost default (FE-CRIT-2)

- [ ] **File:** `src/frontend/config/backend_config.py` ~lines 12-14
  - Change default `BACKEND_URL` from `"https://spotibye-backend-development.kevin-grizzard.workers.dev"` to `"http://localhost:8787"`.
  - Keep env var override (`SPOTIBYE_BACKEND_URL`) so users can still point to a deployed worker.

---

## Frontend — High

### FT-3: Fix playlist tracks response shape crash (FE-HIGH-1)

- [ ] **File:** `src/frontend/services/backend_client.py` ~lines 253-256
  - Add a type guard for the response value before calling `.get()`:
    ```python
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        return response.get("items", response.get("tracks", []))
    return []
    ```

### FT-4: Fix filename suffix increment for digit-ending names (FE-HIGH-2)

- [ ] **File:** `src/frontend/screens/main_screen_filenames.py` ~lines 52-61
  - The current `endswith("_2")` through `"_5"` chain corrupts names whose base legitimately ends in a digit (e.g. `song_14.xlsx` → `song_1_5.xlsx`, `song_35.xlsx` → silent no-op).
  - Replace with a regex that parses the *trailing* `_N` suffix (anchored before the extension), checks if it's in the `_2`–`_4` range, and increments within `_2`–`_5`. If no suffix or outside range, append `_2`.
  - Keep the function as pure string manipulation (no filesystem lookup — out of scope for the current signature).
  - Example behavior:
    - `song.xlsx` → `song_2.xlsx`
    - `song_2.xlsx` → `song_3.xlsx`
    - `song_4.xlsx` → `song_5.xlsx`
    - `My_Playlist_2026.xlsx` → `My_Playlist_2026_2.xlsx` (the `_2026` is not recognized as a suffix, so `_2` is appended safely)
    - `song_14.xlsx` → `song_14_2.xlsx` (same reasoning)
- [ ] **Test:** `src/frontend/tests/test_main_screen_filenames.py` — add cases for digit-ending basenames, plain names, and existing suffix in range.

### FT-5: Deduplicate cache path hashing logic (FE-HIGH-3)

- [ ] **File:** `src/frontend/caching/backend_cache.py`
  - Extract a private helper `_cache_file_path(filename: str) -> Path` that computes the env-hashed prefix + cache dir + filename.
  - Refactor `_load_cache_file`, `_save_cache_file`, `_is_cache_valid`, and `clear_active_export_job` to use this helper.
  - Verify `clear_active_export_job` reads and writes the same file that `cache_active_export_job` creates.

### FT-6: Fix/remove dead cache stats method (FE-HIGH-4)

- [ ] **File:** `src/frontend/caching/backend_cache.py` ~lines 426-436
  - `_get_basic_cache_stats` is dead code (never called) and its inner check `isinstance(cached_data, list)` always fails because cache files use `{"data": [...], ...}` format.
  - Either: delete the method entirely, OR fix the format check (`cached_data.get("data", [])`) and wire it to a live caller.

---

## Verification

- [ ] Run `./scripts/verify-all.sh` from repo root — must pass with zero errors.
- [ ] Run backend tests: `cd src/backend && npm run test:run && npm run lint`
- [ ] Run frontend tests: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`

---

## Links

- **Bug assessment:** [dev-docs/bug-review-2026-06-21-183947.md](../../dev-docs/bug-review-2026-06-21-183947.md)
- **TODO entry:** [dev-docs/TO_DO.md](../../dev-docs/TO_DO.md) (see "Fix critical/high bugs from 2026-06-21 audit")

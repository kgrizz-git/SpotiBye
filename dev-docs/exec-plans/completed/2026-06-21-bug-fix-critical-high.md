# Fix Critical & High Bugs — 2026-06-21 Audit

> **Source audit:** [dev-docs/bug-review-2026-06-21-183947.md](../../dev-docs/bug-review-2026-06-21-183947.md)
> **Scope:** 14 findings (4 critical, 10 high) across backend TypeScript and frontend Python.
> **Verification:** `./scripts/verify-all.sh` after each step group.
> **Sister plan:** [Medium & Low bugs](./2026-06-21-bug-fix-medium-low.md) — `FL-1` depends on the `_cache_file_path` helper introduced by **FT-5**, so finish FT-5 first.
> **Related plan:** [2026-06-21-reccobeats-wiring.md](./2026-06-21-reccobeats-wiring.md) — owns the broader ReccoBeats pipeline. FT-1 should defer to that plan's wiring approach (see "Open questions" below) rather than reinventing a per-track HTTP loop.

## Pre-flight checklist (do these before BT-1)

- [ ] **CHANGELOG.md** — Per `AGENTS.md`, every user-visible change must be added to `[Unreleased] / Fixed` in the same PR. Pre-populate entries for: exposed dev URL (FT-2), silent OAuth catch blocks (BT-4), PII in KV (BT-7), and the playlist-track fetch crash (FT-3).
- [ ] **Shared backend test env fixture (prep for BT-3)** — Add `tests/helpers/env.ts` exporting `createTestEnv(overrides?: Partial<Env>): Env` that pre-populates `ALLOWED_REDIRECT_URIS: 'http://localhost:3000/callback,http://localhost:3000'` plus the existing `CACHE_KV` / `SESSIONS_KV` / `ANALYSIS_QUEUE` mocks. **Refactor ALL 14 inline `mockEnv`/`envWithKv`/`testEnv` definitions across the test suite, not just the 8 files with OAuth calls** — adding `ALLOWED_REDIRECT_URIS` to the `Env` interface breaks `npx tsc --noEmit` in every file that has an inline mock. Confirmed files: `analysis-queue.test.ts`, `analysis.test.ts`, `api-coverage.test.ts`, `auth-flow.test.ts`, `auth.test.ts`, `caching.test.ts`, `export-performance.test.ts`, `export.test.ts`, `integration.test.ts`, `kv-setup.test.ts`, `performance.test.ts`, `spotify.test.ts`, `workers-limits.test.ts`, `workflows.test.ts`. Verify with `cd src/backend && npx tsc --noEmit` after the refactor.
- [ ] **`src/backend/.env.test`** — add `ALLOWED_REDIRECT_URIS=http://localhost:3000/callback,http://localhost:3000` (the comma-separated form the plan specifies). Note: this is loaded by `setup.ts` but inline `mockEnv` objects ignore it, so the shared fixture above is the real fix.
- [ ] **Coordinate with [2026-06-21-reccobeats-wiring.md](./2026-06-21-reccobeats-wiring.md) on FT-1** before starting — see open question Q-1.

## Open questions to resolve before starting

- **Q-1 (FT-1, ReccoBeats cache removal).** The plan offers two options: (a) raise `NotImplementedError`, or (b) loop over `get_track_audio_features` per track. Option (b) is N HTTP requests and would be slow for large playlists. **Decision: pick (a) — raise `NotImplementedError` — and let the active ReccoBeats wiring plan replace this method end-to-end. Do not implement option (b) here.** This avoids duplicate effort and a known-slow code path.
- **Q-2 (BT-3, dev allowlist port).** The plan picks `http://localhost:8080` (matching `OAUTH_CALLBACK_PORT` in `src/frontend/config/backend_config.py:43`), but 6 existing test files post `redirect_uri: 'http://localhost:3000/callback'` or `http://localhost:3000`. Two viable choices: (a) include both ports in the dev allowlist (`http://localhost:3000,http://localhost:3000/callback,http://localhost:8080`) so existing tests pass unchanged, or (b) update every test fixture to port 8080. **Recommended: (a) — include both. The allowlist is for OAuth `redirect_uri`, and the test fixtures are not testing port semantics.**
- **Q-3 (BT-7, in-flight sessions).** Removing `spotify_data` from the `SessionData` type is safe for the type system (the field was never read), but if any live KV entries still contain it the JSON parse will just ignore the extra field. Confirm no production deployments are running with sessions that need migration (likely a no-op since the field was unread). If in doubt, keep `spotify_data?: unknown` on the type and only stop *writing* it — full removal can land later.
- **Q-4 (FT-2, production backend still points to placeholder).** Changing `BACKEND_URL` to `http://localhost:8787` fixes the dev leak, but `PRODUCTION_BACKEND_URL` at `src/frontend/config/backend_config.py:17` still defaults to `https://spotibye-api.your-domain.com` (placeholder). The `USE_PRODUCTION` toggle exists but is never set true in the shipped binary. Out of scope for this plan, but worth flagging for the medium-low plan (FE-MED-2) or a follow-up.
- **Q-5 (BT-3, production allowlist value).** The plan suggests `https://app.spotibye.com` as a placeholder for `[env.production.vars]`. Confirm the actual production frontend domain before merging — this is a security-sensitive value.

---

## Backend — Critical

### BT-1: Fix JWT expiration bypass (BE-SEC-1)

- [ ] **File:** `src/backend/services/jwt.ts` ~line 65
  - Replace `if (decodedPayload.exp && decodedPayload.exp < now)` with explicit undefined check: `if (decodedPayload.exp === undefined || decodedPayload.exp < now)`
  - Ensures a forged JWT with `exp: 0` is rejected instead of accepted.
- [ ] **Test:** `src/backend/tests/jwt.test.ts` (create if needed) — add a test case where `exp` is `0` and verify rejection.

### BT-2: Fix Retry-After NaN busy spin (BE-LOG-1)

- [ ] **File:** `src/backend/services/spotify.ts` ~line 149
  - Parse `Retry-After` header properly: if header is all digits, `parseInt`; if a date string, compute seconds until that date minus `Date.now()`.
  - Fallback to `1` second if parsing fails entirely.
- [ ] **Test:** `src/backend/tests/spotify-service.test.ts` — add cases for numeric delay, date-string delay, and missing header fallback.

---

## Backend — High

### BT-3: Close OAuth open redirect (BE-SEC-3)

> **Test fallout (apply the pre-flight shared fixture first).** Adding `ALLOWED_REDIRECT_URIS: string` to `Env` will break `npx tsc --noEmit` in every test file with an inline `mockEnv: Env` object until those mocks include the new field. After the pre-flight fixture is in place, search for the inline mocks and confirm they route through `createTestEnv()`. The following files currently post OAuth requests with a `redirect_uri` and will need the new allowlist entry to keep passing:
>
> | File | Line | `redirect_uri` value |
> |------|------|----------------------|
> | `src/backend/tests/auth.test.ts` | 85 | `http://localhost:3000/callback` |
> | `src/backend/tests/auth.test.ts` | 102 | (assertion only) |
> | `src/backend/tests/auth.test.ts` | 123 | (mocked `CACHE_KV.get` for callback — unaffected by allowlist) |
> | `src/backend/tests/auth-flow.test.ts` | 65, 81 | `http://localhost:3000/callback` |
> | `src/backend/tests/performance.test.ts` | 58, 80, 121, 147 | `http://localhost:3000` |
> | `src/backend/tests/api-coverage.test.ts` | 210, 276 | `http://localhost:3000/callback` / `http://localhost:3000` |
> | `src/backend/tests/integration.test.ts` | 48 | `http://localhost:3000/callback` |
> | `src/backend/tests/workflows.test.ts` | 36, 93, 195 | `http://localhost:3000/callback` / `http://localhost:3000` |
>
> Per Q-2, recommended dev allowlist: `http://localhost:3000,http://localhost:3000/callback,http://localhost:8080` (or whatever ports the existing tests need).

- [ ] **File:** `src/backend/routes/auth.ts` ~line 14-16
  - Validate `redirect_uri` against a configured allowlist. Add `ALLOWED_REDIRECT_URIS` to `Env` bindings as a **comma-separated string** (e.g., `"http://localhost:8080,https://app.spotibye.com"`), split on `,` and trim whitespace at use site.
  - Reject any URI not in the allowlist with HTTP 400 + `{ error: { code: 'DISALLOWED_REDIRECT_URI', message: '...' } }`. **Do not leak the requested URI in the error message** — keep the message generic.
  - Exact-match comparison is sufficient (no subdomain wildcards) — keeps the allowlist auditable.
  - Place the check after the `if (!redirect_uri)` block on line 16-18, before the `SpotifyAuthService` instantiation on line 20.
- [ ] **File:** `src/backend/types/env.ts` — add `ALLOWED_REDIRECT_URIS: string;` to the `Env` interface.
- [ ] **File:** `src/backend/wrangler.toml` — add `ALLOWED_REDIRECT_URIS` to the top-level `[vars]` and to each `[env.*.vars]` block. Dev: see Q-2 (include test ports). Production: actual frontend domain (e.g., `https://app.spotibye.com` — confirm per Q-5).
- [ ] **File:** `src/backend/.env.test` — add `ALLOWED_REDIRECT_URIS=http://localhost:3000,http://localhost:3000/callback,http://localhost:8080` (loaded by `setup.ts`, but inline mocks ignore it — rely on the shared fixture).
- [ ] **Test:** `src/backend/tests/auth.test.ts` — verify:
  - Disallowed URI is rejected with 400 `DISALLOWED_REDIRECT_URI`
  - Allowed URI proceeds
  - Empty/missing `ALLOWED_REDIRECT_URIS` env var rejects all (fail-closed default)
  - Whitespace-padded allowlist entries (`" http://localhost:3000 "`) are trimmed correctly

### BT-4: Add structured error logging to silent catch blocks (BE-ERR-1)

> **`console.error` is the correct choice here.** Golden Principle #5 (`dev-docs/guides/golden-principles.md:53`) explicitly permits `console.error` and `console.warn` in catch blocks "where a proper logger is unavailable." The codebase has no structured logger today, and `console.error` is already the established pattern in `index.ts:79` and `middleware/auth.ts:52`. A future plan can introduce a structured logger and migrate these calls; for now, follow the existing pattern.

- [ ] **File:** `src/backend/routes/auth.ts` — four silent catches, not three:
  - Line 39 (OAuth init) — change `catch {` to `catch (err) {`; add `console.error('OAuth init error:', err)`.
  - Line 72 (OAuth callback state JSON parse fallback) — same change; add `console.error('OAuth callback state parse error, falling back to bare string:', err)`. (The plan originally missed this one; same anti-pattern as the others.)
  - Line 181 (logout) — same change; add `console.error('Logout error:', err)`.
  - Line 191 (user info) — same change; add `console.error('User info error:', err)`.

### BT-5: Wrap markFailed in try/catch inside queue consumer (BE-LOG-5, BE-ERR-4)

- [ ] **File:** `src/backend/index.ts` ~lines 78-87
  - Wrap the `await jobService.markFailed(body, error)` call in its own try/catch. Log the error and always `message.ack()` so the queue doesn't retry past `max_retries`.
- [ ] **Test:** `src/backend/tests/analysis-queue.test.ts` — verify message is acked even when `markFailed` throws.

### BT-6: Preserve error response body on non-429 Spotify errors (BE-LOG-2)

- [ ] **File:** `src/backend/services/spotify.ts` ~lines 154-155
  - Read the response body before throwing: `const body = await response.text(); throw new Error(\`HTTP ${response.status}: ${body}\`);`
- [ ] **Test:** `src/backend/tests/spotify-service.test.ts` — verify non-429 error message includes body text.

### BT-7: Stop storing raw PII in KV session (BE-SEC-2)

> The `spotify_data` field is written to KV once in the OAuth callback but never read back anywhere — the auth middleware and `/auth/me` endpoint derive user context entirely from the JWT. Remove the field. Per Q-3, prefer the "stop writing + keep type as optional" path on the first pass to avoid any risk with in-flight sessions.

- [ ] **File:** `src/backend/routes/auth.ts` ~line 97 — remove the `spotify_data: userProfile` line from the `SESSIONS_KV.put` payload.
- [ ] **File:** `src/backend/types/auth.ts` ~line 26 — change `spotify_data: any;` to `spotify_data?: unknown;` (keeps the type honest while preventing future writers from accidentally storing PII again). Follow up by removing the field entirely in a later plan once any in-flight sessions have aged out.
- [ ] **File:** `src/backend/tests/` — remove `spotify_data` from session mock objects in `api-coverage.test.ts:41`, `export-performance.test.ts:36`, `analysis.test.ts:280`, `export.test.ts:206`, `spotify.test.ts:99` (verified: 5 occurrences total). Keep the KV `get` mock returning JSON without the field to confirm callers tolerate its absence.

### BT-8: Fix `c: any` in shared playlist items handler (BE-TYPE-1)

> **Imports verified:** `src/backend/types/variables.ts` exists and exports `Variables` (10 lines, no aliases). `src/backend/routes/spotify.ts:8` already imports `type { Variables } from '../types/variables'`, so only the `Context` import from `'hono'` needs to be added. `Context` is already imported in `middleware/auth.ts:1`.

- [ ] **File:** `src/backend/routes/spotify.ts` ~line 132
  - Replace `c: any` with `c: Context<{ Bindings: Env; Variables: Variables }>` (add `Context` to the existing `import { Hono } from 'hono'` line; `Variables` is already imported at line 8).
  - Ensure all `c.req.param`, `c.get`, and `c.env` access is type-checked after the change.

---

## Frontend — Critical

### FT-1: Remove hardcoded ReccoBeats test data and wire real backend cache (FE-CRIT-1)

> **Decision per Q-1:** take the minimal fix only. The real ReccoBeats wiring is owned by [2026-06-21-reccobeats-wiring.md](./2026-06-21-reccobeats-wiring.md); this task removes the unsafe stub so callers stop getting fake `danceability: 0.8, energy: 0.9` data while the broader plan is in flight.
>
> **Caller update scope — corrected:** `get_multiple_track_audio_features_safe` has exactly **one external caller**: the wrapper `get_multiple_track_audio_features` in the same file (lines 162-176), which is itself unreferenced outside the file (verified via `rg "get_multiple_track_audio_features"` — no hits outside `reccobeats_backend.py`). The `analysis_task.is_cancelled()` check at line 198 is an early-return *inside* the function, not a caller. Since the wrapper just propagates exceptions, raising `NotImplementedError` from the safe method is sufficient — no external caller updates are required. If the wiring plan later wants a different behavior, that plan will introduce its own caller and handle the error.

- [ ] **File:** `src/frontend/services/reccobeats_backend.py` ~lines 207-209
  - Remove the hardcoded `if spotify_id in ["cached_track_1", "cached_track_2"]` block and its fake return values.
  - Replace the entire `try` block with an early `raise NotImplementedError('ReccoBeats per-track cache lookup not implemented; see 2026-06-21-reccobeats-wiring.md')` followed by an empty `results: Dict[str, Dict[str, Any]] = {}` (so the function still type-checks if any caller swallows the exception).
  - **Do NOT implement option (b) (per-track HTTP loop)** — slow for large playlists and duplicates work in the wiring plan.
  - **No external caller updates required** — the wrapper method `get_multiple_track_audio_features` (line 162) propagates `NotImplementedError` to its caller, and the method has no callers outside this file.
- [ ] **Test:** `src/frontend/tests/test_reccobeats_backend.py` (new file — current tests are in `test_ui.py:10` / `test_performance.py:13` and only construct the service, they don't exercise this method) — assert:
  - The hardcoded `cached_track_1`/`cached_track_2` branch is gone
  - Calling with any real track ID raises `NotImplementedError`
  - Calling with `cached_track_1` (a real-looking ID) does not return `danceability: 0.8, energy: 0.9`

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
  - Note: `_make_request` (line 143) unwraps `{"data": ...}` to bare values, so response can legitimately be a list (e.g., raw items), a dict (`NormalizedPlaylistItemsResponse` with `items`/`total`/`rawCount`/`href`), or neither (unexpected shape).
- [ ] **Test:** `src/frontend/tests/test_cache.py` or a new test file — cover three response shapes:
  - `_make_request` returns a list → method returns the list unchanged
  - `_make_request` returns a dict with `items` key → method returns the `items` list
  - `_make_request` returns a dict without `items`/`tracks` keys → method returns `[]` (defensive)
  - `_make_request` returns `None` or other unexpected type → method returns `[]` without raising `AttributeError`

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

> **Downstream dependency:** [2026-06-21-bug-fix-medium-low.md](./2026-06-21-bug-fix-medium-low.md) `FL-1` explicitly relies on this `_cache_file_path` helper to fix `clear_cache("playlists.json")` in `backend_main_screen_adapter.py:1041-1048`. **Finish FT-5 before starting the medium-low plan.**

- [ ] **File:** `src/frontend/caching/backend_cache.py`
  - Extract a private helper `_cache_file_path(filename: str) -> Path` that computes the env-hashed prefix + cache dir + filename.
  - Refactor `_load_cache_file` (line 314), `_save_cache_file` (line 350), `_is_cache_valid` (line 364), and `clear_active_export_job` (line 258) to use this helper.
  - Verify `clear_active_export_job` reads and writes the same file that `cache_active_export_job` creates.
  - Confirm `_atomic_write_cache_file` (line 282) still receives the correct `cache_path` argument after the refactor (it currently takes a `Path`, not a `filename`).
- [ ] **Test:** `src/frontend/tests/test_resumable_export_cache.py` (existing file per `ls src/frontend/tests/`) — add cases for:
  - `_cache_file_path("playlists.json")` returns the same path that `_load_cache_file("playlists.json")` would consume
  - Different `backend_url` env settings produce different hashed paths
  - `clear_active_export_job` removes the file created by `cache_active_export_job`

### FT-6: Fix/remove dead cache stats method (FE-HIGH-4)

- [ ] **File:** `src/frontend/caching/backend_cache.py` — method starts at **line 414** (the `~lines 426-436` reference in the original plan pointed into the middle of the function body, not its bounds). The full method spans lines 414-456.
  - `_get_basic_cache_stats` is dead code (never called) and its inner check `isinstance(cached_data, list)` always fails because cache files use `{"data": [...], ...}` format.
  - **Recommended: delete the method entirely.** Wiring it to a live caller is out of scope for this audit-driven plan and risks a new dependency chain. The dead-code removal is the lower-risk fix.
  - If a future plan needs cache stats, add a new method that correctly reads the `{"data": [...]}` envelope.

---

## Verification

- [ ] Run `./scripts/verify-all.sh` from repo root — must pass with zero errors.
- [ ] Run backend tests: `cd src/backend && npm run test:run && npm run lint`
- [ ] Run frontend tests: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
- [ ] Confirm `CHANGELOG.md` has an entry under `[Unreleased] / Fixed` for each user-visible change (FT-2, BT-4, BT-7, FT-3 at minimum).
- [ ] Confirm the dev-docs `TO_DO.md` "Fix critical/high bugs" item is updated (and remains linked to this plan until completed, per the plan-hygiene rules in `AGENTS.md`).
- [ ] After the plan is fully executed, move this file to `dev-docs/exec-plans/completed/` and add a row to `dev-docs/exec-plans/completed/README.md` (per `AGENTS.md` "Plans and Documentation Conventions").

---

## Links

- **Bug assessment:** [dev-docs/bug-review-2026-06-21-183947.md](../../dev-docs/bug-review-2026-06-21-183947.md)
- **TODO entry:** [dev-docs/backlog/TO_DO.md](../../dev-docs/backlog/TO_DO.md) (see "Fix critical/high bugs from 2026-06-21 audit")

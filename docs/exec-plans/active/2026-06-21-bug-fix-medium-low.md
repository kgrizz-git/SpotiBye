# Fix Medium & Low Bugs — 2026-06-21 Audit

> **Source audit:** [dev-docs/bug-review-2026-06-21-183947.md](../../dev-docs/bug-review-2026-06-21-183947.md)
> **Scope:** 36 remaining findings: 21 in backend TypeScript (11 medium, 10 low); 15 in frontend Python (6 medium, 9 low).
> **Sister plan:** [Critical & High bugs](./2026-06-21-bug-fix-critical-high.md) — finish that first.
> **Coordination:** Several `export.ts` items (BE-TYPE-2, BE-LOG-6, BE-LOG-7, BE-API-3) overlap with the active [2026-06-21 Refactor export.ts](./2026-06-21-refactor-export-ts.md) plan. Apply the type-safety fixes inside the new modules during the split rather than re-touching the monolithic file.
> **Dependency Note:** Line numbers for items in `src/backend/routes/auth.ts`, `src/backend/services/spotify.ts`, and `src/frontend/services/backend_client.py` will have shifted slightly due to insertions from the Critical & High plan (BT-3, BT-4, BT-7, FT-3). FL-1 and FL-9 explicitly rely on the `_cache_file_path` helper introduced by FT-5.
> **Verification:** `./scripts/verify-all.sh` after each step group.

---

## Backend — Medium

### BM-1: Stop silently dropping rotated refresh tokens (BE-SEC-4)

- [ ] **File:** `src/backend/services/spotify-auth.ts` ~line 102 and `src/backend/routes/auth.ts` ~line 143
  - Define a `SpotifyTokenResponse` interface with the real fields (`access_token`, `refresh_token?`, `expires_in`, `token_type`, `scope`).
  - Replace `(newTokens as any).refresh_token` with the typed field. If the response includes a rotated refresh token, persist it back to the session KV entry.

### BM-2: Validate individual playlist items, not just top-level (BE-SEC-5)

- [ ] **File:** `src/backend/services/spotify.ts` ~line 52
  - After the top-level `parseSpotifyResponse` call, run each entry in `rawData.items` through a `parsePlaylistItem` validator that requires `id`, `name`, `track`, and `owner` shape (use existing `SpotifyPlaylist` type or a new `SpotifyPlaylistItem` type).
  - Log a warning and drop items that fail validation rather than returning a malformed record.
- [ ] **Test:** `src/backend/tests/spotify-service.test.ts` — add case where one item in `items[]` is missing `id` and verify it is dropped.

### BM-3: Eliminate stale-snapshot progress writes (BE-LOG-4)

- [ ] **File:** `src/backend/services/analysis-job.ts` ~lines 70-78
  - Inside the progress callback, fetch the latest KV status (e.g. `await this.cache.get(statusKey)`) to merge the new progress instead of closing over the initial `current` snapshot from the start of the job.
  - While KV replication is still eventual, this significantly reduces the race window compared to holding a 5-minute old snapshot.
- [ ] **Test:** `src/backend/tests/analysis-job.test.ts` — concurrent progress updates do not lose fields.

### BM-4: Remove pervasive `any` from `export.ts` (BE-TYPE-2)

- [ ] **Files:** `src/backend/services/export.ts` — `buildPlaylistMetadata(playlist: any)`, `buildExportTracks(allTracks: any[])`, and 4+ other locations
  - Apply during the [2026-06-21 Refactor export.ts](./2026-06-21-refactor-export-ts.md) split. Each new module (`export-types.ts`, `export-tracks.ts`, etc.) must be fully typed.
  - If the refactor plan completes first, do a follow-up sweep on the resulting modules.

### BM-5: Remove pervasive `any` from `routes/export.ts` (BE-TYPE-3)

- [ ] **File:** `src/backend/routes/export.ts` — `resolveStepSize(body: any)` and 7+ other locations
  - Define a `ExportRequestBody` Zod schema (or hand-rolled type guard) for each endpoint and parse with Hono's `c.req.valid('json')` validator.
  - Remove every `body: any` parameter; replace with the validated type.

### BM-6: Replace double `as unknown as T` casts (BE-TYPE-5)

- [ ] **File:** `src/backend/services/spotify.ts` ~lines 109, 116, 135
  - For each cast, introduce a typed wrapper that performs a runtime shape check (e.g., `function asPlaylistMeta(x: unknown): PlaylistMeta`).
  - Replace `as unknown as T` with the wrapper.

### BM-7: Surface actual OAuth callback error messages (BE-ERR-2)

- [ ] **File:** `src/backend/routes/auth.ts` ~lines 117-120
  - Return the real `error_description` from Spotify (or a mapped error code) to the client in the JSON body.
  - Keep HTTP status 400 but include a structured `{ error: 'oauth_failed', reason: <string> }` payload.

### BM-8: Wrap `JSON.parse(sessionData)` in try/catch (BE-ERR-3)

- [ ] **File:** `src/backend/middleware/auth.ts` ~line 30
  - Wrap the `JSON.parse` call in try/catch. On failure, log the error with the session id (truncated) and treat the session as missing — clear the cookie and return 401.

### BM-9: Reject empty Spotify credentials at construction (BE-ERR-5)

- [ ] **File:** `src/backend/services/spotify-auth.ts` ~lines 9-11
  - In the constructor, throw `Error('Spotify clientId and clientSecret are required')` if either is empty.
  - Add a unit test verifying the throw.

### BM-10: Serialize concurrent token refresh (BE-RACE-1)

- [ ] **File:** `src/backend/middleware/auth.ts` ~lines 33-54
  - Coalesce concurrent refreshes for the same session by storing an in-flight `Promise<TokenSet>` in a module-level `Map<string, Promise<...>>`.
  - Subsequent callers awaiting the same key share the result. Evict the entry on success/failure.
- [ ] **Test:** `src/backend/tests/auth-middleware.test.ts` — fire two refreshes in parallel, assert only one network call to Spotify.

### BM-11: Promote `no-explicit-any` to error (BE-API-4)

> Do this **after** BM-4, BM-5, and BM-6 are complete, so the existing `any` usages are already fixed.

- [ ] **File:** `src/backend/.eslintrc.json` ~line 18
  - Change `"no-explicit-any": "warn"` to `"no-explicit-any": "error"` (with an allowlist comment for legitimate `unknown`-interop cases).
  - File follow-up tasks for any remaining `any` usages exposed by the stricter rule.

---

## Backend — Low

### BL-1: Handle local-only-track pagination edge case (BE-LOG-3)

- [ ] **File:** `src/backend/services/analysis.ts` ~line 110
  - When a page contains only `track: null` (local/unavailable) items, treat it as a soft-empty page and continue. Currently the pagination loop may early-exit or under-count.
  - Add a regression test with a page of 100% local items.

### BL-2: Guard `undefined` playlist in `buildPlaylistMetadata` (BE-LOG-6)

- [ ] **File:** `src/backend/services/export.ts` ~lines 522-528
  - Apply during the [2026-06-21 Refactor export.ts](./2026-06-21-refactor-export-ts.md) split. `buildPlaylistMetadata` must require a non-null `playlist` argument (signature change to `playlist: Playlist`) and the caller must pass a validated value.
  - Add a unit test for the call site ensuring it never passes `undefined`.

### BL-3: Reconcile Buffer detection (BE-LOG-7)

- [ ] **File:** `src/backend/services/export.ts` ~line 1106
  - Replace the inline `Buffer.isBuffer(...)` / `globalThis.Buffer` check with a single `isNodeBuffer(x: unknown): boolean` helper in `src/backend/utils/buffer.ts` that works in both runtimes.
  - Apply consistently across the codebase.

### BL-4: Drop redundant `as JWTPayload` cast (BE-TYPE-4)

- [ ] **File:** `src/backend/middleware/auth.ts` ~line 22
  - Remove the `as JWTPayload` annotation. The wrapped function already returns the correct type.

### BL-5: Address KV replication race in analysis job (BE-RACE-2)

- [ ] **File:** `src/backend/services/analysis-job.ts` ~lines 38-44
  - Increase the post-write settle wait from 15s to 30s (simpler than a deferred re-read). Document the 30s choice with a comment explaining the KV replication latency tradeoff.
  - Add a metric/log line so the race is observable in production traces.

### BL-6: Delete unreachable error branches (BE-DEAD-1)

- [ ] **File:** `src/backend/middleware/error.ts` ~lines 26-42
  - Remove the branches for `ValidationError`, `UnauthorizedError`, `NotFoundError`, `RateLimitError` — none are thrown anywhere in the codebase.
  - Replace with a single `Error` fallback that logs and returns 500.

### BL-7: Remove dead `calculateAverageAudioFeatures` (BE-DEAD-2)

- [ ] **File:** `src/backend/services/analysis.ts` ~lines 334-354
  - Delete the function. Confirmed no callers via `rg calculateAverageAudioFeatures`.

### BL-8: Wrap health-check response in `data` envelope (BE-API-1)

> Overlaps with FM-5 (same `health_check` client code). Coordinate: change backend shape first, then update the client.

- [ ] **File:** `src/backend/index.ts` ~lines 28-34
  - Update `/health` to return `{ data: { status, service, timestamp } }` for consistency with the rest of the API.
- [ ] **File:** `src/frontend/services/backend_client.py` ~lines 500-505 (handled by FM-5)
  - Update the frontend health-check consumer to read the new `data` envelope.

### BL-9: Remove duplicate `token`/`access_token` in refresh response (BE-API-2)

- [ ] **File:** `src/backend/routes/auth.ts` ~lines 161-163
  - Return only `access_token` (the canonical name). Keep `expires_in` and `token_type`.
  - Update frontend consumers that read `data.token` to use `data.access_token`.

### BL-10: Remove misleading playlist-fetch guard (BE-API-3)

- [ ] **File:** `src/backend/services/export.ts` ~lines 522-524
  - Apply during the [2026-06-21 Refactor export.ts](./2026-06-21-refactor-export-ts.md) split. Drop the `if (id !== playlist.id)` branch — the invariant should be enforced by the caller.

---

## Frontend — Medium

### FM-1: Remove unused `export_id` from `download_export` (FE-MED-1)

- [ ] **File:** `src/frontend/services/backend_client.py` ~line 392
  - The `download_export` method accepts an `export_id` parameter that is never used. The backend endpoint `/export/playlist/:id/download` only requires the `playlist_id`.
  - Remove `export_id` from the `download_export` signature and update all frontend callers to stop passing it.
  - Ensure the unit test reflects the updated signature.

### FM-2: Decorate `_update_analysis_ui` with `@mainthread` (FE-MED-2)

- [ ] **File:** `src/frontend/ui/backend_playlist_card.py` ~line 557
  - Import `from kivy.clock import mainthread`.
  - Decorate `_update_analysis_ui` with `@mainthread`. Confirm the call site is allowed to be async (or wrap with `Clock.schedule_once`).
- [ ] **Test:** `src/frontend/tests/test_backend_playlist_card.py` — call from a background `threading.Thread` and assert no widget assertion error.

### FM-3: Destroy tkinter root on exception (FE-MED-3)

- [ ] **File:** `src/frontend/utils/platform_utils.py` ~lines 119-129
  - Wrap the `Tk()`/`winfo_*` calls in try/finally. Call `root.destroy()` in the `finally` block.
  - If `Tkinter` is unavailable on the platform, return defaults without ever instantiating `Tk()`.

### FM-4: Consolidate download methods through `_make_request` (FE-MED-4)

- [ ] **File:** `src/frontend/services/backend_client.py` ~lines 392-496
  - Refactor `download_export`, `download_batch_export`, and `download_export_job` to delegate to a single `_download_file` helper that handles retries, timeouts, and JSON error parsing (mirroring `_make_request`).
  - Update or add unit tests for each method.

### FM-5: Broaden `health_check` exception handling (FE-MED-5)

- [ ] **File:** `src/frontend/services/backend_client.py` ~lines 500-505
  - Catch `Exception` (or a tuple including `JSONDecodeError`, `TypeError`, `BackendAPIError`) and return `{"status": "error", "error": str(e)}` so callers can branch on the dict instead of crashing.

### FM-6: Surface missing `logout` method instead of silent no-op (FE-MED-6)

- [ ] **File:** `src/frontend/screens/main_screen_logout.py` ~lines 77-85
  - If the running app lacks a `logout` method, log a warning and raise `RuntimeError` so the failure is visible during testing.
  - Confirm callers handle the exception (the auth flow should already terminate cleanly).

---

## Frontend — Low

### FL-1: Use shared helper to clear prefix-hashed cache file (FE-LOW-1)

- [ ] **File:** `src/frontend/screens/backend_main_screen_adapter.py` ~lines 1041-1048
  - Replace the literal `clear_cache("playlists.json")` call with the same hashing helper used in `clear_active_export_job` (see FT-5 in the critical/high plan).
  - Add a test that pre-populates a hashed file and asserts it is removed.

### FL-2: Tighten `is_valid_backend_url` validation (FE-LOW-2)

- [ ] **File:** `src/frontend/config/backend_config.py` ~lines 151-153
  - After the `startswith` check, attempt `urlparse(value)` and require `scheme in {"http","https"}`, non-empty `netloc`, and that `netloc` contains a `.` or is `localhost`.
  - Add a unit test with `https://not a url!!!`, `https://x`, `ftp://example.com`, and a valid URL.

### FL-3: Simplify `_format_backend_api_error` redundant checks (FE-LOW-3)

- [ ] **File:** `src/frontend/screens/backend_main_screen_adapter.py` ~lines 86-106
  - Reduce the nested `isinstance(details_payload, dict)` checks by extracting a single `_format_details(payload: dict | list | str) -> str` helper.
  - Confirm no behavior change with a snapshot-style test.

### FL-4: Avoid re-importing `LabelBase` inside the inner loop (FE-LOW-4)

- [ ] **File:** `src/frontend/app/backend_app.py` ~lines 206-234
  - Move the `LabelBase` import to module scope (after the outer import guard) or, if the import is intentionally lazy, only attempt it once.
  - Remove the inner-loop import.

### FL-5: Delete identity-function `_build_backend_output_path` (FE-LOW-5)

- [ ] **File:** `src/frontend/screens/main_screen_export.py` ~lines 56-66
  - Remove the `multiple=True` passthrough branch (and the function if the remaining single-file branch is trivial).
  - Update callers to use the underlying helper directly.

### FL-6: Replace `Optional[callable]` with `Optional[Callable[..., Any]]` (FE-LOW-6)

- [ ] **File:** `src/frontend/screens/backend_main_screen_adapter.py` ~lines 34-36
  - Add `Callable` to the existing `typing` import. Change the annotation to `Optional[Callable[..., Any]]`.

### FL-7: Rename custom `TimeoutError` to avoid shadowing the builtin (FE-LOW-7)

- [ ] **Files:** `src/frontend/utils/network_utils.py` ~lines 29-32 and `src/frontend/services/reccobeats_backend.py` ~line 125
  - Rename the custom class to `NetworkTimeoutError` (or `BackendTimeoutError`).
  - Update the `reccobeats_backend.py` `raise` site to use the renamed class so `handle_network_errors` catches it (verify it inherits from `NetworkError` which the handler already catches).
  - Run a project-wide `rg TimeoutError` to find all call sites that need updating.

### FL-8: Log diagnostics on `ImportError` (FE-LOW-8)

- [ ] **File:** `src/frontend/ui/backend_cache_explorer.py` ~lines 21-29
  - Log the exception (or write to a UI status bar) so users see "Backend module unavailable: <error>" instead of the generic message.

### FL-9: Make `clear_all_cache` actually clear the cache (FE-LOW-9)

> Reuse the shared cache-path helper extracted in FT-5 (critical/high plan) to locate and delete cache files.

- [ ] **File:** `src/frontend/screens/main_screen_cache.py` ~lines 66-93
  - Call the actual cache-clear implementation (e.g., `BackendCache.clear_all()`) before showing the success popup. If no clear method exists, raise an explicit error in dev builds and hide the menu item.
  - Add a test that pre-populates a cache file and asserts it is gone after the call.

---

## Verification

- [ ] Run `./scripts/verify-all.sh` from repo root — must pass with zero errors.
- [ ] Run backend tests: `cd src/backend && npm run test:run && npm run lint`
- [ ] Run frontend tests: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
- [ ] Update `CHANGELOG.md` with a "Code quality & hardening" entry covering all 36 findings.
- [ ] Re-run any frontend consumers touched by backend response-shape changes in the same pass (`FM-1`, `FM-5`, `BL-8`, `BL-9`) so the API contract stays consistent.

---

## Links

- **Bug assessment:** [dev-docs/bug-review-2026-06-21-183947.md](../../dev-docs/bug-review-2026-06-21-183947.md)
- **Critical & High plan:** [2026-06-21-bug-fix-critical-high.md](./2026-06-21-bug-fix-critical-high.md)
- **TODO entry:** [dev-docs/TO_DO.md](../../dev-docs/TO_DO.md) (see "Fix medium/low bugs from 2026-06-21 audit")

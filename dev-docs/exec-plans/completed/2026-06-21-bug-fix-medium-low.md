# Fix Medium & Low Bugs — 2026-06-21 Audit

> **Source audit:** [dev-docs/bug-review-2026-06-21-183947.md](../../dev-docs/bug-review-2026-06-21-183947.md)
> **Scope:** Originally 36 findings. **7 resolved prior to execution** (BL-3, BL-5, BL-10 via refactor; BM-3, BM-6 implemented; BM-1 body done, gap only; BM-3 implementation done, tests remain). Active work: ~29 items plus 2 test-only follow-ups (BM-3 tests, BM-1 gap). ✅ **All items complete as of 2026-06-24.**
> **Sister plan:** [Critical & High bugs](../completed/2026-06-21-bug-fix-critical-high.md) — ✅ **Complete as of 2026-06-24.** All pre-flight dependencies are in place.
> **Coordination:** The `export.ts` refactor ([2026-06-21-refactor-export-ts.md](../completed/2026-06-21-refactor-export-ts.md)) is ✅ **complete as of 2026-06-24.** BM-4, BM-5, BL-2, BL-3, BL-10 targets have been updated accordingly — see individual items below.
> **Dependency Note:** Line numbers in `src/backend/routes/auth.ts`, `src/backend/services/spotify.ts`, and `src/frontend/services/backend_client.py` shifted due to the critical-high plan (BT-3, BT-4, BT-7, FT-3). FL-1 and FL-9 rely on `_cache_file_path` (FT-5 — ✅ landed in `src/frontend/caching/backend_cache.py:311`).
> **Verification:** `./scripts/verify-all.sh` after each step group.
> **2nd-agent review:** [tmp/plan_review_2026-06-21_160000.md](../../../tmp/plan_review_2026-06-21_160000.md) — 20 findings, all addressed inline below.
> **3rd-agent review:** [tmp/plan_assessment_2026-06-21_medium_low.md](../../../tmp/plan_assessment_2026-06-21_medium_low.md) — 2 errors + 8 gaps + 4 observations, addressed inline below.
> **4th-agent review:** [tmp/bug-fix-medium-low-assessment.md](../../../tmp/bug-fix-medium-low-assessment.md) — 3 errors + 6 gaps + 2 improvements, addressed inline below.
> **2026-06-24 update:** BL-10 and BL-3 resolved during the export.ts refactor. BM-4 and BL-2 retargeted from `services/export.ts` to `export-tracks.ts`. BM-5 is now unblocked. Pre-flight dependencies confirmed in place.

## Pre-flight Dependencies

All pre-flight dependencies are ✅ confirmed in place as of 2026-06-24:

- **`src/backend/tests/helpers/env.ts` with `createTestEnv()`** — ✅ `src/backend/tests/helpers/env.ts` exists with `createTestEnv` and `TEST_ALLOWED_REDIRECT_URIS`. Required for BM-3 and BM-10 test files.
- **`BackendCacheManager._cache_file_path` helper (FT-5)** — ✅ `src/frontend/caching/backend_cache.py:311`. Required for FL-1 and FL-9.
- **`ALLOWED_REDIRECT_URIS` in `.env.test`** — ✅ `src/backend/types/env.ts:21` has the field; `src/backend/.env.test` should be confirmed at execution time.

---

## Backend — Medium

### BM-1: Stop silently dropping rotated refresh tokens (BE-SEC-4)

> **2026-06-24 update:** Partially done during the critical-high plan. `spotify-auth.ts:109` already returns `Promise<AuthTokenResponse>`, and `routes/auth.ts` already reads `newTokens.refresh_token` directly. **One gap remains:** `services/analysis-job.ts:140` still does `const refreshed = ... as RefreshedToken` using a local `RefreshedToken` interface (lines 15-19) that duplicates `AuthTokenResponse`. The local interface and the cast should be removed.

- [x] **File:** `src/backend/services/analysis-job.ts` — the one remaining gap:
  - Remove the local `RefreshedToken` interface (lines 15-19) — it duplicates `AuthTokenResponse` from `src/backend/types/spotify-api.ts`.
  - At line 140, remove the `as RefreshedToken` cast. `refreshAccessToken` already returns `Promise<AuthTokenResponse>`, so the result is already correctly typed.
  - Import `type { AuthTokenResponse }` from `'../types/spotify-api'` if needed (confirm whether it's already imported).

### BM-2: Validate individual playlist items, not just top-level (BE-SEC-5)

- [x] **File:** `src/backend/services/spotify.ts` (`getUserPlaylists`, currently `~line 52`)
  - Add a new `parsePlaylistItems` validator in `src/backend/types/spotify-api.ts` that, given a raw `items[]`, returns a `SpotifyPlaylist[]` filtered to entries that have a string `id` and a string `name` (the two fields downstream callers actually depend on). Log a warning via `console.warn` (Golden Principle #5) for any dropped item including the index, but never throw — the public endpoint contract is "best effort" and must not 500 the entire response.
  - Replace the bare `rawData.items as SpotifyPlaylist[]` cast with a `parsePlaylistItems(rawData.items)` call. Keep the existing `parseSpotifyResponse<T>(rawData, ['items', 'total'])` top-level assertion for shape safety.
- [x] **Test:** `src/backend/tests/spotify-service.test.ts` — add cases: (1) one item missing `id` is dropped and a warning is logged, (2) all items invalid returns `[]` (does not throw), (3) all items valid returns the full array.

### BM-3: Eliminate stale-snapshot progress writes (BE-LOG-4) — ✅ RESOLVED

> **2026-06-24:** Fully implemented. `writeStatusMerged` exists at `analysis-job.ts:159-169`, fetches the latest KV snapshot before every write, and adds `updated_at: new Date().toISOString()`. All three previously-stale sites (progress callback lines 74-80, completion write line 84, retry write line 93) now call `writeStatusMerged`. `updated_at?: string` is in `AnalysisStatusRecord` at `analysis-queue.ts:30`. Tests remain to be written (see below).
>
> **Still needed — tests only:**
- [x] **Test:** New file `src/backend/tests/analysis-job.test.ts` (does not currently exist). Use the `kvNamespace` helper (see BM-10 note about extracting it to `tests/helpers/kv.ts`) and `createTestEnv` from `tests/helpers/env.ts`. Test cases:
    1. **Progress callback test:** two sequential progress updates (10, 60) for the same job_id — the second write must reflect fields from the first (e.g., `started_at` from write 1 must be present in write 2, and `updated_at` from write 2 must be later than write 1).
    2. **Completion-write test:** simulate a progress update (50) followed by a completion — the final write must include the `progress: 50` field set by the progress callback (not the stale `progress: 10` from the initial `processing` write).
    3. **Retry-write test:** simulate a progress update (50) followed by an exception — the catch-block retry write must include the `progress: 50` field, not the stale `progress: 10`.

### BM-4: Remove pervasive `any` from export-tracks.ts (BE-TYPE-2)

> **2026-06-24 update:** The refactor is complete but did NOT eliminate `any` in `export-tracks.ts` — the types were carried over as-is. The "skip if refactor completes first" assumption was wrong. This item must still be applied, now targeting `export-tracks.ts` instead of the old `services/export.ts`.
>
> **Type mismatch to resolve first:** `buildPlaylistMetadata` accesses `playlist?.followers?.total`, but `SpotifyPlaylist` in `src/backend/types/spotify.ts` has no `followers` field. Before changing the param type, add `followers?: { total: number }` to `SpotifyPlaylist`. Confirm against the live Spotify API contract (the field is present on full playlist objects from `GET /playlists/{id}`).

- [x] **File:** `src/backend/services/export-tracks.ts`
  - `buildPlaylistMetadata(playlist: any)` → `buildPlaylistMetadata(playlist: SpotifyPlaylist | undefined)` (see BL-2 below; these two items share the same function — do them together)
  - `calculateTotalDurationMs(items: any[])` → `calculateTotalDurationMs(items: SpotifyPlaylistTrackItem[])`
  - `mapTrackForExport(track: any, audioFeatures: any)` → `mapTrackForExport(track: SpotifyTrack, audioFeatures: SpotifyAudioFeatures | null | undefined)` (verify `SpotifyAudioFeatures` exists or define it in `src/backend/types/spotify-api.ts`)
  - `buildExportTracks(allTracks: any[])` → `buildExportTracks(allTracks: SpotifyPlaylistTrackItem[])`
  - `loadAudioFeaturesMap(...)` return type `Map<string, any>` → `Map<string, SpotifyAudioFeatures>`
  - Inner `.filter((item: any) =>` / `.map((item: any) =>` lambdas — remove the redundant `any` annotations once the parameter type is `SpotifyPlaylistTrackItem[]`
  - Import `SpotifyPlaylist`, `SpotifyTrack`, `SpotifyPlaylistTrackItem` from `src/backend/types/spotify.ts`; import (or define) `SpotifyAudioFeatures` as needed

### BM-5: Remove pervasive `any` from `routes/export.ts` (BE-TYPE-3)

> **2026-06-24 update:** The refactor is complete and did not split `routes/export.ts` — the route file is unchanged. This item is now unblocked.

- [x] **File:** `src/backend/routes/export.ts` — `resolveStepSize(body: any)` at `~line 39`, `resolveRequestedFormat(body: any)` at `~line 75`, `resolveIncludeAudioFeatures(body: any)` at `~line 94`, and 5+ other locations
  - **Use hand-rolled type guards (recommended).** This matches the existing `parseXlsxRenderMode` pattern at `routes/export.ts:67-73` and avoids adding a new dependency. Introducing `zod` should be a separate "add Zod" PR with a `package.json` review, not bundled with this bug-fix pass.
  - Define lightweight types per endpoint (e.g. `interface CreateJobsBody { playlist_ids?: unknown[]; format?: unknown; ... }`) and a guard function (e.g. `function parseCreateJobsBody(raw: unknown): CreateJobsBody`). Replace every `body: any` parameter with the parsed type.

### BM-6: Replace double `as unknown as T` casts (BE-TYPE-5) — ✅ RESOLVED

> **2026-06-24:** Fully implemented. `spotify.ts:246-280` has three typed wrappers (`asAudioFeatures`, `asArtistFull`, `asAudioFeaturesList`) replacing the original casts at lines 109, 116, 135. Each wrapper performs a minimal shape check and throws on failure. One residual `null as unknown as SpotifyAudioFeatures` at line 276 is a null-entry sentinel for the batch audio-features endpoint (Spotify returns null for tracks with no features) — this is not a bypass of the type system; it is the correct way to propagate a known null in a typed array context. No further action needed.

### BM-7: Surface actual OAuth callback error messages (BE-ERR-2)

- [x] **File:** `src/backend/routes/auth.ts` (the OAuth callback **catch block**, currently `~line 139-142` post critical-high insertions)
  - The current code returns generic `OAUTH_CALLBACK_FAILED` / `"Failed to complete OAuth flow"` for any failure (code exchange, profile fetch, KV write, JWT generation), losing all diagnostic context.
  - **Do not conflate this with the `?error=...` callback param** (that flow is already handled correctly at `auth.ts:69-71`).
  - Inspect the `error` value: classify known cases (e.g. `message.includes('Token expired')` → `OAUTH_TOKEN_EXPIRED`, `message.includes('HTTP 4')` → `OAUTH_BAD_REQUEST`, etc.) and return a mapped error code. Fall back to `OAUTH_CALLBACK_FAILED` with the original `error.message` in the `details` field (do not include the raw error in the top-level `message` to avoid leaking internal details).
  - **TypeScript type-safety note:** in `catch (error)` blocks, the `error` variable is typed as `unknown` under `strict: true`. Check `error instanceof Error` before accessing `.message`; fall back to `String(error)` otherwise. Apply the same pattern to BM-1 (refresh-token rotation) and BL-9 (refresh response), both of which also catch `error` from `refreshAccessToken` / `JSON.parse`.
  - Keep HTTP status 500 (the route still genuinely failed) but include a structured `{ error: { code, message, details: { reason: <string> } } }` payload.

### BM-8: Wrap `JSON.parse(sessionData)` in try/catch (BE-ERR-3)

> **Scope-expansion note:** the original bug (BE-ERR-3) is about unprotected `JSON.parse`. The plan also adds shape validation, which goes beyond the strict scope of BE-ERR-3. Shape validation is included because (a) it's required for the `SessionData` consumers to safely use the result, and (b) it's the natural completion of "treat as missing." Reviewers should treat both as part of this finding, not as separate scope creep.
>
> **Correction (3rd-agent review):** an earlier draft of this plan instructed to "clear the cookie (`Set-Cookie: session=; Max-Age=0`)" on parse failure. **This was wrong** — SpotiBye does not use HTTP cookies. Auth is via the `Authorization: Bearer <jwt>` header (`middleware/auth.ts:12-14`), and the refresh token lives in KV (not in a cookie). Setting `Set-Cookie` would be dead/meaningless code. The fix is to **return a 401 only** — no cookie manipulation.

- [x] **Files:** `src/backend/middleware/auth.ts` (`~line 30`) **and** `src/backend/routes/auth.ts` (`~line 155`, the refresh handler) — both have unprotected `JSON.parse(sessionData)` calls.
  - Wrap each in try/catch. On failure, log the error with the session id (truncated to 8 chars for PII safety) via `console.error` (Golden Principle #5) and treat the session as missing — throw `HTTPException(401, { message: 'Session expired or invalid' })`. **No cookie clearing** (SpotiBye uses Bearer-token auth, not cookies).
  - **Also validate the parsed shape** before returning it: require `typeof parsed === 'object'`, `parsed !== null`, and the required fields `user_id` (string), `access_token` (string), `expires_at` (number). If any field is missing or wrong type, treat the session as missing — same 401 response. This guards against partially-corrupted KV data that parses as JSON but doesn't match the `SessionData` shape.
  - Extract a shared helper `safeParseSession(raw: string | null): SessionData | null` in `src/backend/middleware/auth.ts` to avoid duplicating the try/catch and the shape check.
  - **Route helper import:** Ensure `src/backend/routes/auth.ts` imports and uses `safeParseSession` to replace its own raw `JSON.parse` call.

### BM-9: Reject empty Spotify credentials at construction (BE-ERR-5)

- [x] **File:** `src/backend/services/spotify-auth.ts` (constructor, currently `~lines 9-12`)
  - In the constructor, throw `new Error('Spotify clientId and clientSecret are required')` if either is empty (after the `|| ''` fallback). Apply to both `clientId` and `clientSecret` independently — partial credentials are still invalid.
  - **Test:** `src/backend/tests/spotify-auth.test.ts` (file already exists at `~78` lines) — add a new `describe('SpotifyAuthService construction', ...)` block with three cases: (1) both empty throws, (2) only `clientId` empty throws, (3) only `clientSecret` empty throws, (4) both valid does not throw. The existing `afterEach(() => vi.restoreAllMocks())` is reusable.

### BM-10: Serialize concurrent token refresh (BE-RACE-1)

- [x] **File:** `src/backend/middleware/auth.ts` (token refresh block, currently `~lines 33-54`)
  - Coalesce concurrent refreshes for the same session by storing an in-flight `Promise<TokenSet>` in a module-level `Map<string, Promise<...>>`. Use the session id as the key. Subsequent callers awaiting the same key share the result. Evict the entry on success/failure (use `try/finally`).
  - **Note on the race window:** Cloudflare Workers isolates are single-threaded for JS execution. The race only occurs across `await` boundaries. Two parallel HTTP requests from the same user both read the stale `expires_at`, both enter the refresh branch, and both call `refreshAccessToken`. The in-flight map dedupes that case.
- [x] **Test:** New file `src/backend/tests/auth-middleware.test.ts` (does not currently exist). **Test harness: use real timers (do not use `vi.useFakeTimers()`).** The dedup is across `await` boundaries, not across timers — fake timers would hide the actual race.
  - **Test helper (Golden Principle #7 compliance):** do **not** copy the `kvNamespace` factory from `tests/analysis-queue.test.ts:8-23` into the new test file. Instead, **extract the shared helper** to `src/backend/tests/helpers/kv.ts` and import it from both `auth-middleware.test.ts` and `analysis-queue.test.ts`. The helper exports:
    ```ts
    export function kvNamespace(initial: Record<string, unknown> = {}): KVNamespace { ... }
    export function envWithKv(cacheKv = kvNamespace(), sessionsKv = kvNamespace()): Env { ... }
    ```
    Update `analysis-queue.test.ts` to import from the helper. This satisfies the "no hand-rolled helpers" principle and prepares for BM-3's new test file (`analysis-job.test.ts`) to also use the same helper.
  - Test steps:
    1. Prime the KV with a session whose `expires_at` is in the past.
    2. Mock `fetch` (via `vi.stubGlobal('fetch', ...)`) to return a **deferred** promise — `let resolveFetch: (v: Response) => void; const fetchPromise = new Promise<Response>((r) => { resolveFetch = r; })`. This keeps both in-flight `authMiddleware` calls in the refresh branch at the same time.
    3. Call `Promise.all([authMiddleware(req1, next1), authMiddleware(req2, next2)])` but **do not await yet** — kick off both microtasks, then resolve the fetch deferred.
    4. `await fetchPromise.then(...)` is not enough; the test should:
       - Start both calls but don't await.
       - `await new Promise(setImmediate)` (or `await new Promise(r => queueMicrotask(r))`) to let both middleware invocations enter the refresh branch.
       - Then resolve the fetch deferred and `await` both middleware calls.
    5. Assert `fetch` was called **exactly once** (vi mock call count check), and both `next()` invocations were called (i.e., both requests proceeded).
    6. After both resolve, repeat with a second `Promise.all` to confirm the in-flight map was cleaned up (second call triggers a new fetch — not deduped).
    7. Call `vi.unstubAllGlobals()` alongside `vi.restoreAllMocks()` in the `afterEach` setup to prevent `fetch` mock leakage and test contamination.

### BM-11: Promote `no-explicit-any` to error (BE-API-4) — **DEFERRED to follow-up PR**

> **Decision:** this is a linter-config hardening, not a bug fix. It is **out of scope for this plan** and will be tracked as a separate "lint hardening" PR. Reasons: (1) 156 pre-existing warnings today means flipping the rule requires either 156 `// eslint-disable` comments or accepting the warning count; (2) the bulk of warnings are in route boundary `body: any` parameters which BM-4/BM-5 are removing — if the refactor-export-ts plan lands first, the count may drop to ~30-50; (3) the rule flip is a one-line change in `.eslintrc.json` that deserves its own review.
>
> **Follow-up PR (separate):** after BM-4/BM-5/BM-6 land and the refactor-export-ts plan completes, run `rg "@typescript-eslint/no-explicit-any" src/backend/` to get the new warning count, file a follow-up PR to flip the rule, and add `// eslint-disable-next-line` comments with justification for any remaining `any` usages.

---

## Backend — Low

### BL-1: Handle local-only-track pagination edge case (BE-LOG-3)

- [x] **File:** `src/backend/services/analysis.ts` (`~lines 100-110`)
  - **Already fixed and tested:** the current code uses `while (tracksData.rawCount === limit && offset < tracksData.total)` for continuation. The regression test `continues paginating by raw Spotify page count when normalized items are filtered out` at `src/backend/tests/analysis.test.ts:117-151` already covers a 100% local-item page (page 1: 99/100 items filtered → rawCount=100 → continues; page 2: 1/50 items filtered → rawCount=50 → stops).
  - **Action:** Verify the existing test still passes (it should). If a stronger edge case is needed (e.g., a 100% local playlist where `rawCount < limit` on every page but `offset < total`), add a separate test rather than overwriting the existing one. Otherwise, mark this finding as "no-op — already covered."

### BL-2: Guard `undefined` playlist in `buildPlaylistMetadata` (BE-LOG-6)

> **2026-06-24 update:** The refactor moved `buildPlaylistMetadata` to `export-tracks.ts`. The caller in `export-collect.ts:82` passes `playlist` which is `undefined` when `existingExportData` already has the matching ID (line 76-78). The correct signature is `SpotifyPlaylist | undefined`, not a non-null `Playlist`. Handle this together with BM-4 (same function).

- [x] **File:** `src/backend/services/export-tracks.ts` (`buildPlaylistMetadata`, line 5)
  - Change signature from `playlist: any` → `playlist: SpotifyPlaylist | undefined` (the caller legitimately passes `undefined` when existing data is reused — the function's optional-chaining already handles this correctly at runtime).
  - This is the same function targeted by BM-4; apply both changes in one edit.
- [x] **Test:** Confirm the caller at `export-collect.ts:82` (`buildPlaylistMetadata(playlist, tracksData.total)`) compiles cleanly — `playlist` is `SpotifyPlaylist | undefined` after line 77's conditional.

### BL-3: Reconcile Buffer detection (BE-LOG-7) — ✅ RESOLVED

> **2026-06-24:** Resolved by the export.ts refactor. `arrayBufferToBase64` moved to `export-xlsx.ts:6-15` with the inline `typeof Buffer !== 'undefined'` check intact (option a as recommended). No further action needed.

### BL-4: Drop redundant `as JWTPayload` cast (BE-TYPE-4)

- [x] **File:** `src/backend/middleware/auth.ts` (`~line 22`)
  - Remove the `as JWTPayload` annotation. `verifyToken` is declared as `Promise<JWTPayload>` (see `src/backend/services/jwt.ts:46`), so the cast is a no-op.

### BL-5: Address KV replication race in analysis job (BE-RACE-2) — ✅ RESOLVED

> **2026-06-24:** Fully implemented. `analysis-job.ts:43` already checks `ageMs < 30000` (not 15000), and `analysis-job.ts:44` already logs `console.warn(... ageMs ...)` with `job_id`. Comment at lines 38-41 documents the 30s rationale. No further action needed.

### BL-6: Strengthen error-branch discriminators (BE-DEAD-1)

- [x] **File:** `src/backend/middleware/error.ts` (`~lines 26-42`)
  - The branches match `err.name === 'ValidationError' | 'UnauthorizedError' | 'ForbiddenError' | 'NotFoundError'`. None of these are `throw`n in `src/backend/` (confirmed via `rg "throw new (ValidationError|...)"`). However, **the `err.name` string match can be hit by 3rd-party errors with those `.name` properties** (e.g., `pg` throws `error.name === 'ValidationError'` for some constraint failures; `mongoose` throws `ValidationError`; `jsonwebtoken` throws `JsonWebTokenError`/`TokenExpiredError`; `zod` throws `ZodError`).
  - **Do not delete the branches — strengthen the matchers with a discriminator field** (recommended). Concrete changes per branch:
    1. `err.name === 'ValidationError'` — also require `typeof err.code === 'string' && /^[A-Z_]+_VALIDATION/i.test(err.code)`. Falls through to 500 if no discriminator.
    2. `err.name === 'UnauthorizedError'` — also require `err.code === 'UNAUTHORIZED'` (or `err.statusCode === 401` if set). Falls through to 401 only if the error carries a confirming field.
    3. `err.name === 'ForbiddenError'` — also require `err.code === 'FORBIDDEN'` (or `err.statusCode === 403`). Falls through to 403 only with confirmation.
    4. `err.name === 'NotFoundError'` — also require `err.code === 'NOT_FOUND'` (or `err.statusCode === 404`). Falls through to 404 only with confirmation.
  - **TypeScript compile-safety casting:** Hono's `ErrorHandler` types `err` as standard `Error`, meaning that directly reading custom properties like `code` and `statusCode` will fail compilation. Instruct the implementation to explicitly type-cast it first (e.g. `const errorWithCode = err as { code?: unknown; statusCode?: unknown };`) or use a type assertion to safely inspect these properties.
  - Add a comment above the if/else chain explaining: (a) the match is by `err.name` string, (b) SpotiBye never throws these classes directly, (c) the discriminator is required to avoid silently mapping 3rd-party errors to the wrong status.

### BL-7: Remove dead `calculateAverageAudioFeatures` (BE-DEAD-2)

- [x] **File:** `src/backend/services/analysis.ts` (`~lines 334-354`)
  - Delete the function. Confirmed no callers via `rg calculateAverageAudioFeatures src/backend/` (only the definition matches).

### BL-8: Wrap health-check response in `data` envelope (BE-API-1)

> Overlaps with FM-5 (same `health_check` client code). Coordinate: change backend shape first, then update the client.

- [x] **File:** `src/backend/index.ts` (`~lines 28-34`)
  - Update `/health` to return `{ data: { status, service, timestamp } }` for consistency with the rest of the API. **No backward-compat shim** — the outer `status: 'healthy'` field is redundant once the frontend reads from the new envelope (handled by FM-5 in the same execution pass per the "Reordering rationale" in Execution Grouping). Keeping both would create two sources of truth.
- [x] **File:** `src/frontend/services/backend_client.py` (`~lines 500-505`, handled by FM-5)
  - Update the frontend health-check consumer to read the new `data` envelope. `_make_request` already unwraps `data` (returns the inner dict), so the new shape is automatically handled — no consumer code change needed.
- [x] **Test updates (3rd-agent review, G-1):** three existing test files assert the OLD shape (`data.status`, `data.service`, `data.timestamp` at the top level). They will fail under the new envelope. Update:
  1. `src/backend/tests/integration.test.ts:19-20` — change `expect(data).toHaveProperty('status', 'healthy')` → `expect(data.data).toHaveProperty('status', 'healthy')`; same for `service`.
  2. `src/backend/tests/api-coverage.test.ts:213-215` — same change (data → data.data for `status` and `service`).
  3. `src/backend/tests/workflows.test.ts:216-221` — change `data` → `data.data` for `status`, `service`, `timestamp` (line 221's `new Date(data.timestamp)` becomes `new Date(data.data.timestamp)`).

### BL-9: Remove duplicate `token`/`access_token` in refresh response (BE-API-2)

- [x] **File:** `src/backend/routes/auth.ts` (refresh response, currently `~lines 182-186` post critical-high insertions)
  - Return only `access_token` (the canonical name). Keep `expires_in` and `token_type`. Remove the duplicate `token` field.
  - Update frontend consumers that read `data.token` to use `data.access_token`. The current `backend_client.refresh_token` already does `response.get("token") or response.get("access_token")` (line 228) — confirm that still works after the removal, then simplify the lookup to `response.get("access_token")`.
- [x] **Test update (3rd-agent review, G-2):** `src/backend/tests/auth.test.ts:170` asserts `expect(data.data).toHaveProperty('token', 'test-jwt-token')` — this will fail when the `token` field is removed. Delete this assertion line; keep the `access_token` assertion on the next line.

### BL-10: Remove misleading playlist-fetch guard (BE-API-3) — ✅ RESOLVED

> **2026-06-24:** Resolved during the export.ts refactor. `generatePlaylistExportSlice` moved to `export-collect.ts:61-98`. Lines 76-78 now correctly skip the Spotify fetch when existing data already covers this playlist:
> ```ts
> const playlist = existingExportData?.playlist.id === playlistId
>   ? undefined
>   : await spotifyService.getPlaylist(playlistId);
> ```
> The ID-match check is slightly more conservative than the plan's `existingExportData ? undefined : ...` form, and is correct. No further action needed.

---

## Frontend — Medium

### FM-1: Remove unused `export_id` from `download_export` (FE-MED-1)

- [x] **File:** `src/frontend/services/backend_client.py` (current line `~406`, was 392 pre-frontend-FT-3)
  - The `download_export(self, playlist_id, export_id)` method accepts an `export_id` parameter that is never used in the body. The backend endpoint `/export/playlist/:id/download` only requires `playlist_id`.
  - Remove `export_id` from the `download_export` signature. Change to `download_export(self, playlist_id) -> bytes`.
  - **Also update the caller** at `src/frontend/screens/backend_main_screen_adapter.py:453-471` (`download_export(self, playlist_id, export_id, save_path)`). The adapter's `export_id` parameter is unused in the body (line 471) — drop it. If the caller at `main_screen_export.py:496` passes a real `export_id`, replace it with `playlist_id` and update the test.
  - No unit test exists for `download_export` today (`test_backend_client.py` does not exercise it). Add one as part of FM-4's helper extraction.

### FM-2: Decorate `_update_analysis_ui` with `@mainthread` (FE-MED-2)

- [x] **File:** `src/frontend/ui/backend_playlist_card.py` (`_update_analysis_ui` definition `~line 557`, callers `~lines 530-555`)
  - Import `from kivy.clock import mainthread`.
  - Decorate `_update_analysis_ui` with `@mainthread`. **The decorator is a one-liner — no need to also wrap with `Clock.schedule_once`.** `@mainthread` automatically schedules the call on the main thread via `Clock.schedule_once` under the hood, so it's safe to call from a background `threading.Thread`.
  - **Clean up the boilerplate at the call sites** (`_load_analysis_worker`, `~lines 530-555`). The current code has three `Clock.schedule_once(lambda _dt: self._update_analysis_ui(...), 0)` wrappers — these become unnecessary once `_update_analysis_ui` is decorated with `@mainthread`. **Replace each wrapper with a direct call.** Example for the success path:
    ```python
    # Before:
    Clock.schedule_once(
        lambda _dt, a=analysis: self._update_analysis_ui(
            analysis_container, duration_label, a, None
        ),
        0,
    )
    # After:
    self._update_analysis_ui(analysis_container, duration_label, analysis, None)
    ```
    Apply the same simplification to the no-backend-connection path (lines 530-538) and the exception path (lines 550-555). Note: the `analysis` and `exc` variables from the surrounding `try`/`except` are still captured normally by the method call.
  - Confirm `_update_analysis_ui` does not have other non-thread-safe callers (only the analysis flow) before applying.
- [x] **Test:** New file `src/frontend/tests/test_backend_playlist_card.py` (does not currently exist). Mock a Kivy widget and call the method from a `threading.Thread`; assert no widget-assertion error is raised.

### FM-3: Destroy tkinter root on exception (FE-MED-3)

- [x] **File:** `src/frontend/utils/platform_utils.py` ~lines 119-129
  - Wrap the `Tk()`/`winfo_*` calls in try/finally. Call `root.destroy()` in the `finally` block.
  - If `Tkinter` is unavailable on the platform, return defaults without ever instantiating `Tk()`.

### FM-4: Consolidate download methods through `_make_request` (FE-MED-4)

- [x] **File:** `src/frontend/services/backend_client.py` (current lines `~406-510`, was 392-496 pre-frontend-FT-3)
  - Refactor `download_export`, `download_batch_export`, and `download_export_job` to delegate to a single `_download_file(self, endpoint, timeout)` helper that:
    - Builds the URL from `endpoint` (full path)
    - Sets auth/trace headers (same as `_make_request`)
    - Calls `self.session.get(url, headers=headers, timeout=timeout)`
    - On `response.status_code >= 400`, parses JSON error body and raises `BackendAPIError` (same logic as the current code)
    - Returns `response.content` on success
  - **Do NOT delegate to `_make_request` directly** — the response is binary (an xlsx/csv/json file), not JSON. The helper is a separate `session.get` wrapper that shares the error-parsing logic.
  - Apply to all three methods. Add unit tests in `test_backend_client.py` for each method's success path and error path (mock `self.session.get` via `unittest.mock.patch.object(BackendClient, 'session', ...)` or by replacing `self.session` directly in a fixture).

### FM-5: Broaden `health_check` exception handling (FE-MED-5)

- [x] **File:** `src/frontend/services/backend_client.py` (`~lines 513-519`)
  - Current code catches only `BackendAPIError`. Broaden to catch `Exception` (defense-in-depth — `_make_request` already wraps transport errors in `BackendAPIError`, but a coding bug could raise `JSONDecodeError` or `TypeError`).
  - Return shape: `{"status": "error", "error": str(e)}` (matches the unhealthy shape).
  - **Contract documentation:** `health_check` returns a dict with at least a `status` key, one of `"healthy" | "unhealthy" | "error"`. Callers can branch on `result.get("status") == "healthy"`. Document in CHANGELOG under "Changed".
  - The backend shape change in BL-8 also affects this — `health_check` must handle both the old `{ status, service, timestamp }` and new `{ data: { status, ... } }` shapes. The current code returns `_make_request`'s output directly; after BL-8, `_make_request` will return the unwrapped `data` dict, so the new shape is already handled.

### FM-6: Surface missing `logout` method instead of silent no-op (FE-MED-6)

- [x] **File:** `src/frontend/screens/main_screen_logout.py` (`~lines 77-85`)
  - Current code silently no-ops if the app lacks a `logout` method:
    ```python
    if app and hasattr(app, "logout"):
        app.logout()
    ```
    This leaves credentials in memory if the no-op path is hit.
  - **Change to: log a `logger.error` and return gracefully** (NOT raise). Rationale: in production, the `App` always has `logout` (defined in `src/frontend/app/backend_app.py:274`). The `hasattr` check only matters in dev/test setups that use minimal app mocks. Raising `RuntimeError` would break those test setups, which is a heavier cost than the original silent no-op. Logging the error makes the issue visible in production logs without breaking dev workflows.
    ```python
    if app is None:
        return
    if not hasattr(app, "logout"):
        logger.error(
            "App is missing logout method — credentials remain in memory. "
            "Check that the app is fully initialized before calling perform_logout."
        )
        return
    app.logout()
    ```
  - Add a small unit test that calls `perform_logout()` with a mock app lacking `logout` and asserts the error log was emitted (via `caplog` or `unittest.mock.patch` on the logger). Do **not** assert any exception is raised.

---

## Frontend — Low

### FL-1: Add `clear_file` helper for prefix-hashed cache files (FE-LOW-1)

- [x] **File:** `src/frontend/caching/backend_cache.py` (new method); `src/frontend/screens/backend_main_screen_adapter.py` (current lines `~1041-1048`); reuse `_cache_file_path` from FT-5.
  - **Add a new `BackendCacheManager.clear_file(filename: str) -> None` method** that internally uses `_cache_file_path` (FT-5) to resolve the path and `unlink()` it directly. Do **not** route through `clear_cache` with a glob — the existing glob path uses `cache_dir.glob(pattern)` which has no env-hash prefix and would miss the actual hashed files.
  - The previous draft's suggestion `self.cache_manager.clear_cache(str(self.cache_manager._cache_file_path("playlists.json").name))` was **incorrect** — it would resolve to the same full hashed filename and call `clear_cache` with that as a literal (no wildcard), but the existing `clear_cache` method does not apply the env-hash prefix when matching, so the call would have side effects but for the wrong reasons. Discard that suggestion in favor of the new `clear_file` method.
  - **Adapter call site update** at `backend_main_screen_adapter.py:1041-1048`:
    - Replace `self.cache_manager.clear_cache("playlists.json")` with `self.cache_manager.clear_file("playlists.json")`.
    - The `tracks_*.json` / `analysis_*.json` / `export_*.json` patterns at lines 1043-1047 are **glob patterns** and need a different fix. Add a sibling method `clear_cache_glob(pattern: str)` that internally applies the env-hash prefix (e.g. `cache_dir.glob(f"{env_hash}_{pattern}")`) and unlinks each match. Use this for the three glob-pattern call sites.
    - **Loop Resiliency in `clear_cache_glob`:** Ensure that the `unlink()` call inside the glob clear loop is wrapped in a `try...except FileNotFoundError:` block (or verify `exists()` before unlinking) to prevent a single file deletion race or missing file error from aborting the entire clear loop.
- [x] **Test:** Add to existing `src/frontend/tests/test_resumable_export_cache.py`. Cases:
    1. `test_clear_file_removes_hashed_file` — pre-populate `{env_hash}_playlists.json`, call `clear_file("playlists.json")`, assert file is gone.
    2. `test_clear_file_missing_is_noop` — call `clear_file("nonexistent.json")` on a dir without the file, assert no exception.
    3. `test_clear_cache_glob_uses_env_hash_prefix` — pre-populate `{env_hash}_tracks_abc.json` and `unrelated_tracks_xyz.json`, call `clear_cache_glob("tracks_*.json")`, assert the hashed one is gone and the unrelated one remains.

### FL-2: Tighten `is_valid_backend_url` validation (FE-LOW-2)

- [x] **File:** `src/frontend/config/backend_config.py` (`~lines 153-155`)
  - Current code only checks `url.startswith(("http://", "https://"))` — accepts `https://not a url!!!`.
  - **Correction (3rd-agent review):** use `parsed.hostname` (not `parsed.netloc`) for the "contains `.` or is `localhost`" check. `netloc` includes the port (e.g. `localhost:8787`), so the equality check `"localhost:8787" == "localhost"` always fails. `hostname` strips the port. Also guard `hostname is not None` (e.g. for `http:///path`).
  - After the `startswith` check, call `urllib.parse.urlparse(value)` and require:
    - `parsed.scheme in {"http", "https"}`
    - `parsed.hostname is not None` and is non-empty
    - `parsed.hostname` contains a `.` OR equals `localhost` (reject `https://x`)
  - ```python
    def is_valid_backend_url(url: str) -> bool:
        if not url or not url.startswith(("http://", "https://")):
            return False
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.hostname is None:
            return False
        return "." in parsed.hostname or parsed.hostname == "localhost"
    ```
- [x] **Test:** Add to `src/frontend/tests/test_configuration.py` (file already exists). Cases:
    - `https://example.com` → True
    - `http://localhost:8787` → True (regression test for the netloc-vs-hostname fix)
    - `http://localhost` → True
    - `https://not a url!!!` → False
    - `https://x` → False
    - `ftp://example.com` → False
    - `""` → False
    - `"http://"` → False (empty netloc, hostname is None)
    - `"http:///path"` → False (hostname is None)

### FL-3: Simplify `_format_backend_api_error` redundant checks (FE-LOW-3)

- [x] **File:** `src/frontend/screens/backend_main_screen_adapter.py` (`~lines 68-120`)
  - The `details_payload` variable is always a dict after the assignment at lines 87-91 (else it defaults to `{}`). The `isinstance(details_payload, dict)` checks at lines 99 and 105 are therefore redundant.
  - Simplify to: extract a small helper `_format_details(details: dict) -> str` that returns the `upstream`/`upstream_status` parts. Inline the rest.
  - No behavior change — `details_payload` is always a dict at those lines.
- [x] **Test:** Add a snapshot-style test to `test_backend_main_screen_adapter.py` (new file). Construct a `BackendAPIError` with a known `response_data` shape and assert the formatted output matches a fixed string. The current call sites (anywhere `_format_backend_api_error` is invoked) are stable; verify the existing call sites still produce the same output.

### FL-4: Avoid re-importing `LabelBase` inside the inner loop (FE-LOW-4)

- [x] **File:** `src/frontend/app/backend_app.py` (`~lines 206-234`)
  - The function `_setup_fonts` imports `LabelBase` at `~line 209` (in the outer try) and again at `~line 227` (inside the system-fonts loop). The second import is a no-op after the first succeeds, but if the first fails and the second succeeds, the import is repeated once per system font.
  - Move the import to module scope (after the outer import guard at the top of the file) with a try/except that sets `LABEL_BASE_AVAILABLE = True/False`. Use the module-level reference inside the loop.
  - Alternative: keep the import lazy but cache the result in a module-level `_label_base = None` and attempt import only when `_label_base is None`.

### FL-5: Clean up unused `playlist` parameter in `_build_backend_output_path` (FE-LOW-5)

- [x] **Files:**
  1. `src/frontend/screens/main_screen_export.py` (`~lines 56-66`) — the orchestrator method.
  2. `src/frontend/screens/main_screen.py` (`~lines 960-964`) — the `MainScreen` delegation method.
  3. `src/frontend/tests/test_main_screen_export.py` (`~lines 54-56`) — the existing test calls the orchestrator with 3 args.
  - **Bug review correction:** the bug review claimed `_build_backend_output_path` with `multiple=True` is "an identity function (passthrough)." This is **incorrect** — the `multiple=True` branch returns `os.path.join(base_dir, f"{base_name}{extension}")`, which strips the user-provided extension and replaces it with the current export format's extension. The function does real work, not passthrough.
  - The only call site is at `main_screen_export.py:236` (passes `valid_playlists[0], output_path, total > 1`). It is **not** called from `main_screen_export.py:321` or `:355` (those are `adapter.download_batch_export` calls using `target_path`).
  - **Real cleanup:** the `playlist: dict` parameter is **never used** in the function body. Drop it from **both** the orchestrator and the `MainScreen` delegation:
    ```python
    # main_screen_export.py:56
    def _build_backend_output_path(
        self, base_output_path: str, multiple: bool
    ) -> str:
        if not multiple:
            return base_output_path
        base_dir = os.path.dirname(base_output_path)
        base_name = os.path.splitext(os.path.basename(base_output_path))[0]
        extension = self._get_file_extension(self._selected_export_format())
        return os.path.join(base_dir, f"{base_name}{extension}")

    # main_screen.py:960 — delegation method
    def _build_backend_output_path(
        self, base_output_path: str, multiple: bool
    ) -> str:
        """Build output file path for backend export."""
        return self.export_orchestrator._build_backend_output_path(base_output_path, multiple)
    ```
  - **Update the call site** at `main_screen_export.py:236-238` to `target_path = self._build_backend_output_path(output_path, total > 1)` (drop the `valid_playlists[0]` arg).
  - **Update the existing test** at `test_main_screen_export.py:54-56` (`test_build_backend_output_path_single`): change the call to `orchestrator._build_backend_output_path("/tmp/file.xlsx", False)`. Add a regression test that **also covers the delegation in `main_screen.py`** — mock the orchestrator and call `screen._build_backend_output_path("/tmp/file.xlsx", False)` to confirm the delegation passes the args through correctly.
  - **Test:** add a new unit test class `TestBuildBackendOutputPath` (in the same `test_main_screen_export.py` file) with cases: (1) `multiple=False` returns the path unchanged, (2) `multiple=True` with `output_path="/tmp/foo.txt"` and `xlsx` format returns `/tmp/foo.xlsx`, (3) `multiple=True` with no extension on the path still works, (4) `MainScreen._build_backend_output_path` delegation passes the 2-arg signature through to the orchestrator.

### FL-6: Replace `Optional[callable]` with `Optional[Callable[..., Any]]` (FE-LOW-6)

- [x] **File:** `src/frontend/screens/backend_main_screen_adapter.py` (`~lines 34-36`)
  - Add `Callable` to the existing `from typing import` import. Change the three annotations:
    - `self.playlists_loaded_callback: Optional[callable] = None` → `Optional[Callable[..., Any]] = None`
    - Same for `error_callback` and `progress_callback`
  - This makes the annotations valid types (the bare `callable` builtin is a runtime check, not a type expression — mypy and other type checkers reject it).

### FL-7: Rename custom `TimeoutError` to avoid shadowing the builtin (FE-LOW-7)

- [x] **Files:** `src/frontend/utils/network_utils.py` (`~lines 29-32`) and `src/frontend/services/reccobeats_backend.py` (`~line 125`)
  - **The bug:** `reccobeats_backend.py:125` does `raise TimeoutError(f"...")` (the **built-in** `TimeoutError`, not the custom one — `reccobeats_backend.py` only imports `retry_on_network_error, handle_network_errors` from `network_utils`, not the custom class). The custom `TimeoutError` in `network_utils.py:29` is exported but never raised from `reccobeats_backend`. The custom `handle_network_errors` catches only the custom `TimeoutError` (via `requests.exceptions.Timeout`), so a reccoBeats timeout would NOT be caught by the custom handler — it propagates as a builtin `Exception`.
  - **Hard rename** (recommended): rename the custom class to `NetworkTimeoutError`. No deprecated alias — the only consumers are internal to this repo (8 call sites, all internal; `rg TimeoutError src/frontend/` shows no external consumers in this repo). A deprecated alias adds ongoing maintenance cost for no benefit.
  - Update `reccobeats_backend.py:125` to `raise NetworkTimeoutError(...)` after importing it.
  - **Public API change:** `TimeoutError` is exported from `src/frontend/__init__.py:5,17` and `src/frontend/utils/__init__.py`. Document in CHANGELOG under "Changed" with a one-line note: "Custom `TimeoutError` renamed to `NetworkTimeoutError` to avoid shadowing the builtin. Update imports."
  - Update all 8 internal call sites via `rg "TimeoutError" src/frontend/`.

### FL-8: Log diagnostics on `ImportError` (FE-LOW-8)

- [x] **File:** `src/frontend/ui/backend_cache_explorer.py` (`~lines 21-29`)
  - Current code: `except ImportError: BACKEND_AVAILABLE = False; logger.warning("Backend components not available for backend cache status")` — the `as exc` is not captured, so the actual error is lost.
  - Change to `except ImportError as exc: ...` and include the error in the warning: `logger.warning(f"Backend components not available for backend cache status: {exc}")`.
  - **Scope note:** `exc` only exists inside the `except` block. To surface it in `initialize_backend_client` (line 122), capture the message in a module-level variable:
    ```python
    _BACKEND_IMPORT_ERROR: str = ""
    try:
        from ..services.backend_client import BackendClient
        ...
        BACKEND_AVAILABLE = True
    except ImportError as exc:
        BACKEND_AVAILABLE = False
        _BACKEND_IMPORT_ERROR = str(exc)
        logger.warning(f"Backend components not available for backend cache status: {exc}")
    ```
    Then in `initialize_backend_client` at line 122:
    ```python
    self.backend_status_label.text = (
        f"Backend: Not Available ({_BACKEND_IMPORT_ERROR})"
        if _BACKEND_IMPORT_ERROR
        else "Backend: Not Available"
    )
    ```

### FL-9: Make `clear_all_cache` actually clear the cache (FE-LOW-9)

> Reuse the shared cache-path helper extracted in FT-5 (critical/high plan) to locate and delete cache files.

- [x] **Files:**
  1. `src/frontend/caching/backend_cache.py` (`clear_cache` method, currently `~line 413`) — fix the `pattern=None` default to use env-hash prefix.
  2. `src/frontend/screens/main_screen_cache.py` (`~lines 66-93`) — call the actual cache clear.
  - **Sub-finding (3rd-agent review, G-6):** the current `clear_cache(pattern=None)` implementation does `self.cache_dir.glob("*.json")`, which matches **every** JSON file in the cache dir, including:
    - `backend_token_{env_hash}.json` — the user's auth token (deleting this logs them out).
    - `backend_selection.json` — the user's selected backend URL (deleting this resets their config).
    These should NOT be deleted when the user clicks "Clear Cache." The fix is to change the `pattern=None` default to `f"{env_hash}_*.json"` — i.e., only env-hash-prefixed data files (playlists, tracks, analysis, export). Auth tokens and backend selection are unprefixed (or use `backend_*` naming) and are correctly skipped.
  - **Plan body:**
    1. In `caching/backend_cache.py:413-433`, change the `else` branch to:
       ```python
       if pattern:
           cache_files = list(self.cache_dir.glob(pattern))
       else:
           env_hash = self._hash_backend_url(self._get_backend_url_safe())
           cache_files = list(self.cache_dir.glob(f"{env_hash}_*.json"))
       ```
    2. In `screens/main_screen_cache.py:66-93`, before `success_popup.open()`, call the actual cache clear through the adapter: `screen.backend_adapter.cache_manager.clear_cache(None)`. **Verified path:** `screen` is a `MainScreen` instance (`src/frontend/screens/main_screen.py`); `MainScreen` exposes `self.backend_adapter` (set in `initialize_with_backend` at `main_screen.py:95-97`); the adapter exposes `self.cache_manager` (set at `backend_main_screen_adapter.py:30` as `self.cache_manager = get_cache_manager()`). `MainScreen` itself has **no** `cache_manager` attribute, so a direct `screen.cache_manager` call would raise `AttributeError`.
    3. **Failure handling:** if `screen.backend_adapter is None` (e.g., the user opened the app in offline mode), show the error popup with `"Backend not initialized — nothing to clear"` and skip the success popup.
- [x] **Test:** Add to `src/frontend/tests/test_main_screen_cache.py` (new file, since the test exercises a UI flow, not the cache manager). Test cases:
    1. `test_clear_all_cache_removes_data_files_only` — pre-populate `{env_hash}_playlists.json`, `backend_token_{env_hash}.json`, and `backend_selection.json` in a temp dir. Call `cache_manager.clear_cache(None)`. Assert `{env_hash}_playlists.json` is gone; assert `backend_token_{env_hash}.json` and `backend_selection.json` remain. This is the regression test for the G-6 fix.
    2. `test_clear_all_cache_shows_error_when_no_backend_adapter` — set `screen.backend_adapter = None`, assert the error popup path is taken and no cache clear is attempted.
    3. Mock all `Popup` instances to avoid UI side effects.

---

## Verification

- [x] Run `./scripts/verify-all.sh` from repo root — must pass with zero errors.
- [x] Run backend tests: `cd src/backend && npm run test:run && npm run lint`
- [x] Run frontend tests: `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v`
- [x] **CHANGELOG entry** under `## [Unreleased]` should be **grouped by category** (not 36 individual bullets) for scannability. Suggested groups:
  - **Backend auth & token handling** — BM-1, BM-3, BM-7, BM-8, BM-9, BM-10, BL-4
  - **Backend type safety** — BM-2, BM-4, BM-5, BM-6 (BM-11 deferred to follow-up PR)
  - **Backend service & data hardening** — BL-1 (no-op), BL-2, BL-3, BL-5, BL-6, BL-7, BL-9, BL-10
  - **Backend API contract** — BL-8, FM-5 (the frontend change)
  - **Frontend service hardening** — FM-1, FM-3, FM-4, FM-5, FM-6
  - **Frontend thread & resource safety** — FM-2
  - **Frontend cache & cleanup** — FL-1, FL-3, FL-4, FL-5, FL-7, FL-8, FL-9
  - **Frontend validation** — FL-2, FL-6
- [x] Re-run any frontend consumers touched by backend response-shape changes in the same pass (`FM-1`, `FM-5`, `BL-8`, `BL-9`) so the API contract stays consistent.

---

## Links

- **Bug assessment:** [dev-docs/bug-review-2026-06-21-183947.md](../../dev-docs/bug-review-2026-06-21-183947.md)
- **Critical & High plan:** [2026-06-21-bug-fix-critical-high.md](../completed/2026-06-21-bug-fix-critical-high.md) — ✅ Complete
- **TODO entry:** [dev-docs/backlog/TO_DO.md](../../dev-docs/backlog/TO_DO.md) (see "Fix medium/low bugs from 2026-06-21 audit")
- **2nd-agent review:** [tmp/plan_review_2026-06-21_160000.md](../../../tmp/plan_review_2026-06-21_160000.md) — 20 findings, all addressed inline above.
- **3rd-agent review:** [tmp/plan_assessment_2026-06-21_medium_low.md](../../../tmp/plan_assessment_2026-06-21_medium_low.md) — 2 errors + 8 gaps + 4 observations, all addressed inline above.
- **4th-agent review:** [tmp/bug-fix-medium-low-assessment.md](../../../tmp/bug-fix-medium-low-assessment.md) — 3 errors + 6 gaps + 2 improvements, all addressed inline above.

## Coordination Notes

### With `2026-06-21-refactor-export-ts.md` — ✅ Complete

- **BL-10** — ✅ Resolved during the refactor (see BL-10 above).
- **BL-3** — ✅ Resolved during the refactor (see BL-3 above).
- **BM-4** — The refactor did NOT eliminate `any` in `export-tracks.ts`. Item retargeted to `export-tracks.ts`; must still be applied (see updated BM-4).
- **BM-5** — The refactor did not split `routes/export.ts`. Item is now unblocked (see updated BM-5).
- **BL-2** — The refactor moved `buildPlaylistMetadata` to `export-tracks.ts`. Item retargeted; apply together with BM-4.

### With `2026-06-21-bug-fix-critical-high.md` — ✅ Complete

- **FL-1 and FL-9** — `_cache_file_path` (FT-5) is confirmed at `src/frontend/caching/backend_cache.py:311`. Unblocked.
- **BM-3 and BM-10** — `createTestEnv` is confirmed at `src/backend/tests/helpers/env.ts`. Unblocked.

### With `2026-06-21-bug-review-medium-low-fixes.md` (RESOLVED — superseded)
- ✅ **Resolved 2026-06-21.** The duplicate plan was moved to [`dev-docs/exec-plans/completed/superseded/2026-06-21-bug-review-medium-low-fixes.md`](../../completed/superseded/2026-06-21-bug-review-medium-low-fixes.md) with a SUPERSEDED notice pointing back to this plan. The README index at `dev-docs/exec-plans/completed/README.md` was updated.
- The duplicate's useful elements (4-commit grouping, several test names) are now incorporated in the "Execution Grouping" section of this plan.

## Execution Grouping

The 20 finding steps are best executed as **6 atomic commits** (matches the superseded plan's grouping, but with correct file paths and post-critical-high line numbers). Commit 2 was split into 2a (type safety) and 2b (dead code + service hardening) to address O-3 (heavy commit). Each commit must pass `./scripts/verify-all.sh` independently:

| Commit | Scope | Items | Files |
|--------|-------|-------|-------|
| `fix(backend): harden auth and token boundaries` | Auth, middleware, service edges | BM-1 (gap only), ~~BM-3✅~~ (tests only), ~~BL-5✅~~, BM-7, BM-8, BM-9, BM-10, BL-4 | `routes/auth.ts`, `middleware/auth.ts`, `services/spotify-auth.ts`, `services/analysis-job.ts`; new `tests/analysis-job.test.ts`, `tests/auth-middleware.test.ts` |
| `fix(backend): tighten service validation and types` | Type safety, validation | BM-2, BM-4, BM-5, ~~BM-6✅~~, ~~BM-11~~ | `services/spotify.ts`, `services/export-tracks.ts`, `routes/export.ts`, `types/spotify-api.ts` |
| `fix(backend): clean up dead code and weak error branches` | Dead code, service hardening | BL-1 (no-op), BL-2, ~~BL-3✅~~, BL-6, BL-7, BL-9, ~~BL-10✅~~ | `services/export-tracks.ts`, `services/analysis.ts`, `middleware/error.ts`, `routes/auth.ts` |
| `fix(backend): align health-check and refresh response shape` | API contract | BL-8 | `index.ts`; coordinate with frontend commit |
| `fix(frontend): harden client downloads, validation, and thread safety` | Frontend service, validation, thread | FM-1, FM-2, FM-3, FM-4, FM-5, FM-6, FL-2, FL-6 | `services/backend_client.py`, `ui/backend_playlist_card.py`, `utils/platform_utils.py`, `config/backend_config.py`, `screens/main_screen_logout.py`, `screens/backend_main_screen_adapter.py`; new `tests/test_backend_playlist_card.py` |
| `fix(frontend): cache helpers, dead code, and error logging` | Cache cleanup, dead code, logging | FL-1, FL-3, FL-4, FL-5, FL-7, FL-8, FL-9 | `caching/backend_cache.py`, `screens/main_screen_cache.py`, `screens/main_screen_export.py`, `app/backend_app.py`, `ui/backend_cache_explorer.py`, `services/reccobeats_backend.py`, `utils/network_utils.py` |
| `docs: record medium/low fix plan in CHANGELOG` | Documentation | — | `CHANGELOG.md` |

**Reordering rationale:**
- BM-3 and BL-5 **must** be in the same commit (commit 1) — both touch `src/backend/services/analysis-job.ts`. Splitting them risks a merge conflict on the file's `process` method. (Addresses E-1.)
- Backend auth (commit 1) is independent of type tightening (commits 2-3). Either can go first.
- Commit 4 (API contract) **must** be paired with FM-5 in commit 5 to keep the contract in sync (the plan's Verification section already flags this).
- Commit 6 is the final frontend cleanup pass and is independent of commits 1-4.

**Test file path correction from the superseded plan:** the superseded plan referenced non-existent subdirectories like `tests/routes/auth.test.ts` and `tests/services/test_backend_client.py`. The actual layout is flat — `src/backend/tests/<name>.test.ts` and `src/frontend/tests/test_<name>.py`.

**Follow-up PRs (out of scope, tracked separately):**
- **Lint hardening** — flip `@typescript-eslint/no-explicit-any` from warn to error in `.eslintrc.json`. Open after BM-4/BM-5 land (BM-6 and the refactor are already done), so the warning count is tractable (likely 30-50, not 156).

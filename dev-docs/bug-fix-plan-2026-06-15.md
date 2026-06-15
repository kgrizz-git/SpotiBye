# Bug Fix Plan — 2026-06-15

Plan to address the findings in `bug-review-2026-06-15-112416.md`. Ordered by
severity. Each item lists root cause, fix approach, files, and verification.

---

## H1. User-scoped cache keys for playlist detail / tracks

**Root cause:** Cache keys (`playlist:${id}`, `playlist:${id}:tracks:...`) are
global. A second authenticated user can read another user's cached private or
collaborative playlist without Spotify re-authorizing them.

**Fix:**
- Derive a stable user identity already present on the request (the JWT subject
  / Spotify user id from `c.get(...)`) and prefix every Spotify cache key with
  it, e.g. `user:${userId}:playlist:${id}`.
- Apply the same scoping to the track-items handler and any other per-user
  Spotify cache key (audit `track:`, playlists list, etc. — scope the
  resource-owner-sensitive ones).
- Confirm the user id is available in the middleware that sets `access_token`;
  if not, add it there.

**Files:** `src/backend/routes/spotify.ts:112,141` (and other cache keys in the
file), auth middleware that populates context.

**Verify:** Unit test that two different user contexts produce different cache
keys and do not cross-read. `npm run test:run`.

---

## H2. Export pagination on filtered (local/unavailable) items

**Root cause:** `normalizePlaylistItemsResponse()` drops entries without a
track id, so callers see fewer items than the raw page. Export stop/advance
logic keys off the filtered count → early stop (sync path) and offset overlap
(resumable path).

**Fix:**
- Have `getPlaylistTracks` / `normalizePlaylistItemsResponse` return the **raw
  page size** alongside the filtered items (e.g. add `fetchedRawCount` to
  `NormalizedPlaylistItemsResponse`), keeping `total` as Spotify reports it.
- Sync export (`export.ts:476`): stop when `rawCount < limit`; advance
  `offset += limit` (the raw page size), not by filtered length.
- Resumable export (`export.ts:312`): advance `next_offset` by the raw fetched
  count, and base `playlistDone` on raw offset reaching `total`, not on
  filtered `collectedTracks` (which legitimately differs from `total`).

**Files:** `src/backend/services/spotify.ts:60-93`,
`src/backend/services/export.ts:300-330,476-483`, type
`NormalizedPlaylistItemsResponse`.

**Verify:** Unit test with a mock page of 100 raw items / 95 valid tracks across
multiple pages — assert no early stop, no offset overlap, no duplicate tracks.

---

## H3. User-selected export format is ignored — ✅ DONE (2026-06-15)

**Root cause:** Frontend always forces `.xlsx` and sends `"xlsx"`; backend only
special-cases `csv`, so `JSON` silently becomes XLSX.

**Decision (confirmed):** Implement JSON export end-to-end. Output shape =
**nested per-playlist**: an array of playlist objects, each with metadata
(name, owner, followers, description, url, total_duration) and a nested
`tracks` array of track objects (same fields as the XLSX columns).

**Pipeline note (from code read):** the resumable exporter already
pre-assembles each playlist into structured `WorksheetAssemblyData` (playlist
metadata + `headers` + `rows`) in the non-CSV branch (`export.ts:322,422`).
JSON rides this same accumulation path — no new collect-phase branch needed.
Only the final serializer and format plumbing change.

**Fix:**
- Widen the `file_format` union `'xlsx' | 'csv'` → add `'json'`
  (`export.ts:24` and all narrowing casts).
- `resolveRequestedFormat` (`export.ts:73`): accept `csv`, `json`, `xlsx`.
- Add a JSON serializer that zips each worksheet's `headers`+`rows` back into
  track objects and nests them under playlist metadata; bypass the rich/lite
  XLSX renderer path entirely for `json`.
- Add the `json` branch to the download MIME/extension tuples at
  `export.ts:386,882,960` (`application/json`, `.json`).
- Frontend `main_screen.py`: pass the chosen format through instead of forcing
  xlsx at `414/1166/1344/1591`; map extension from format
  (`.xlsx`/`.csv`/`.json`) — including the hardcoded `.xlsx` filename logic at
  `1166-1167`; send lowercased format to combined + sequential endpoints.

**Files:** `src/frontend/screens/main_screen.py:414,1166,1344,1591`,
`src/backend/routes/export.ts:73` and assembly/MIME sites,
`src/backend/services/export.ts` assembler.

**Verify:** Manual export of each format produces a correctly-named, correctly
-typed file; backend tests for `resolveRequestedFormat` and per-format
assembly.

---

## M1. Playlist analysis only processes first 100 tracks

**Root cause:** `analyzePlaylist()` calls `getPlaylistTracks(id, 100, 0)` once.

**Fix:** Paginate through all tracks (mirror the `generatePlaylistExport`
while-loop using the raw-count stop condition from H2) before computing totals,
artist counts, genre distribution, and insights.

**Files:** `src/backend/services/analysis.ts:62`.

**Verify:** Test with a >100-track mock playlist; assert totals/counts reflect
all tracks.

---

## M2. Combined XLSX duplicate worksheet names

**Root cause:** Sheet names sanitized/truncated but not de-duplicated;
collisions make `addWorksheet()` throw.

**Fix:** Add a uniqueness pass — track used names (case-insensitive) and append
a numeric suffix that respects the 31-char Excel limit (e.g. truncate to make
room for ` (2)`).

**Files:** `src/backend/services/export.ts:589,907` (centralize in one helper).

**Verify:** Test two playlists with identical names and names colliding after
truncation; assert distinct worksheet names and no throw.

---

## M3. OAuth documented as PKCE but not implemented — ✅ DONE (2026-06-15)

**Root cause:** Docs/architecture claim PKCE; implementation uses plain
authorization-code (no `code_challenge` / `code_verifier`).

**Decision (confirmed):** Implement PKCE as a **confidential client + PKCE**
(keep the client secret AND add PKCE — defense in depth). The flow is
backend-mediated, so the verifier lives server-side:

- `/auth/spotify/login` (`auth.ts:12`): generate a `code_verifier`, derive the
  S256 `code_challenge`, and store **both** `redirect_uri` and `code_verifier`
  in the `oauth_state:${state}` KV record (change the stored value from a bare
  string to JSON).
- `getAuthUrl` (`spotify-auth.ts:14`): add `code_challenge` and
  `code_challenge_method=S256` to the authorize URL.
- Callback (`auth.ts:53-60`): read the verifier back from KV and pass it to
  exchange.
- `exchangeCodeForTokens` (`spotify-auth.ts:37`): accept and send
  `code_verifier` in the token POST body (keep Basic auth).
- Generate verifier with Workers `crypto.getRandomValues`; challenge via
  `crypto.subtle.digest('SHA-256', ...)` + base64url. Confirm base64url (no
  padding, URL-safe) — this is the most common PKCE bug.
- Update architecture/docs to describe the now-accurate flow.
- Frontend (`backend_client.py:190`) needs no PKCE changes under this model.

**Files:** `src/backend/routes/auth.ts:12,53`,
`src/backend/services/spotify-auth.ts:14,37`, plus architecture/docs.

**Verify:** End-to-end auth flow against Spotify; unit test challenge/verifier
generation and round-trip.

---

## M4. Console script points to removed package

**Root cause:** `pyproject.toml` still exposes
`spotify-playlist-exporter = "spotify_playlist_exporter_v2.__main__:main"`;
that module no longer exists → `ModuleNotFoundError`.

**Fix:** Update or remove the `[project.scripts]` entry to the current
entrypoint (confirm the real one from the code map / frontend main).

**Files:** `pyproject.toml:33`, cross-check `dev-docs/code-map.md:16`.

**Verify:** `pip install -e .` then run the console script; import resolves.

---

## M5. JWT falls back to hardcoded `default-secret`

**Root cause:** `JWTService` defaults to `'default-secret'` when `JWT_SECRET`
is unset → predictable tokens on misconfigured deploys.

**Fix:** Fail closed — throw in the constructor (or at startup config
validation) when `JWT_SECRET` is missing/empty. Keep tests passing by injecting
a test secret explicitly.

**Files:** `src/backend/services/jwt.ts:22`, callers/config validation, test
setup.

**Verify:** Constructor throws without secret; tests pass with injected secret;
`npm run test:run`.

---

## L1. `CacheService.exists()` invalid KV option shape

**Root cause:** Passes `{ stream: true }`; Workers KV expects
`{ type: "stream" }` (or `"stream"`). Cast hides the mismatch; render modes may
report unavailable.

**Fix:** Use `this.kv.get(key, { type: 'stream' })` (or just
`{ type: 'arrayBuffer' }`/metadata check appropriate to intent) and update the
test asserting the wrong shape.

**Files:** `src/backend/services/cache.ts:51`, corresponding test.

**Verify:** Unit test reflects correct option; behavior check that existing
download bytes report as present.

---

## Cross-cutting / verification health

- The frontend verification phase fails under the sandbox (real localhost
  requests, one cache test writing to `~/.spotibye_cache`). Separately from the
  bugs: stub/mock network in those tests and redirect cache to a temp dir so
  `./scripts/verify-all.sh` is green in-sandbox. Track as its own task.

## Suggested sequencing

1. H1, H2, H3 (security + data-correctness, user-visible).
2. M1, M2 (export/analysis correctness).
3. M5, L1 (security/correctness, small).
4. M3, M4 (protocol/docs/packaging) — M3 may need a product decision.
5. Verification-health cleanup.

Open decisions to confirm before coding: **H3** (implement JSON vs. drop it) and
**M3** (implement PKCE vs. fix docs).

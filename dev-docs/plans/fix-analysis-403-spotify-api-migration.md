# Fix Playlist Analysis 403 - Spotify February 2026 Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop backend playlist analysis from failing when Spotify rejects removed batch artist endpoints.

**Architecture:** Keep all Spotify API calls inside `src/backend/services/spotify.ts`. Replace the removed batch artist lookup with individual artist requests and make artist metadata best-effort so playlist analysis still returns duration and artist counts when genre lookup fails.

**Tech Stack:** TypeScript, Cloudflare Worker, Hono, Vitest, Spotify Web API.

---

## Problem

Playlist analysis can fail with HTTP 403 when fetching artist data:

```text
[ERROR] Playlist analysis failed: Analysis failed: HTTP 403: Forbidden
```

The current risk is here:

- `src/backend/services/spotify.ts#getArtists()` calls `GET /artists?ids=...`
- `src/backend/services/analysis.ts#analyzePlaylist()` calls `spotifyService.getArtists([...artistIdSet])`

Spotify's February 2026 Development Mode migration removed batch/bulk fetch endpoints for affected apps. The migration guide says batch endpoints such as `GET /artists` should be replaced with individual item fetches such as `GET /artists/{id}`.

## Important Constraints

- All Spotify API calls must stay in `src/backend/services/spotify.ts`.
- Do not restore Spotify `/audio-features` into analysis. That is a separate removed/restricted endpoint family and is not needed for this fix.
- `genres` on Spotify Artist is currently available but deprecated in Spotify docs. Treat genre distribution as best-effort.
- Increased request count can make large playlists slow. Use conservative concurrency and keep graceful degradation.
- Coordinate with `dev-docs/plans/reccobeats-wiring.md`; this plan is Track A's dependency.

---

## Task 1 - Add `getArtist()` and Replace Batch Artist Fetching

**Files:**
- Modify: `src/backend/services/spotify.ts`
- Test: add or update service-level tests for `SpotifyService` in `src/backend/tests/spotify-service.test.ts` or the existing closest service test file.

- [ ] Add a public single-artist method:

```ts
async getArtist(artistId: string): Promise<SpotifyArtistFull> {
  const response = await this.fetchWithRetry(`${this.baseUrl}/artists/${artistId}`);
  const rawData = await response.json();
  parseSpotifyResponse<Record<string, unknown>>(rawData, ['id', 'name']);
  return rawData as SpotifyArtistFull;
}
```

- [ ] Replace `getArtists()` so it no longer calls `/artists?ids=...`.

```ts
async getArtists(artistIds: string[]): Promise<SpotifyArtistFull[]> {
  const uniqueIds = [...new Set(artistIds.filter(Boolean))];
  return this.fetchWithConcurrency(uniqueIds, (id) => this.getArtist(id), 5);
}
```

- [ ] Add a private bounded-concurrency helper that preserves input order:

```ts
private async fetchWithConcurrency<T>(
  items: string[],
  fetchFn: (item: string) => Promise<T>,
  concurrency = 5
): Promise<T[]> {
  const results: T[] = [];
  let nextIndex = 0;

  const workers = Array.from(
    { length: Math.min(concurrency, items.length) },
    async () => {
      while (nextIndex < items.length) {
        const currentIndex = nextIndex;
        nextIndex += 1;
        results[currentIndex] = await fetchFn(items[currentIndex]);
      }
    }
  );

  await Promise.all(workers);
  return results;
}
```

- [ ] Add a test that fails before the change:
  - mock `globalThis.fetch`
  - call `getArtists(['artist1', 'artist2'])`
  - assert requests are made to `/artists/artist1` and `/artists/artist2`
  - assert no request is made to `/artists?ids=...`

- [ ] Add a test for de-duplication:
  - `getArtists(['artist1', 'artist1'])`
  - assert only one HTTP request is sent.

## Task 2 - Preserve Rate-Limit Behavior

**Files:**
- Modify: `src/backend/services/spotify.ts`
- Test: `src/backend/tests/spotify-service.test.ts` or closest service test file.

- [ ] Keep the existing `fetchWithRetry()` 429 handling.
- [ ] Add a test where the first artist request returns `429` with `Retry-After: 1`, then returns `200`.
- [ ] Use fake timers or a small injected wait helper if the existing test framework supports it; do not make tests sleep for real seconds.

If adding fake timers requires too much refactor, preserve this item by writing a narrower test that asserts `fetchWithRetry()` reads `Retry-After` through a mocked sleep helper.

## Task 3 - Make Artist Fetch Best-Effort in Analysis

**Files:**
- Modify: `src/backend/services/analysis.ts`
- Test: `src/backend/tests/analysis.test.ts`

- [ ] Wrap only the artist fetch in a `try/catch`.

```ts
let artistData: SpotifyArtistFull[] = [];
try {
  artistData = await spotifyService.getArtists([...artistIdSet]);
} catch (error) {
  console.warn('Failed to fetch Spotify artist metadata; continuing without genre insights', {
    playlistId,
    artistCount: artistIdSet.size,
    error: error instanceof Error ? error.message : String(error),
  });
}
```

- [ ] Keep track and overview analysis outside this `try/catch`; failures to fetch playlist tracks should still fail the analysis job.
- [ ] Add a test that simulates `getArtists()` throwing `HTTP 403: Forbidden`.
- [ ] Assert `analyzePlaylist()` still returns:
  - `status: "completed"`
  - populated `overview`
  - populated `artists.unique_artists`
  - empty `genre_distribution`

## Task 4 - Verify Pagination Is Not Regressed

**Files:**
- Modify: `src/backend/tests/analysis.test.ts`
- Reference: `src/backend/services/analysis.ts`

- [ ] Add a regression test for the current `rawCount` pagination behavior:
  - page 1 raw count is full page size
  - normalized item count is lower because some entries are local/unavailable
  - page 2 is still fetched

This keeps the older "fix pagination" TODO tracked without applying its stale implementation.

## Task 5 - Update Documentation

**Files:**
- Modify: `docs/february-2026-spotify-migration-findings.md`
- Modify if needed: `dev-docs/backend-analysis-routes.md`
- Modify if needed: `dev-docs/playlist-analysis-popup.md`
- Modify if needed: `dev-docs/code-map.md`
- Modify if needed: `dev-docs/plans/reccobeats-wiring.md`

- [ ] Document that backend playlist analysis now fetches artist metadata individually.
- [ ] Document that genre data is best-effort because Spotify marks artist `genres` deprecated.
- [ ] Remove or correct stale claims that `/results` always returns 404.
- [ ] Remove or correct stale references to deleted `src/backend/services/reccobeats.ts`.
- [ ] Keep the ReccoBeats restoration work tracked in `reccobeats-wiring.md`; do not fold that contract spike into this Spotify-only fix.

---

## Verification Checklist

- [ ] `cd src/backend && npm run test:run`
- [ ] `cd src/backend && npm run lint`
- [ ] `cd src/backend && npm run build`
- [ ] `cd src/backend && npx wrangler deploy --dry-run`
- [ ] Analysis completes when `GET /artists/{id}` succeeds.
- [ ] Analysis completes without genre data when artist fetch returns 403.
- [ ] No backend analysis code calls Spotify `GET /artists?ids=...`.
- [ ] No backend analysis code calls Spotify `/audio-features`.

## Follow-Up Items Preserved From Earlier Plan

- Performance tuning for large playlists remains tracked in `reccobeats-wiring.md` Track D.
- ReccoBeats restoration remains tracked in `reccobeats-wiring.md` Track B.
- API-key cleanup remains tracked in `reccobeats-wiring.md` Track C.

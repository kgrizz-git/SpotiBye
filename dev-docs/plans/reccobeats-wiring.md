# Plan: Fix ReccoBeats Pipeline & Wire Analysis to Backend Route

**Goal:** Make the Playlist Analysis popup in the frontend populate with enhanced data — genre distribution from ReccoBeats, artist stats, duration — sourced from the Cloudflare Worker calling Spotify and ReccoBeats.

**Status:** ⬜ Phase 1 | ⬜ Phase 2 | ⬜ Phase 3 (optional)

**Background reading:**
- [playlist-analysis-popup.md](../playlist-analysis-popup.md) — blockers summary + what the popup expects
- [backend-analysis-routes.md](../backend-analysis-routes.md) — detailed route-level analysis and existing fix suggestions

**Current state:**
- Backend has `callReccoBeatsAPI()` method but it's never called
- `analyzePlaylist()` uses Spotify metadata only (tracks, artist genres) — no ReccoBeats integration
- Spotify `/audio-features` was removed in Feb 2026 API migration (returns 403)
- ReccoBeats API does not require an API key (per https://reccobeats.com/docs/documentation/introduction)

---

## Summary table

| Phase | Scope | Est. | Risk | Status |
|---|---|---|---|---|
| 1 | Fix TypeScript backend blockers | 1–2 h | low | ⬜ |
| 2 | Normalize result schema + wire Python parser | 1–2 h | low | ⬜ |
| 3 | Queues for large playlists (production hardening) | 3–4 h | medium | ⬜ optional |

---

## Phase 1 — Fix TypeScript backend blockers

All changes in this phase are in `src/backend/`. No Python changes needed.

### 1-A  Fix the ReccoBeats URL typo

**File:** [src/backend/services/analysis.ts:51](../../src/backend/services/analysis.ts#L51)

```ts
// Before
private reccoBeatsUrl = 'https://api.recocbeats.com/v1';

// After
private reccoBeatsUrl = 'https://api.reccobeats.com/v1';
```

> **Note before deploying:** verify the actual ReccoBeats hostname and that the `/analyze` endpoint path is correct per ReccoBeats documentation.

### 1-B  Remove unused API key infrastructure

Since ReccoBeats does not require an API key, remove the unused infrastructure:

**File:** [src/backend/types/env.ts](../../src/backend/types/env.ts)

Remove `RECCOBEATS_API_KEY` and `RECOCOBEATS_API_KEY` (if present).

**File:** [src/backend/.env.test](../../src/backend/.env.test)

Remove `RECOCOBEATS_API_KEY`.

**File:** [src/backend/tests/setup.ts](../../src/backend/tests/setup.ts)

Remove `process.env.RECOCOBEATS_API_KEY`.

**All test files:** Remove `RECOCOBEATS_API_KEY` from mock env objects.

**File:** [src/backend/services/analysis.ts](../../src/backend/services/analysis.ts)

Remove `reccoBeatsApiKey` parameter from constructor and remove auth header from `callReccoBeatsAPI()`.

### 1-C  Fix track pagination — currently only first 100 tracks are analyzed

**File:** [src/backend/services/analysis.ts](../../src/backend/services/analysis.ts)

Replace the single `getPlaylistTracks(playlistId, 100, 0)` call with full pagination:

```ts
// Collect all tracks across pages
const allItems: any[] = [];
let offset = 0;
const limit = 50;
while (true) {
  const page = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
  allItems.push(...page.items);
  if (allItems.length >= page.total || page.items.length < limit) break;
  offset += limit;
}
const tracks = allItems
  .map((item: SpotifyPlaylistTrackItem) => item.track ?? item.item)
  .filter((t): t is SpotifyTrack => t?.id !== undefined);
```

---

## Phase 2 — Normalize result schema and wire Python parser

### 2-A  Define the canonical KV result schema

After Phase 1 the `results` key in KV will hold the merged Spotify + ReccoBeats response. Define a stable shape that both the TypeScript writer and the Python reader agree on.

**Proposed schema** (write this to `analysis:{playlistId}:{userId}:results`):

```json
{
  "playlist_id": "...",
  "computed_at": "2026-05-07T12:00:00Z",
  "overview": {
    "total_tracks": 266,
    "total_duration_ms": 75672000,
    "formatted_duration": "21h 1m 12s"
  },
  "artists": {
    "unique_artists": 224,
    "diversity": 0.84,
    "top_artists": [
      { "artist": "Solvent", "count": 22 },
      { "artist": "Matthew Dear", "count": 16 }
    ]
  },
  "genre_distribution": {
    "Electronic/Dance": { "count": 92, "percentage": 34.6 },
    "Other": { "count": 213, "percentage": 55.0 }
  },
  "insights": ["High energy playlist..."],
  "reccobeats_raw": { ... }
}
```

The `overview`, `artists`, and `insights` sections come from `generatePlaylistInsights()` (Spotify metadata: tracks, artist genres). The `genre_distribution` and `reccobeats_raw` come from the ReccoBeats response.

**Note:** Audio features (danceability, energy, etc.) are NOT included since Spotify `/audio-features` is no longer available.

**File:** [src/backend/services/analysis.ts](../../src/backend/services/analysis.ts)

Update `analyzePlaylist()` to:
1. Fetch all tracks via pagination
2. Fetch artist data for genre information
3. Call `generatePlaylistInsights()` on Spotify metadata
4. Call `callReccoBeatsAPI()` with track data
5. Merge results

```ts
const spotifyInsights = await this.generatePlaylistInsights(tracks, artistData);
const reccoBeatsResult = await this.callReccoBeatsAPI({ tracks: tracks.map(t => t.id) });

return {
  playlist_id: playlistId,
  computed_at: new Date().toISOString(),
  ...spotifyInsights,
  genre_distribution: reccoBeatsResult.genre_distribution ?? {},
  reccobeats_raw: reccoBeatsResult
};
```

Ensure `diversity` is in `generatePlaylistInsights`:
```ts
diversity: totalTracks > 0 ? Object.keys(artistCounts).length / totalTracks : 0,
```

### 2-B  Return Spotify-only stats immediately from the POST handler (no ReccoBeats wait)

This gives the popup something useful to show within seconds rather than waiting for the full ReccoBeats round-trip.

**File:** [src/backend/routes/analysis.ts](../../src/backend/routes/analysis.ts)

Before firing `waitUntil`, compute and store partial results synchronously:

```ts
// Quick Spotify-only pass (no ReccoBeats call yet)
const partialResults = await analysisService.computeSpotifyStats(playlistId);
await cacheService.set(resultsKey, { ...partialResults, status: 'partial' }, 3600);
await cacheService.set(statusKey, { ...status, status: 'processing' }, 3600);

// Full analysis (incl. ReccoBeats) in background
c.executionCtx.waitUntil( /* ... as above, overwrites with complete results ... */ );
```

This requires extracting `computeSpotifyStats()` as a separate method in `AnalysisService` that fetches tracks + artist data and returns `generatePlaylistInsights()` output, without calling ReccoBeats.

### 2-C  Update the Python popup parser to match the schema

**File:** [src/frontend/ui/backend_playlist_card.py](../../src/frontend/ui/backend_playlist_card.py) — `_update_analysis_ui()`

Verify the parser handles the updated schema:
- `results.overview.formatted_duration` — ✅ already handled
- `results.genre_distribution` as `{genre: {count, percentage}}` — ✅ already handled
- `results.artists.unique_artists` / `.diversity` / `.top_artists` — ✅ already handled
- Remove any references to `audio_features` since they're no longer available

Also verify `_load_analysis_worker()` flows through correctly in `ReccoBeatsBackendService._poll_analysis_completion()`.

> The Python poller in [src/frontend/services/reccobeats_backend.py](../../src/frontend/services/reccobeats_backend.py) already calls `get_analysis_results()` when status is `completed`. No Python changes needed for the happy path — just verify end-to-end after the TypeScript fixes land.

---

## Phase 3 — Queues for large playlists (production hardening, optional)

`waitUntil` is a best-effort mechanism. For playlists with 500+ tracks the Spotify pagination + ReccoBeats call can push past Workers' 30-second CPU limit. The correct fix is to move the work off the request lifecycle entirely.

### 3-A  Add a Cloudflare Queue

In `wrangler.toml`:
```toml
[[queues.producers]]
queue = "analysis-jobs"
binding = "ANALYSIS_QUEUE"

[[queues.consumers]]
queue = "analysis-jobs"
max_batch_size = 1
max_retries = 3
```

Update `src/backend/types/env.ts`:
```ts
ANALYSIS_QUEUE: Queue<AnalysisJobMessage>;
```

Define the message type:
```ts
interface AnalysisJobMessage {
  playlistId: string;
  userId: string;
  jobId: string;
  accessToken: string;
}
```

### 3-B  Route handler enqueues, consumer does the work

**File:** [src/backend/routes/analysis.ts](../../src/backend/routes/analysis.ts)

Replace `waitUntil` + inline analysis with a queue send:
```ts
await c.env.ANALYSIS_QUEUE.send({ playlistId, userId, jobId, accessToken });
return c.json({ data: { ...status, status: 'queued' }, meta: ... });
```

**New file:** `src/backend/workers/analysis-consumer.ts`

```ts
export default {
  async queue(batch: MessageBatch<AnalysisJobMessage>, env: Env): Promise<void> {
    for (const msg of batch.messages) {
      const { playlistId, userId, jobId, accessToken } = msg.body;
      const svc = new AnalysisService(accessToken);
      const cache = new CacheService(env.CACHE_KV);
      const statusKey = `analysis:${playlistId}:${userId}:status`;
      const resultsKey = `analysis:${playlistId}:${userId}:results`;
      try {
        const result = await svc.analyzePlaylist(playlistId, userId, jobId);
        await cache.set(resultsKey, result, 86400);
        await cache.set(statusKey, { status: 'completed', completed_at: new Date().toISOString() }, 3600);
        msg.ack();
      } catch (err: any) {
        await cache.set(statusKey, { status: 'failed', error: err.message }, 3600);
        msg.retry();
      }
    }
  }
};
```

Export the consumer in `wrangler.toml` under a separate entry point so it runs as a distinct Worker.

---

## Verification checklist

After Phase 1 + 2:

- [ ] `POST /analysis/playlist/{id}` returns `{ status: 'processing' }` within 200 ms
- [ ] `GET /analysis/playlist/{id}/status` returns `completed` within ~15–30 s for a 100-track playlist
- [ ] `GET /analysis/playlist/{id}/results` returns the normalized JSON schema (not 404)
- [ ] Double-clicking a playlist card opens the Playlist Analysis popup
- [ ] Genre distribution and artist section populate (not "Retrieving analysis...")
- [ ] Duration label updates with the real total
- [ ] Analysis result is served from local Python cache on subsequent popup opens (no re-fetch)
- [ ] No `RECCOBEATS_API_KEY` references remain in code or tests

After Phase 3:

- [ ] Analysis for a 300-track playlist completes without Worker timeout
- [ ] If Worker restarts mid-analysis, the job retries automatically (Queue `max_retries`)
- [ ] Status correctly transitions `queued → processing → completed`

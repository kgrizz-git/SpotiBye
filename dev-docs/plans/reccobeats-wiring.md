# Plan: Fix ReccoBeats Pipeline & Wire Analysis to Backend Route

**Goal:** Make the Playlist Analysis popup in the frontend actually populate with real data — genre distribution, artist stats, duration, audio feature summary — sourced from the Cloudflare Worker calling Spotify and ReccoBeats.

**Status:** ⬜ Phase 1 | ⬜ Phase 2 | ⬜ Phase 3 (optional)

**Background reading:**
- [playlist-analysis-popup.md](../playlist-analysis-popup.md) — blockers summary + what the popup expects
- [backend-analysis-routes.md](../backend-analysis-routes.md) — detailed route-level analysis and existing fix suggestions

---

## Summary table

| Phase | Scope | Est. | Risk | Status |
|---|---|---|---|---|
| 1 | Fix four TypeScript backend blockers | 2–3 h | low | ⬜ |
| 2 | Normalize result schema + wire Python parser | 1–2 h | low | ⬜ |
| 3 | Queues for large playlists (production hardening) | 3–4 h | medium | ⬜ optional |

---

## Phase 1 — Fix the four TypeScript backend blockers

All changes in this phase are in `src/backend/`. No Python changes needed.

### 1-A  Fix the ReccoBeats URL typo

**File:** [src/backend/services/analysis.ts:5](../../src/backend/services/analysis.ts#L5)

```ts
// Before
private reccoBeatsUrl = 'https://api.recocbeats.com/v1';

// After
private reccoBeatsUrl = 'https://api.reccobeats.com/v1';
```

> **Note before deploying:** verify the actual ReccoBeats hostname and that the `/analyze` endpoint path is correct. The v2 Python path (`src/spotify_playlist_exporter_v2/services/reccobeats.py`) has the real base URL and endpoint shape — check it before assuming the hostname above is right.

Also add the API key to the auth header in `callReccoBeatsAPI`:

```ts
// Before
headers: { 'Content-Type': 'application/json' }

// After — read key from Env (passed in constructor, see 1-B)
headers: {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${this.reccoBeatsApiKey}`
}
```

### 1-B  Thread `RECCOBEATS_API_KEY` through env → service

**File:** [src/backend/types/env.ts](../../src/backend/types/env.ts)

```ts
// Add (and fix the RECOCOBEATS typo while we're here)
RECCOBEATS_API_KEY: string;
// Remove or keep as alias:
RECOCOBEATS_API_KEY?: string;  // deprecated spelling — remove once wrangler.toml updated
```

**File:** [src/backend/routes/analysis.ts](../../src/backend/routes/analysis.ts)

Pass key into `AnalysisService`:
```ts
const analysisService = new AnalysisService(accessToken, c.env.RECCOBEATS_API_KEY);
```

**File:** [src/backend/services/analysis.ts](../../src/backend/services/analysis.ts)

Update constructor:
```ts
constructor(accessToken: string, reccoBeatsApiKey: string = '') {
  this.accessToken = accessToken;
  this.reccoBeatsApiKey = reccoBeatsApiKey;
}
```

Also update `wrangler.toml` (or equivalent secrets config): rename `RECOCOBEATS_API_KEY` → `RECCOBEATS_API_KEY` in the deployed Worker's environment.

### 1-C  Use `ctx.waitUntil()` so the background work survives response send

**File:** [src/backend/routes/analysis.ts](../../src/backend/routes/analysis.ts)

Replace the detached `.catch()` with `c.executionCtx.waitUntil(...)`:

```ts
// Before — promise is killed when response is sent
analysisService.analyzePlaylist(playlistId, userId, jobId).catch(error => { ... });

// After — Worker stays alive until the promise resolves
const resultsKey = `analysis:${playlistId}:${userId}:results`;

c.executionCtx.waitUntil(
  analysisService.analyzePlaylist(playlistId, userId, jobId)
    .then(async (result) => {
      await cacheService.set(resultsKey, result, 86400);       // 24 h
      await cacheService.set(statusKey, {
        ...status,
        status: 'completed',
        completed_at: new Date().toISOString()
      }, 3600);
    })
    .catch(async (error) => {
      console.error('Analysis failed:', error);
      await cacheService.set(statusKey, {
        ...status,
        status: 'failed',
        error: error.message,
        completed_at: new Date().toISOString()
      }, 3600);
    })
);
```

> **Caveat:** `waitUntil` extends I/O lifetime but not CPU time. If Spotify + ReccoBeats calls exceed ~30 s, the Worker will still time out. For playlists under ~200 tracks this is unlikely to be an issue; for very large playlists, Phase 3 (Queues) is the proper fix.

### 1-D  Fix track pagination — currently only first 100 tracks are sent to ReccoBeats

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
const trackIds = allItems
  .filter(item => item.track?.id)
  .map(item => item.track.id);
```

### 1-E  Batch audio feature requests — Spotify limits to 100 IDs per call

**File:** [src/backend/services/analysis.ts](../../src/backend/services/analysis.ts)

Spotify's `/audio-features` endpoint rejects requests with more than 100 IDs. Batch them:

```ts
const audioFeatures: any[] = [];
for (let i = 0; i < trackIds.length; i += 100) {
  const batch = trackIds.slice(i, i + 100);
  const batchFeatures = await spotifyService.getMultipleAudioFeatures(batch);
  audioFeatures.push(...batchFeatures);
}
```

---

## Phase 2 — Normalize the result schema and wire the Python parser

### 2-A  Define the canonical KV result schema

After Phase 1 the `results` key in KV will hold whatever `AnalysisService.analyzePlaylist()` returns. That's currently the raw ReccoBeats response wrapped with job metadata. Define a stable shape that both the TypeScript writer and the Python reader agree on.

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
  "audio_features": {
    "avg_danceability": 0.62,
    "avg_energy": 0.71,
    "avg_valence": 0.45,
    "avg_tempo": 128.4,
    "avg_acousticness": 0.12
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

The `overview`, `audio_features`, and `artists` sections come from `generatePlaylistInsights()` (Spotify-only, no ReccoBeats dependency). The `genre_distribution` and `reccobeats_raw` come from the ReccoBeats response.

**File:** [src/backend/services/analysis.ts](../../src/backend/services/analysis.ts)

Update `analyzePlaylist()` to call `generatePlaylistInsights()` on the Spotify data and merge it with the ReccoBeats response:

```ts
const spotifyInsights = await this.generatePlaylistInsights(
  allItems.map(item => item.track),
  audioFeatures
);
const reccoBeatsResult = await this.callReccoBeatsAPI(analysisData);

return {
  playlist_id: playlistId,
  computed_at: new Date().toISOString(),
  ...spotifyInsights,
  genre_distribution: reccoBeatsResult.genre_distribution ?? {},
  reccobeats_raw: reccoBeatsResult
};
```

Add `diversity` to `generatePlaylistInsights`:
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

This requires extracting `computeSpotifyStats()` as a separate method in `AnalysisService` that fetches tracks + audio features and returns `generatePlaylistInsights()` output, without calling ReccoBeats.

### 2-C  Update the Python popup parser to match the schema

**File:** [src/frontend/ui/backend_playlist_card.py](../../src/frontend/ui/backend_playlist_card.py) — `_update_analysis_ui()`

The current parser already handles the proposed schema shape but was written speculatively. Once Phase 2-A defines the real schema, verify and adjust:

- `results.overview.formatted_duration` — ✅ already handled
- `results.genre_distribution` as `{genre: {count, percentage}}` — ✅ already handled
- `results.artists.unique_artists` / `.diversity` / `.top_artists` — ✅ already handled
- `results.audio_features.avg_energy` etc. — currently not shown in popup; add if desired

Also update the `_load_analysis_worker()` in the same file: after the analysis `status` goes `completed`, the adapter calls `get_analysis_results()` to fetch the results key. Confirm this flows through correctly in `ReccoBeatsBackendService._poll_analysis_completion()`.

> The Python poller in [src/frontend/services/reccobeats_backend.py](../../src/frontend/services/reccobeats_backend.py) already calls `get_analysis_results()` when status is `completed`. No Python changes needed for the happy path — just verify end-to-end after the TypeScript fixes land.

### 2-D  Fix environment variable naming

Remove the `RECOCOBEATS` typo everywhere. Files to update:

| File | Change |
|---|---|
| [src/backend/types/env.ts](../../src/backend/types/env.ts) | Remove `RECOCOBEATS_API_KEY`, keep only `RECCOBEATS_API_KEY` |
| [src/backend/.env.test](../../src/backend/.env.test) | Rename key |
| [src/backend/tests/setup.ts](../../src/backend/tests/setup.ts) | Rename key |
| All test files that set `RECOCOBEATS_API_KEY` | Rename key |
| `wrangler.toml` / Cloudflare dashboard | Rename the deployed secret |

---

## Phase 3 — Queues for large playlists (production hardening, optional)

`waitUntil` is a best-effort mechanism. For playlists with 500+ tracks the Spotify pagination + batch audio features + ReccoBeats call can push past Workers' 30-second CPU limit. The correct fix is to move the work off the request lifecycle entirely.

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
      const svc = new AnalysisService(accessToken, env.RECCOBEATS_API_KEY);
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
- [ ] `RECCOBEATS_API_KEY` (no typo) is the only spelling in env types and tests

After Phase 3:

- [ ] Analysis for a 300-track playlist completes without Worker timeout
- [ ] If Worker restarts mid-analysis, the job retries automatically (Queue `max_retries`)
- [ ] Status correctly transitions `queued → processing → completed`

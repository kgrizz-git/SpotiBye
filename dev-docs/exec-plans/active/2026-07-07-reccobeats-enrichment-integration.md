# ReccoBeats Enrichment Integration — Full Playlist Analysis

**Status:** Ready for implementation
**Date:** 2026-07-07 (last reviewed 2026-07-08)
**Source:** [Backlog TO_DO.md#reccobeats-enrichment-gaps](../../backlog/TO_DO.md#reccobeats-enrichment-gaps)
**Assessments:** Iterated in `tmp/*reccobeats*assessment*.md` — latest `tmp/2026-07-08T220000Z-reccobeats-enrichment-integration-plan-gap-assessment.md` (gaps folded into plan 2026-07-08)

## Goal

Fully integrate ReccoBeats enrichment for **playlist analysis**: display all retrieved audio features, add track metadata aggregates, reconcile OpenAPI with implementation.

### Scope

| In scope | Out of scope (separate follow-up) |
|----------|-----------------------------------|
| ReccoBeats enrichment in `AnalysisService` | Removing dead Spotify `/audio-features` from `SpotifyService` |
| Analysis popup UI | Export audio features migration to ReccoBeats |
| OpenAPI/doc reconciliation for analysis | `GET /spotify/tracks/:id/audio-features` proxy removal |
| Raw-enrichment KV cache (analysis) | `time_signature` in exports (Spotify-only) |

**Already true:** `AnalysisService` uses ReccoBeats (`api.reccobeats.com/v1/audio-features`), not Spotify `/audio-features`. Export still calls dead Spotify endpoints when `include_audio_features: true` (frontend currently sends `false`).

### Spotify endpoints (Feb 2026 Dev Mode)

| Endpoint | Status | Still in code? |
|----------|--------|----------------|
| `GET /v1/audio-features/{id}` and `?ids=...` | Removed/restricted | Yes — `SpotifyService`, export path |
| `GET /v1/artists?ids=...` | Removed | No — individual `GET /artists/{id}` |
| `GET /v1/playlists/{id}/tracks` | Renamed → `/items` | Migrated |

Details: [`february-2026-spotify-migration-findings.md`](../investigations/february-2026-spotify-migration-findings.md)

## References

- [2026-07-05-reccobeats-enrichment-gaps.md](../investigations/2026-07-05-reccobeats-enrichment-gaps.md)
- [reccobeats-api-contract.md](../reccobeats-api-contract.md)
- ReccoBeats docs: https://reccobeats.com/docs/apis/get-audio-features · https://reccobeats.com/docs/apis/get-tracks

---

## Implementation Plan

### Phase 0: Shared Constants & Utilities

- [ ] Create `src/backend/utils/constants.ts`:
  - `MUSIC_KEYS`, `MODE_NAMES` — **new shared names** extracted from inline `keyMap` / `modeMap` in `mapTrackForExport` (`export-tracks.ts`)
  - `ANALYSIS_SCHEMA_VERSION = '1.0'`
  - `RECCOBEATS_JITTER_DELAY_MS = 50`
  - `ANALYSIS_RESULTS_TTL_SECONDS = 86400` (env-overridable)
  - Unit test: `MUSIC_KEYS.length === 12` and `MUSIC_KEYS[0] === 'C'`
- [ ] Create `src/backend/utils/music-helpers.ts`:
  - `keyName(key): string | null` — name for 0–11, else `null`
  - `modeName(mode): string | null` — `'minor'`/`'major'` for 0/1, else `null`
  - Callers map `null` → `'N/A'` (helpers must not return `'N/A'` — it is truthy and breaks export's `keyName ? ... : 'N/A'` pattern)
- [ ] Create `src/backend/utils/http-retry.ts` with `createFetchWithRetry(config)`:
  - **Import** the already-exported `parseRetryAfter` from `services/spotify.ts:224` — do **not** move or re-implement it (both `spotify.ts` and `http-retry.ts` import the same source)
  - **Signature:** returns a `fetch`-compatible function `(url, init?) => Promise<Response>`; `config = { maxRetries = 3, timeoutMs = 15000, backoffMs = 500 }`
  - 429 + `Retry-After`: honor header delay; **5xx backoff:** exponential (`backoffMs * 2^attempt`), retry up to `maxRetries`, then throw
  - **Workers timeout:** use `AbortController` + `setTimeout`/`clearTimeout` (or `Promise.race`), not `AbortSignal.timeout()` — not guaranteed on Workers. A timeout counts as a retryable attempt (retry up to `maxRetries`, then throw)
- [ ] Add OpenAPI test deps: the existing `js-yaml` entry (`package.json:40`) is a transitive-dependency **override pin** — **leave it in place, do not remove it**. Separately add `js-yaml` + `@types/js-yaml` to `devDependencies` so the new `openapi-schema.test.ts` can import it directly
- [ ] Update `mapTrackForExport` in `export-tracks.ts` to use shared constants/helpers only — **no other export changes** (still calls dead Spotify `/audio-features` when `include_audio_features: true`; frontend hardcodes `false`). The inline `keyMap`/`modeMap` at `export-tracks.ts:26-27` are **byte-identical** to `MUSIC_KEYS`/`MODE_NAMES` — this is a direct swap, not a semantic change
- [ ] Verify export tests pass

### Phase 0.5: Analysis Types

Move types from `services/analysis.ts` → `src/backend/types/analysis.ts`. **`analysis-job.ts:1`** imports `AnalysisResult` from `./analysis` today — update to `../types/analysis`. If `analysis.ts` still needs `AnalysisResult` internally, it imports it back from `../types/analysis` (single source of truth; no duplicate definition). `reccobeats_metadata` (on `PlaylistInsights`/`AnalysisResult`), `CachedRawEnrichment`, `KeyModeDistribution`, and the `errors`/`schema_version` fields are **new additions**; the rest are moves of existing (currently private) interfaces.

- [ ] Create `src/backend/types/analysis.ts`:

```typescript
export interface AudioFeatureAverages {
  acousticness: number;
  danceability: number;
  energy: number;
  instrumentalness: number;
  liveness: number;
  loudness: number;
  speechiness: number;
  tempo: number;
  valence: number;
}

export interface ReccoBeatsAudioFeature extends AudioFeatureAverages {
  /** ReccoBeats UUID — not the Spotify track ID (Spotify ID is in `href`). */
  id: string;
  href: string;
  isrc?: string | null;
  key?: number;
  mode?: number;
}

export interface ReccoBeatsAudioFeaturesResponse {
  content: ReccoBeatsAudioFeature[];
}

export interface KeyModeDistribution {
  /** Bare pitch-class labels: `"C"`, `"C#"`, … `"B"` (not `"C major"`). ReccoBeats `key` 0–11 = Spotify pitch class (0 = C). */
  key_percentages: Record<string, number>;
  dominant_key: string;
  dominant_key_percentage: number;
  mode_percentages: { major: number; minor: number };
  dominant_mode: 'major' | 'minor';
}

export interface AudioFeatureSummary {
  track_count: number;
  averages: AudioFeatureAverages;
  key_mode_distribution?: KeyModeDistribution;
}

export interface PlaylistInsights {
  overview: {
    total_tracks: number;
    total_duration_ms: number;
    average_duration_ms: number;
    formatted_duration: string;
  };
  artists: {
    unique_artists: number;
    top_artists: Array<{ artist: string; count: number }>;
    diversity: number;
  };
  genre_distribution: Record<string, { count: number; percentage: number }>;
  audio_features?: AudioFeatureSummary;
  insights: string[];
  reccobeats_metadata?: {
    isrc_available: number;
    popularity_min?: number;
    popularity_max?: number;
    retrieved_at: string;
  };
}

export interface AnalysisResult {
  job_id: string;
  playlist_id: string;
  user_id: string;
  status: string;
  computed_at: string;
  completed_at: string;
  overview?: PlaylistInsights['overview'];
  artists?: PlaylistInsights['artists'];
  genre_distribution?: PlaylistInsights['genre_distribution'];
  audio_features?: AudioFeatureSummary;
  insights?: string[];
  reccobeats_metadata?: PlaylistInsights['reccobeats_metadata'];
  errors: Array<{ source: string; message: string }>;
  schema_version: string;
}

export interface ReccoBeatsTrackMetadata {
  /** ReccoBeats UUID — not the Spotify track ID (Spotify ID is in `href` if present). */
  id: string;
  trackTitle: string;
  artists: Array<{ id: string; name: string; href: string }>;
  durationMs: number;
  isrc?: string;
  popularity?: number;
}

export interface ReccoBeatsTrackMetadataResponse {
  content: ReccoBeatsTrackMetadata[];
}

export interface CachedRawEnrichment {
  audio_features: ReccoBeatsAudioFeature[];
  track_metadata: ReccoBeatsTrackMetadata[];
  schema_version: string;
  cached_at: string;
  track_count: number;
}
```

- [ ] Update imports in `analysis.ts`, `analysis-job.ts`, and test files

### Phase 1: Key/Mode Aggregation + Error Handling

In `src/backend/services/analysis.ts`:

- [ ] Extend `AudioFeatureSummary` with `key_mode_distribution?: KeyModeDistribution`
- [ ] Update `aggregateReccoBeatsAudioFeatures`:
  - Valid key/mode: `typeof f.key === 'number'` (key `0` is valid), same for `mode` in `{0,1}`
  - `key_percentages` keys = bare note names via `MUSIC_KEYS[f.key]` (`"C"`, `"C#"`, …)
  - UI display combines `dominant_key` + `dominant_mode` → `"C major"` (same as export's `keyName` + `modeName` pattern)
  - Omit `key_mode_distribution` if fewer than 2 tracks have valid key/mode
- [ ] `isReccoBeatsAudioFeature`: no change for optional `key`/`mode`; `isrc` optional at guard level
- [ ] Refactor `fetchReccoBeatsAudioFeaturesBatch` → shared `createFetchWithRetry` (do not change `SpotifyService.fetchWithRetry` — backlog consolidation)
- [ ] Jitter `RECCOBEATS_JITTER_DELAY_MS` between batch groups in the **audio-features** fetch chain only (metadata parallelization is Phase 2). **Insertion point:** after each concurrency chunk's `Promise.all` resolves and before the next chunk starts (`analysis.ts:185-202`), not between individual requests within a chunk
- [ ] Delete dead code: `calculateDistribution` (`analysis.ts:369`), `getAnalysisJobStatus` (`analysis.ts:229`), and orphaned `JobStatus` interface (`analysis.ts:27`) — all confirmed no callers
- [ ] **Create** `src/backend/utils/logger.ts`; replace **all** `console.log`/`console.warn`/`console.error` in `analysis.ts` (no `console.*` left — Golden Principle #5). **Logger scope for this plan is `analysis.ts` only.** `console.*` in `analysis-job.ts:39`, `routes/analysis.ts`, `cache.ts`, `export-*.ts` etc. are **out of scope** (backend-wide `console.*` migration is a separate `TO_DO.md` item)
- [ ] In `analyzePlaylist`, declare `const errors: Array<{ source: string; message: string }> = []` at the **top of the try block** (in scope for all operations); push Spotify artist-fetch failures (e.g. `{ source: 'spotify:artists', message }`) instead of the current swallow-and-continue. Note: the result-object return statement gains `errors` and `schema_version` fields in **Phase 2** (when the try/catch is restructured into `Promise.allSettled`); Phase 1 only introduces the `errors[]` array and the artist-fetch push
- [ ] Tests: key/mode aggregation cases; update mocks with `key: 0`, `mode: 1`

### Phase 2: Track Metadata + Caching + Schema Version

- [ ] `fetchReccoBeatsTrackMetadata` for `GET /v1/track?ids=...` (batch 50, concurrency 3, shared retry)
  - **Popularity:** collect all `popularity` values order-independently (min/max only; no index zip, no batch skip on length mismatch)
- [ ] `isReccoBeatsTrackMetadataResponse` type guard: `content` is array; each item has `id`, `trackTitle` strings; `artists` array with `{ id, name, href }` strings; `durationMs` number; optional `isrc` string and `popularity` number (skip missing values in min/max and ISRC aggregates — do not fail the whole batch)
- [ ] `generatePlaylistInsights` (make **private**): 4th param `reccoBeatsMetadata[]`
  - `isrc_available`: count audio-features items with `typeof f.isrc === 'string' && f.isrc.length > 0`
  - `popularity_min`/`popularity_max`: only from metadata items where `typeof popularity === 'number'`; **omit both fields entirely** from `reccobeats_metadata` when no item has a numeric `popularity`
  - `retrieved_at`: `new Date().toISOString()` at analysis time
- [ ] `analyzePlaylist`: parallel `Promise.allSettled` for **both** ReccoBeats chains (audio features + track metadata); remove legacy single-chain try/catch and old 75%/90% progress emissions; accumulate into the shared `errors[]` from Phase 1; return `errors` + `schema_version: ANALYSIS_SCHEMA_VERSION`
- [ ] `emittedWarmKeepalive` instance flag on `AnalysisService` — emit 70% progress once after the first successful ReccoBeats batch group so long retry loops do not look stalled to the frontend poller
- [ ] Thread optional `onProgress` into batch fetchers; emit 70% after first successful batch group (guarded by `emittedWarmKeepalive`)
- [ ] `compareVersions(a, b)` in `src/backend/utils/version.ts` — parses `"major.minor"` positive integers (no `v` prefix, no pre-release), **returns `-1 | 0 | 1`** (numeric compare, so `"1.10" > "1.9"`); callers use `compareVersions(schema_version, ANALYSIS_SCHEMA_VERSION) < 0` for the stale check (document in file comment)
- [ ] **Stale re-enqueue (POST)** in `src/backend/routes/analysis.ts` `POST /playlist/:id`: when `existingStatus.status === 'completed'`, also read `resultsKey` (**a second KV read on the completed hot path** — acceptable; status-key hit is fast); if results missing or `schema_version` missing/`compareVersions(...) < 0`, **do not** return early — delete `statusKey` + `resultsKey` and enqueue a fresh job (today's POST at `routes/analysis.ts:27-41` always returns completed status without re-enqueueing and never reads `resultsKey`)
- [ ] **Stale GET results check** in `GET /playlist/:id/results`: if `schema_version` missing or `< ANALYSIS_SCHEMA_VERSION`, delete **both** `resultsKey` and `statusKey`, return `404` `ANALYSIS_RESULTS_NOT_FOUND`
- [ ] `ANALYSIS_RESULTS_TTL_SECONDS` in `analysis-job.ts` (replace hardcoded 86400); **keep write order:** results key first, then status `completed`
- [ ] **Frontend stale-results recovery** — call chain: `AnalysisMixin.analyze_playlist` → `ReccoBeatsBackendService.analyze_playlist` → `_poll_analysis_completion`:
  - **Local cache** (`get_cached_analysis` → `_load_cache_file` returns the **unwrapped** `data`, i.e. the `AnalysisResult`, not the `{data, timestamp, ttl}` envelope — confirmed `backend_cache.py:350`): if `cached.get('schema_version')` missing or older than expected, invalidate local cache, then call `reccobeats_service.analyze_playlist` (do not return stale file cache). Define `EXPECTED_ANALYSIS_SCHEMA_VERSION = '1.0'` as a module-level constant in the frontend analysis mixin (hardcoded, with a comment pointing to backend `ANALYSIS_SCHEMA_VERSION`); no shared config module needed
  - **Poll loop** (`_poll_analysis_completion`): wrap `get_analysis_results` in try/except; on `error_code == 'ANALYSIS_RESULTS_NOT_FOUND'`, invalidate local cache and re-POST once (`_reposted_on_stale` guard). POST stale re-enqueue (above) must be in place or re-POST returns the old completed status with no new job
  - Test: stale KV results → fresh analysis completes with `schema_version: '1.0'`
- [ ] **Raw enrichment cache** (key `analysis:playlist:${playlistId}:raw-enrichment` — **no `userId`**; playlist-derived, shareable; comment at key construction). **This intentionally deviates** from the `analysis:${playlistId}:${userId}:*` namespacing used by the status/results keys — raw ReccoBeats data is user-agnostic, so sharing it across users for the same playlist is safe and saves duplicate fetches; document the deviation in the key-construction comment:
  - Read: on hit with matching `schema_version` and `track_count` matching current playlist, use cached arrays; **re-fetch any chain whose cached array is empty**
  - Write: cache partial success — store populated arrays and `[]` for failed chains; include `cached_at` and `track_count`
- [ ] Progress: 20 (tracks) → 50 (artists) → 65 (before parallel ReccoBeats fetches) → 70 (first batch group, once) → 85 (fetches done) → 95 (insights)
- [ ] Tests: metadata parsing; audio-features OK + metadata 503; partial `errors[]`; parallel success/fail combos; stale GET deletes both KV keys; POST re-enqueues when completed but results stale

### Phase 3: Frontend Analysis Popup

Extends existing analysis UI in `src/frontend/ui/backend_playlist_card.py` (not a separate screen).

- [ ] **Author mockup** `dev-docs/investigations/2026-07-07-reccobeats-ui-mockup.md` (a11y labels/order; **no axe-core** — Kivy has no DOM)
- [ ] Structured audio features layout (all 9 + key/mode); loudness as `{value} dB`
- [ ] Valence → mood bands (upper bound exclusive except the last, which is inclusive):

  | Range | Mood |
  |-------|------|
  | [0.00, 0.20) | Melancholic |
  | [0.20, 0.40) | Somber |
  | [0.40, 0.60) | Neutral |
  | [0.60, 0.80) | Cheerful |
  | [0.80, 1.00] | Euphoric |
- [ ] `reccobeats_metadata` aggregates (ISRC count, popularity range)
- [ ] Partial-failure banner from `errors[]`
- [ ] Defensive access: `result.get('audio_features') or {}`, `.get('averages')`, `.get('reccobeats_metadata')`; omit new sections when `schema_version` absent (compare against `EXPECTED_ANALYSIS_SCHEMA_VERSION` from the mixin — see Phase 2 frontend recovery step)
- [ ] Key/mode display: combine `dominant_key` + `dominant_mode` → `"C major"` (bare keys in `key_percentages` are not display-ready)
- [ ] Tests: all features; `N/A` for missing; no crash without `audio_features`; **Phase 1-shaped result** (no `schema_version`, new fields absent) renders without crash; valence boundary cases

### Phase 4: OpenAPI Reconciliation

Split schemas in `src/backend/docs/openapi.yaml`: shared `ApiEnvelope`, `AnalysisStartResponse` (POST) vs `AnalysisResultsResponse` (GET). Comment in `routes/analysis.ts` POST handler that body is ignored. Update `src/backend/docs/api-examples.md`.

**Delete from analysis schemas/examples only** (do **not** remove `include_audio_features` from **export** request bodies at `openapi.yaml` ~460–467, ~990):

- Analysis response: `duration_minutes`, `average_bpm`, `bpm_distribution`, `energy_score`, `recommendations`, `similar_playlists`, `SimilarPlaylist` schema
- Analysis request (`AnalysisRequest`): `include_recommendations` only (POST ignores body today; simplify to empty schema)
- GET analysis results: remove `analysis` wrapper sub-object (flat `data: { job_id, playlist_id, overview, … }`)

**Add to match `AnalysisResult`:** `overview`, `artists`, `genre_distribution`, `audio_features` (with `key_mode_distribution`), `insights`, `reccobeats_metadata`, `schema_version`, `errors`

- [ ] **New** `src/backend/tests/openapi-schema.test.ts` (schema/example validation — complements, does not replace, `analysis.test.ts` / `api-coverage.test.ts`). This is an **integration-style** test that drives the real job pipeline, then validates its output against the spec:
  - Mock `Env` with `CACHE_KV`, `SESSIONS_KV`, `ANALYSIS_QUEUE`; seed `SESSIONS_KV` with test token (or mock `SpotifyService` at boundary)
  - Mock `fetch` for ReccoBeats per contract; drive `AnalysisJobService.process`
  - Parse `openapi.yaml` at test time with `js-yaml` (the dev-dependency added in Phase 0)
  - **Rigor level (pick the lighter, less-fragile check):** assert the spec's `AnalysisResultsResponse` **example key-paths exist** on the live response (example ⊆ response). Do **not** attempt full JSON-Schema `$ref` resolution/validation — only additionally assert that the resolved `AnalysisResult` **required-field names** are all present (name presence, not type validation)
- [ ] **New** `src/backend/tests/analysis-pipeline.test.ts`: end-to-end KV population via `AnalysisJobService.process`

### Phase 5: Recommendations — Deferred

Keep on `TO_DO.md`. `GET /v1/track/recommendation` needs separate UI/caching design.

---

## Deployment

1. Backend Phase 1 → Phase 2 (includes POST stale re-enqueue + GET stale purge) → Frontend Phase 3
2. Frontend must tolerate results without `schema_version` between Phase 1 and Phase 2 deploys
3. After Phase 2 deploy, stale pre-`schema_version` KV entries trigger re-analysis via POST/GET stale checks (not TTL alone)
4. Optional: `ANALYSIS_RESULTS_TTL_SECONDS=3600` for 24h post-deploy
5. Rollback is safe (additive optional fields)

### Error handling (ReccoBeats batches)

| Scenario | Behavior |
|----------|----------|
| 429 / 5xx | Retry (up to 3), then throw |
| 4xx non-429 | Fail batch immediately |
| Timeout | `AbortController` + timer per attempt; retry up to 3, then throw |
| Malformed body | Type guard throws |
| Exhausted retries | `Promise.allSettled` → partial result + `errors[]` |

### Decisions

- ReccoBeats best-effort; analysis always completes
- `errors` always present (`[]` on success); includes Spotify artist-fetch and ReccoBeats partial failures
- ReccoBeats `id` fields are ReccoBeats UUIDs; Spotify track IDs live in `href` — aggregates do not join by `id`
- Raw-enrichment cache shared across users for same playlist; 24h TTL + `track_count` check mitigates playlist edits
- `SpotifyService.fetchWithRetry` unchanged; consolidate with `createFetchWithRetry` via backlog item
- Future: KV-based cross-invocation rate-limit tracking if 429s spike post-deploy

---

## Deferred Follow-ups

**Export & dead Spotify cleanup** (`TO_DO.md`): migrate `export-tracks.ts`, remove `getAudioFeatures`/`getMultipleAudioFeatures`, deprecate proxy route.

**Retry consolidation** (`TO_DO.md`): migrate `SpotifyService.fetchWithRetry` to `createFetchWithRetry`.

---

## Quality Checklist

- [ ] `CHANGELOG.md` — user-visible analysis features
- [ ] `QUALITY_SCORE.md` — ReccoBeats C, Analysis C+
- [ ] `spotify-api-reference.md` — mark `/audio-features` removed
- [ ] `TO_DO.md` — backlog entries for export migration + retry consolidation; uncheck enrichment item when done
- [ ] Move plan to `completed/` when finished

# ReccoBeats Enrichment Integration — Full Playlist Analysis

**Status:** Ready for implementation
**Date:** 2026-07-07 (last reviewed 2026-07-08)
**Source:** [Backlog TO_DO.md#reccobeats-enrichment-gaps](../../backlog/TO_DO.md#reccobeats-enrichment-gaps)
**Assessments:** Iterated in `tmp/*reccobeats*assessment*.md` — latest `tmp/2026-07-08-reccobeats-enrichment-plan-gap-assessment.md`

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
  - `MUSIC_KEYS`, `MODE_NAMES` (from `export-tracks.ts`)
  - `ANALYSIS_SCHEMA_VERSION = '1.0'`
  - `RECCOBEATS_JITTER_DELAY_MS = 50`
  - `ANALYSIS_RESULTS_TTL_SECONDS = 86400` (env-overridable)
  - Unit test: `MUSIC_KEYS.length === 12` and `MUSIC_KEYS[0] === 'C'`
- [ ] Create `src/backend/utils/music-helpers.ts`:
  - `keyName(key): string | null` — name for 0–11, else `null`
  - `modeName(mode): string | null` — `'minor'`/`'major'` for 0/1, else `null`
  - Callers map `null` → `'N/A'` (helpers must not return `'N/A'` — it is truthy and breaks export's `keyName ? ... : 'N/A'` pattern)
- [ ] Create `src/backend/utils/http-retry.ts` with `createFetchWithRetry(config)` (429 + `Retry-After`, 5xx backoff, `timeoutMs` default 15000)
- [ ] Add OpenAPI test deps: **keep** `js-yaml` in `package.json` `overrides` (transitive pin) **and** add `js-yaml` + `@types/js-yaml` to `devDependencies`
- [ ] Update `mapTrackForExport` in `export-tracks.ts` to use shared constants/helpers
- [ ] Verify export tests pass

### Phase 0.5: Analysis Types

Move types from `services/analysis.ts` → `src/backend/types/analysis.ts`. Update imports in `analysis.ts`, **`analysis-job.ts`** (currently imports `AnalysisResult` from `./analysis`), `routes/analysis.ts`, and tests.

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
  id: string;
  trackTitle: string;
  artists: Array<{ id: string; name: string; href: string }>;
  durationMs: number;
  isrc: string;
  popularity: number;
}

export interface ReccoBeatsTrackMetadataResponse {
  content: ReccoBeatsTrackMetadata[];
}

export interface CachedRawEnrichment {
  audio_features: ReccoBeatsAudioFeature[];
  track_metadata: ReccoBeatsTrackMetadata[];
  schema_version: string;
  cached_at: string;
}
```

- [ ] Update imports in `analysis.ts`, `analysis-job.ts`, `routes/analysis.ts`, and test files

### Phase 1: Key/Mode Aggregation + Error Handling

In `src/backend/services/analysis.ts`:

- [ ] Extend `AudioFeatureSummary` with `key_mode_distribution?: KeyModeDistribution`
- [ ] Update `aggregateReccoBeatsAudioFeatures`:
  - Valid key/mode: `typeof f.key === 'number'` (key `0` is valid), same for `mode` in `{0,1}`
  - Omit `key_mode_distribution` if fewer than 2 tracks have valid key/mode
- [ ] `isReccoBeatsAudioFeature`: no change for optional `key`/`mode`; `isrc` optional at guard level
- [ ] Refactor `fetchReccoBeatsAudioFeaturesBatch` → shared `createFetchWithRetry` (do not change `SpotifyService.fetchWithRetry` — backlog consolidation)
- [ ] Jitter `RECCOBEATS_JITTER_DELAY_MS` between batch groups **within** each fetch chain; launch audio-features + metadata chains in parallel via `Promise.allSettled`
- [ ] Delete dead code: `calculateDistribution`, `getAnalysisJobStatus` (no callers)
- [ ] Structured logger in `analysis.ts` (`src/backend/utils/logger.ts`, `service: 'analysis'`)
- [ ] Tests: key/mode aggregation cases; update mocks with `key: 0`, `mode: 1`

### Phase 2: Track Metadata + Caching + Schema Version

- [ ] `fetchReccoBeatsTrackMetadata` for `GET /v1/track?ids=...` (batch 50, concurrency 3, shared retry)
  - **Popularity:** collect all `popularity` values order-independently (min/max only; no index zip, no batch skip on length mismatch)
- [ ] `isReccoBeatsTrackMetadataResponse` type guard: `content` is array; each item has `id`, `trackTitle` strings; `artists` array with `{ id, name, href }` strings; `durationMs` number; `isrc` string; `popularity` number
- [ ] `generatePlaylistInsights` (make **private**): 4th param `reccoBeatsMetadata[]`
  - `isrc_available`: count where `typeof f.isrc === 'string' && f.isrc.length > 0`
  - `popularity_min`/`popularity_max` from metadata
  - `retrieved_at`: `new Date().toISOString()` at analysis time
- [ ] `analyzePlaylist`: parallel `Promise.allSettled` for both ReccoBeats chains; remove legacy single-chain try/catch and old 75%/90% progress emissions; collect `errors[]` (empty on full success); `schema_version: ANALYSIS_SCHEMA_VERSION`
- [ ] `emittedWarmKeepalive` instance flag on `AnalysisService` (70% fires at most once per run)
- [ ] Thread optional `onProgress` into batch fetchers; emit 70% after first successful batch group
- [ ] `compareVersions` in `src/backend/utils/version.ts` — `"major.minor"` positive integers, no `v` prefix, no pre-release (document in file comment)
- [ ] GET results stale check: if `schema_version` missing or `< ANALYSIS_SCHEMA_VERSION`, delete results + status keys, return `404` `ANALYSIS_RESULTS_NOT_FOUND`
- [ ] `ANALYSIS_RESULTS_TTL_SECONDS` in `analysis-job.ts` (replace hardcoded 86400)
- [ ] **Frontend stale-results recovery** in `reccobeats_backend.py`:
  - In `_poll_analysis_completion`, when status is `completed` and `get_analysis_results` raises `BackendAPIError` with `error_code == 'ANALYSIS_RESULTS_NOT_FOUND'`, clear local analysis cache and re-POST once (do not confuse with transient network errors)
  - Test this path
- [ ] **Raw enrichment cache** (key `analysis:playlist:${playlistId}:raw-enrichment` — **no `userId`**; playlist-derived, shareable; comment at key construction):
  - Read: on hit with matching `schema_version`, use cached arrays; **re-fetch any chain whose cached array is empty**
  - Write: cache partial success — store populated arrays and `[]` for failed chains; include `cached_at`
- [ ] Progress: 20 → 50 → 65 → 70 (once, first batch group) → 85 → 95
- [ ] Tests: metadata parsing; audio-features OK + metadata 503; partial `errors[]`; parallel success/fail combos; stale cache 404 deletes keys

### Phase 3: Frontend Analysis Popup

Mockup first: `dev-docs/investigations/2026-07-07-reccobeats-ui-mockup.md` (a11y labels/order; **no axe-core** — Kivy has no DOM).

- [ ] Structured audio features layout (all 9 + key/mode); loudness as `{value} dB`
- [ ] Valence → mood bands (0.20→Somber, 0.40→Neutral, etc.; upper bound exclusive except 0.80–1.00 inclusive)
- [ ] `reccobeats_metadata` aggregates (ISRC count, popularity range)
- [ ] Partial-failure banner from `errors[]`
- [ ] Defensive `schema_version` checks (omit new sections if absent; forward-compat if higher)
- [ ] Tests: all features; `N/A` for missing; no crash without `audio_features`; **Phase 1-shaped result** (no `schema_version`, new fields absent) renders without crash; valence boundary cases

### Phase 4: OpenAPI Reconciliation

Split schemas: shared `ApiEnvelope`, `AnalysisStartResponse` (POST) vs `AnalysisResultsResponse` (GET). Remove aspirational `recommendations` / `include_recommendations`. Comment in POST handler that body is ignored. Update `api-examples.md`.

- [ ] `openapi-schema.test.ts`: mock ReccoBeats per contract; drive `AnalysisJobService.process`
  - Assert example key-paths exist on live response (example ⊆ response)
  - Resolve `$ref` and validate `AnalysisResult` required fields against live response (schema-level check)
- [ ] `analysis-pipeline.test.ts`: end-to-end KV population

### Phase 5: Recommendations — Deferred

Keep on `TO_DO.md`. `GET /v1/track/recommendation` needs separate UI/caching design.

---

## Deployment

1. Backend Phase 1 → Phase 2 → Frontend Phase 3
2. Frontend must tolerate results without `schema_version` between Phase 1 and Phase 2 deploys
3. Consider `ANALYSIS_RESULTS_TTL_SECONDS=3600` for 24h post-deploy, then revert
4. Rollback is safe (additive optional fields)

### Error handling (ReccoBeats batches)

| Scenario | Behavior |
|----------|----------|
| 429 / 5xx | Retry (up to 3), then throw |
| 4xx non-429 | Fail batch immediately |
| Timeout | Retry with `AbortSignal`, then throw |
| Malformed body | Type guard throws |
| Exhausted retries | `Promise.allSettled` → partial result + `errors[]` |

### Decisions

- ReccoBeats best-effort; analysis always completes
- `errors` always present (`[]` on success)
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

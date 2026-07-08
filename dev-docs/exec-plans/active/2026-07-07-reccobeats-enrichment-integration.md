# ReccoBeats Enrichment Integration — Full Playlist Analysis

**Status:** Needs review

**Date:** 2026-07-07
**Source:** [Backlog TO_DO.md#reccobeats-enrichment-gaps](../../backlog/TO_DO.md#reccobeats-enrichment-gaps)

## Goal

Fully integrate ReccoBeats enrichment for playlist analysis by displaying all retrieved audio features, adding missing endpoints, and reconciling the OpenAPI specification with actual backend implementation.

## Revision History

This plan was updated on 2026-07-07 after two independent assessments identified gaps and better alternatives. Key changes from the second assessment (E1–E6, B1–B5, G1–G5): moved constants/helpers to `src/backend/utils/`; split `AnalysisResponse` into `AnalysisStartResponse` (POST) and `AnalysisResultsResponse` (GET); replaced per-track metadata array with aggregates; mapped metadata by position instead of `href` parsing; started `schema_version` at `1.0`; scoped the shared retry util to `AnalysisService`; re-framed loudness as a new formatting decision; added the `70%` progress callback threading step; and dropped `response.clone()` as unnecessary. A third assessment (`tmp/2026-07-07T190000Z-reccobeats-enrichment-plan-assessment.md`) added further fixes. A fourth assessment (`tmp/2026-07-07T200000Z-reccobeats-enrichment-plan-assessment.md`) applied final clarifications: resolved type-guard vs aggregation-logic ambiguity (G5), specified skipped-batch semantics for track metadata (G1), added the audio-features-success+track-metadata-fail test scenario (G2), documented Phase 1→Phase 2 deployment ordering for schema_version (G3), made dead-code deletion unconditional (G4), replaced fragile line-number references with function-name searches (E1–E2), added a stagger note for parallel fetch chains (B1), and chose the live-response approach for the OpenAPI validation test (B3). A fifth assessment (`tmp/2026-07-08T120000Z-reccobeats-enrichment-integration-plan-assessment.md`) corrected the API contract path, clarified that `time_signature` is Spotify-only (not ReccoBeats), added explicit raw-enrichment cache steps, fixed `js-yaml` dependency placement, made `errors` always present on success, added a stale-cache test step, and noted `isrc` optional handling in the type guard.

## Background

Spotify's February 2026 API migration removed the `/audio-features` endpoint family, forcing a migration to ReccoBeats for audio feature data. The current implementation:

- Fetches all 9 audio features via `GET /v1/audio-features` in batches (50 IDs, 3 concurrent)
- Aggregates them into averages but **only displays 5** in the UI
- Ignores `key` and `mode` even though ReccoBeats returns them
- Never calls `GET /v1/track` for ISRC and ReccoBeats popularity
- Has unimplemented `recommendations` fields documented in OpenAPI spec

## Audit Findings (Plan Review)

The plan was reviewed against the live codebase on 2026-07-07. Two independent assessments were incorporated:

- **`MUSIC_KEYS` constant already exists** in `src/backend/services/export-tracks.ts:26` as `keyMap`. Plan now extracts it to shared constants instead of creating a duplicate.
- **OpenAPI `AnalysisResponse` schema is entirely wrong** — top-level fields (`energy_score`, `danceability`, etc.) don't match the actual `AnalysisResult` shape (`overview`, `artists`, `genre_distribution`, `audio_features`, `insights`). Phase 4 now covers a full rewrite.
- **`AnalysisRequest` is entirely aspirational** — the POST route never reads the request body. Both `include_audio_features` and `include_recommendations` are ignored by the backend.
- **ReccoBeats rate limits documented as possible** — API contract says 429 responses with `Retry-After` may occur.
- **`loudness` is in dB**, not a 0-1 scale — UI must format it as `{value} dB`, not as a 0-1 percentage (this is a formatting decision for the new display, not a fix to existing code).
- **Existing test mocks omit `key`/`mode`** — test data will need updating.
- **`isReccoBeatsAudioFeature` type guard** doesn't require `key`/`mode` (they're optional in the `ReccoBeatsAudioFeature` interface — this is correct for the current API contract; aggregation handles null/undefined instead).
- **`calculateDistribution` in `analysis.ts:369-380` is dead code** — never called. Plan now addresses it.
- **No schema versioning for cached analysis results** — KV cache will serve stale-format results after the schema changes. Plan now adds schema version tracking. Note: status key TTL is 1h (`routes/analysis.ts:58`) but **results key TTL is 24h** (`analysis-job.ts:78`), so stale results persist up to 24h.
- **`time_signature` is a Spotify audio feature, not ReccoBeats.** `export-tracks.ts` reads it from `SpotifyAudioFeatures` (legacy `/audio-features` data). ReccoBeats `GET /v1/audio-features` does not return `time_signature` per `dev-docs/reccobeats-api-contract.md`. No ReccoBeats analysis work is needed for this field.

## Reference Documentation

- Investigation: [2026-07-05-reccobeats-enrichment-gaps.md](../investigations/2026-07-05-reccobeats-enrichment-gaps.md) — full audit of current gaps
- API Contract: [reccobeats-api-contract.md](../reccobeats-api-contract.md) — verified endpoint contracts (lives at `dev-docs/reccobeats-api-contract.md`, not under `references/`)
- ReccoBeats Public API Docs: https://reccobeats.com/docs/documentation/introduction
- ReccoBeats Rate Limiting: https://reccobeats.com/docs/documentation/rate-limiting
- ReccoBeats Audio Features: https://reccobeats.com/docs/apis/get-audio-features
- ReccoBeats Track Metadata: https://reccobeats.com/docs/apis/get-tracks
- ReccoBeats Recommendations: https://reccobeats.com/docs/apis/get-tracks (see `/v1/track/recommendation`)

## Implementation Plan

### Phase 0: Shared Constants & Utilities (prerequisite)

The key-to-name mapping already exists in `export-tracks.ts:26` as an inline `keyMap`, with inline usage at `export-tracks.ts:28-31`. Extract to shared files. Also extract the retry utility into `src/backend/utils/` per `ARCHITECTURE.md` (`types/` has no logic, `utils/` is for pure helpers).

- [ ] Create `src/backend/utils/constants.ts` with pure constant data:
  - `MUSIC_KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']` (moved from `export-tracks.ts:26`)
  - `MODE_NAMES: Record<number, string> = { 0: 'minor', 1: 'major' }` (moved from `export-tracks.ts:27`)
  - `ANALYSIS_SCHEMA_VERSION = '1.0'` (not an inline string)
  - `RECCOBEATS_JITTER_DELAY_MS = 50` (proactive rate-limit spacing between batch groups)
  - `ANALYSIS_RESULTS_TTL_SECONDS = 86400` (default results KV TTL; override via Wrangler env for rollout)
  - Add a comment documenting that `MUSIC_KEYS` follows the chromatic scale (index = Pitch Class 0-11) and add a unit test asserting `MUSIC_KEYS.length === 12` and `MUSIC_KEYS[0] === 'C'` to protect the ordering invariant the aggregation relies on.
- [ ] Create `src/backend/utils/music-helpers.ts` with pure helper functions (no internal imports):
  - `keyName(key: number): string` — returns `'N/A'` for out-of-range values
  - `modeName(mode: number): string` — returns `'N/A'` for non-0/1 values
- [ ] Create `src/backend/utils/http-retry.ts` with a generic retry factory function:
  ```typescript
  export interface RetryConfig {
    maxRetries?: number;
    baseDelay?: number;
    shouldRetry?: (status: number) => boolean;
    timeoutMs?: number;
    onRetry?: (attempt: number, status: number, delayMs: number) => void;
  }

  export function createFetchWithRetry(config: RetryConfig): (url: string, options?: RequestInit) => Promise<Response>;
  ```
  - The factory supports 429 status reading `Retry-After` header and backing off.
  - The factory supports 5xx and connection timeouts with exponential backoff.
  - The factory aborts hung requests per `timeoutMs` (defaulting to 15000) using `AbortController`.
- [ ] **Install OpenAPI validation dependencies:** `js-yaml` currently appears only in `package.json` `overrides` (for transitive pinning). Remove it from `overrides`, then add both packages to `devDependencies`:
  ```bash
  npm install --save-dev js-yaml @types/js-yaml
  ```
- [ ] Update `export-tracks.ts` to import from `utils/constants.ts` and `utils/music-helpers.ts`: rename the inline `keyMap` (line 26) → `MUSIC_KEYS` and `modeMap` (line 27) → `MODE_NAMES`, and update all three usage sites (lines 28-31) to call the imported `keyName`/`modeName` helpers instead of the inline logic.
- [ ] Verify existing export tests still pass

### Phase 0.5: Move and Refactor Analysis Types

Extract inline types and interfaces from `src/backend/services/analysis.ts` to a new shared types file `src/backend/types/analysis.ts` to ensure consistency and type reusability.

- [ ] **Create `src/backend/types/analysis.ts` and export the following interfaces:**
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
    overview?: {
      total_tracks: number;
      total_duration_ms: number;
      average_duration_ms: number;
      formatted_duration: string;
    };
    artists?: {
      unique_artists: number;
      top_artists: Array<{ artist: string; count: number }>;
      diversity: number;
    };
    genre_distribution?: Record<string, { count: number; percentage: number }>;
    audio_features?: AudioFeatureSummary;
    insights?: string[];
    reccobeats_metadata?: {
      isrc_available: number;
      popularity_min?: number;
      popularity_max?: number;
      retrieved_at: string;
    };
    errors: Array<{ source: string; message: string }>;
    schema_version: string;
  }

  export interface CachedRawEnrichment {
    audio_features: ReccoBeatsAudioFeature[];
    track_metadata: ReccoBeatsTrackMetadata[];
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
  ```
- [ ] Import these types in `src/backend/services/analysis.ts`, `src/backend/routes/analysis.ts`, and test files. Verify imports are clean.

### Phase 1: Backend Changes — Key/Mode Aggregation + Error Handling

This phase operates on `src/backend/services/analysis.ts` unless otherwise noted.

- [ ] Import shared `MUSIC_KEYS`/`MODE_NAMES`/helpers from `../utils/constants` and `../utils/music-helpers`
- [ ] Add `KeyModeDistribution` interface:
  ```typescript
  interface KeyModeDistribution {
    key_percentages: Record<string, number>;  // "C": 30, "G": 20, ...
    dominant_key: string;
    dominant_key_percentage: number;
    mode_percentages: { major: number; minor: number };
    dominant_mode: 'major' | 'minor';
  }
  ```
- [ ] Extend `AudioFeatureSummary` interface (in `types/analysis.ts`) to include `key_mode_distribution?: KeyModeDistribution`
- [ ] Update `aggregateReccoBeatsAudioFeatures` (line 304) to compute key/mode distributions:
  - Filter tracks to those with valid `key` (0-11) and `mode` (0 or 1) — use `typeof f.key === 'number'` (not truthy check, since `key: 0` is valid and falsy)
  - Handle `null` explicitly: `typeof null !== 'number'` so the same check covers both null and undefined
  - For the existing 9 numeric features, the current `feature[field]` aggregation already works because these are always returned as numbers; no change needed there
  - If fewer than 2 tracks have valid key/mode data, omit `key_mode_distribution` entirely
  - Compute percentage for each of the 12 keys, determine dominant key
  - Compute major/minor percentage split, determine dominant mode
- [ ] **Type guard decision:** `key`/`mode` are optional in `ReccoBeatsAudioFeature` (lines 72-73) so `isReccoBeatsAudioFeature` (line 341) is correct as-is — the type guard does NOT check `key`/`mode` (they're optional, so absence is valid input). `isrc` is also optional; if present it must be `string | null` — the guard may optionally assert `typeof record.isrc === 'string' || record.isrc === null || record.isrc === undefined`, or leave `isrc` to defensive aggregation logic (counting non-empty strings only). The *aggregation logic* (`aggregateReccoBeatsAudioFeatures`) is where the three runtime states are handled for `key`/`mode`: `typeof f.key === 'number'` (valid), `f.key === undefined` (absent), `f.key === null` (explicit null) — similarly for `mode`. The type guard itself needs no change for `key`/`mode`.
- [ ] **Use the shared retry utility (created in Phase 0):** Refactor `fetchReccoBeatsAudioFeaturesBatch` to delegate to `fetchWithRetry` from `../utils/http-retry` (passing a ReccoBeats-specific `shouldRetry` if needed). Do **not** change `SpotifyService.fetchWithRetry` — it keeps its existing behavior to avoid blast radius. Classification is by status code only; the response body is not read before a retry, so **no `response.clone()` is needed** (dropped as unnecessary). Since `fetchWithRetry` throws on non-retryable status or when retries are exhausted, remove the inline `!response.ok` check in the batch fetcher, keep body read + type-guard, and let thrown errors propagate to the `Promise.allSettled` wrapper in `analyzePlaylist`.
- [ ] **Proactive rate limiting (jitter):** Use `RECCOBEATS_JITTER_DELAY_MS` from `utils/constants.ts` between concurrent batch groups inside the ReccoBeats batch fetchers to spread load proactively (in addition to the reactive 429 retry). For the parallel audio-features + track-metadata structure, the two chains are launched together via `Promise.allSettled` and their first batch groups fire simultaneously — consider a single `RECCOBEATS_JITTER_DELAY_MS` delay before launching the second fetch chain to desynchronize the first round (natural timing differences after round 1 keep them apart).
- [ ] **Address dead code:** Delete `calculateDistribution` (analysis.ts:369-380) entirely — it is a private method with zero internal calls and zero external references (verified by grep). Remove it and note the deletion in the PR. (Relocating dead code to a new util only preserves the debt.)
- [ ] Add backend unit tests for key/mode aggregation:
  - Single track with key/mode
  - All 12 keys present (distribution correctness)
  - Null/undefined key or mode on some tracks
  - All tracks missing key/mode (should omit field)
- [ ] Update existing analysis test mock data in `src/backend/tests/analysis.test.ts`:
  - Add `key: 0` and `mode: 1` to all existing mock ReccoBeats responses (both the "averaged features" test and the "chunks into batches" test)
  - Verify expected `audio_features.averages` values don't change
- [ ] **Structured logging:** Replace all `console.log`, `console.warn`, and `console.error` in `analysis.ts` with a structured logger. No shared logger util exists today, so create a minimal one (e.g., `src/backend/utils/logger.ts`) whose envelope matches the existing convention in `index.ts` (`console.error(JSON.stringify({ event, service, environment, ... }))`) — each entry must include `service: 'analysis'`. Note: this narrows the AGENTS.md "no console.log" principle to `analysis.ts`; other backend files (`cache.ts`, `export-*`, `analysis-job.ts`) still use raw `console.*` and are out of scope.
- [ ] Verify all existing tests still pass

### Phase 2: Backend Changes — Track Metadata Endpoint

Adds `GET /v1/track` batch metadata fetching into `src/backend/services/analysis.ts`.

- [ ] Add `ReccoBeatsTrackMetadata` interface matching the API contract response:
  ```typescript
  interface ReccoBeatsTrackMetadata {
    id: string;           // ReccoBeats UUID (internal, not displayed)
    trackTitle: string;
    artists: Array<{ id: string; name: string; href: string }>;
    durationMs: number;
    isrc: string;
    popularity: number;
    // `href` may be present in the response but is NOT used for mapping (see below)
  }
  ```
- [ ] Add `ReccoBeatsTrackMetadataResponse` interface (`{ content: ReccoBeatsTrackMetadata[] }`)
- [ ] Add `isReccoBeatsTrackMetadataResponse` type guard
- [ ] Add `fetchReccoBeatsTrackMetadata` method for `GET /v1/track?ids=...` endpoint
  - Use same batch size (50) and concurrency (3) as audio features
  - Apply the same retry strategy via the shared `fetchWithRetry` utility
  - **Map by position, not by parsing `href`.** ReccoBeats returns `content` in the same order as the requested `ids`, so zip the request Spotify IDs with the response `content` by index. Add a lightweight safety check: assert the returned `content` length matches the requested batch size; if it doesn't, log a structured warning and **skip that batch entirely** — its tracks contribute nothing to popularity aggregates.
- [ ] **Derive `isrc_available` from audio features:** In `generatePlaylistInsights` (in `src/backend/services/analysis.ts`), compute `isrc_available` by counting the number of items in the `reccoBeatsAudioFeatures` array that contain a non-empty `isrc` string. This removes the dependency on the track metadata endpoint for ISRC data, making it robust if the track metadata fetch fails.
- [ ] **Track Metadata only for Popularity:** Use the resolved `reccoBeatsMetadata` purely to calculate `popularity_min` and `popularity_max` across tracks. If the track metadata fetch fails, default these fields to undefined.
- [ ] **Success Errors initialization:** In `analyzePlaylist` (in `src/backend/services/analysis.ts`), if both parallel fetches succeed without error, return `errors: []` in the final `AnalysisResult` for consistent frontend parsing.
- [ ] Add `schema_version: string` field to `AnalysisResult` (value: `ANALYSIS_SCHEMA_VERSION`, which is `'1.0'`) — enables cache invalidation when schema changes in the future. The constant already lives in `utils/constants.ts` (Phase 0). Treat a missing `schema_version` as "legacy / pre-1.0".
- [ ] Set `schema_version: ANALYSIS_SCHEMA_VERSION` in the `analyzePlaylist` return literal in `src/backend/services/analysis.ts`.
- [ ] **Version comparison helper:** Prefer the `compare-versions` npm package (or `semver`) for `compareVersions(v1, v2)` instead of a hand-rolled split-and-compare — handles pre-releases and edge cases. If keeping a local helper, create `src/backend/utils/version.ts` with component-wise numeric comparison and document that pre-release strings are out of scope.
- [ ] **Cache Stale Check in GET Handler:** In `src/backend/routes/analysis.ts` `GET /playlist/:id/results` handler, import `ANALYSIS_SCHEMA_VERSION` and `compareVersions` from `../utils/version`, retrieve the cached `results`, and validate `results.schema_version`. If `schema_version` is missing or below `ANALYSIS_SCHEMA_VERSION` (using `compareVersions`), treat it as a cache miss: delete `resultsKey`, delete the status key `statusKey`, and return a `404` error (`ANALYSIS_RESULTS_NOT_FOUND`) so the client re-triggers analysis.
- [ ] **Lower TTL for deployment:** Import `ANALYSIS_RESULTS_TTL_SECONDS` from `utils/constants.ts` in `src/backend/services/analysis-job.ts` (replacing the hardcoded 86400). Allow override via Wrangler env (e.g. `ANALYSIS_RESULTS_TTL_SECONDS=3600` for the first 24h post-deploy), then revert to 86400.
- [ ] **Verify queue consumer** (`src/backend/services/analysis-job.ts`) calls `AnalysisService.analyzePlaylist` and does not have independent ReccoBeats fetch logic. The queue consumer is the only caller of `analyzePlaylist`, so changes to `analyzePlaylist` are automatically used by queue processing.
- [ ] **Remove legacy progress and error boundaries (Transition Step):** Delete the old try/catch block around audio-features fetch in `analyzePlaylist` (legacy `src/backend/services/analysis.ts`) and remove the `await onProgress?.(75)` and `await onProgress?.(90)` calls to make room for parallel `Promise.allSettled` orchestrations.
- [ ] **Pin progress emissions to instance boolean:** Add an instance field `emittedWarmKeepalive = false` on `AnalysisService` to track whether the 70% progress keep-alive has been emitted for the current run, avoiding state leakage between concurrent jobs.
- [ ] Wire track metadata fetch into `analyzePlaylist`:
  - After collecting all track IDs, initiate both ReccoBeats fetches in parallel using `Promise.allSettled()`:
  ```typescript
  const [audioFeaturesResult, metadataResult] = await Promise.allSettled([
    this.fetchReccoBeatsAudioFeatures(trackIds),
    this.fetchReccoBeatsTrackMetadata(trackIds)
  ]);
  ```
  - Extract values from fulfilled promises, default to `[]` for rejected ones
  - For each rejected promise, push a `{ source: string, message: string }` object into a local `errors` array, and log a structured warning including the endpoint name, error message, and attempt count.
  - Pass the local `errors` array and the fetched metadata/features down to `generatePlaylistInsights`.
  - Spread the collected `errors` array (if non-empty) into the final returned `AnalysisResult` literal.
- [ ] Move the `generatePlaylistInsights` call to **after** the `Promise.allSettled` resolves — locate it by searching for `this.generatePlaylistInsights(`.
- [ ] Update `generatePlaylistInsights` signature to accept `reccoBeatsMetadata: ReccoBeatsTrackMetadata[]` as a 4th parameter; compute the aggregates (`isrc_available` from audio features, `popularity_min/max` from track metadata) inside it and return them in the `reccobeats_metadata` field (already on `PlaylistInsights` from Phase 0.5). Update the call site in `analyzePlaylist` to pass the fulfilled metadata result.
- [ ] Make `generatePlaylistInsights` `private` — it is currently **public** (`async generatePlaylistInsights` with no visibility modifier). Confirm with `rg` that no test or subclass references it directly, then add the `private` keyword.
- [ ] **Thread `onProgress` into the batch fetchers:** Update `fetchReccoBeatsAudioFeatures` and `fetchReccoBeatsTrackMetadata` to accept an optional `onProgress?: (p: number) => Promise<void>` callback, and pass `onProgress` down from `analyzePlaylist` (or a wrapper that emits `70`). Emit `70` once after the first batch-group completes successfully (using `this.emittedWarmKeepalive` to guard so it fires at most once even across retries).
- [ ] Update progress callback positions in `analyzePlaylist` for the parallel fetch structure:
  - 20% → tracks fetched
  - 50% → artists fetched
  - 65% → before parallel ReccoBeats fetches begin
  - 70% → once, after the first batch-group completes successfully (keep-alive signal)
  - 85% → parallel fetches complete
  - 95% → insights generated
- [ ] **Raw enrichment cache — read path:** In `analyzePlaylist`, before initiating ReccoBeats fetches, read KV key `analysis:playlist:${playlistId}:raw-enrichment`. If present and `schema_version` matches `ANALYSIS_SCHEMA_VERSION`, deserialize as `CachedRawEnrichment` and skip both fetch chains.
- [ ] **Raw enrichment cache — write path:** After a successful parallel fetch (or partial success where at least one chain fulfilled), write `{ audio_features, track_metadata, schema_version }` to the same KV key with a 24h TTL.
- [ ] **Raw enrichment cache — helpers:** Add `getCachedRawEnrichment(playlistId)` / `setCachedRawEnrichment(playlistId, data)` on `CacheService` (or thin wrappers on `AnalysisService` that delegate to KV). Reuse `CachedRawEnrichment` from `types/analysis.ts` (Phase 0.5).
- [ ] **Raw enrichment cache — export follow-up:** Document that `export-tracks.ts` does not yet read this cache; a follow-up can share the key to avoid duplicate ReccoBeats calls during export+analysis on the same playlist.

  **Rationale for intermediate progress (70%):** If retries occur, the job status record may look stalled. Emitting `70%` after a successful (possibly retried) batch keeps the status warm. If no retries are needed, this is a no-op.
- [ ] Add backend unit tests:
  - Track metadata endpoint parsing
  - **Audio-features succeeds, track-metadata fails (HTTP 503)** — the most likely partial-failure scenario in production. Assert `status === 'completed'`, `audio_features` is populated (averages intact), and `reccobeats_metadata` is present with `isrc_available === 0`. No crash.
  - Track metadata returns a payload that fails `isReccoBeatsTrackMetadataResponse` (type-guard failure — mock fetch returns HTTP 200 with `{ content: [{ id: 'x' /* missing isrc, popularity */ }] }`). The per-batch fetcher throws, outer `Promise.allSettled` catches it as rejected, analysis completes with `reccobeats_metadata` present and `isrc_available === 0`.
  - **Partial failure errors recording:** Assert that when a fetch fails, an entry is added to `results.errors` containing the source and error message.
  - Parallel fetch with audio-features failing, track metadata succeeding
  - Parallel fetch with both succeeding
  - Parallel fetch with both failing
- [ ] **Stale cache check test:** Store a cached result with `schema_version: '0.9'` (or missing) in KV, call `GET /analysis/playlist/:id/results`, assert `404` (`ANALYSIS_RESULTS_NOT_FOUND`) and that both `resultsKey` and `statusKey` are deleted.

### Phase 3: Frontend Changes — Audio Features Display

Updates `src/frontend/ui/backend_playlist_card.py` to display all features in a structured layout.

**Before starting UI work:** Create a rough layout mockup of the analysis popup showing where the new audio features sections will go. Keep it as a reference in `dev-docs/investigations/2026-07-07-reccobeats-ui-mockup.md` (matches the `YYYY-MM-DD-topic.md` convention used by other investigations). Include accessibility in the mockup: screen-reader labels per section and a sensible tab/reading order; add an `axe-core` check to the Phase 3 frontend tests. The mockup should cover:
- Happy path (all ReccoBeats data available)
- Partial data (some features missing, showing `N/A`)
- ReccoBeats entirely unavailable (audio_features undefined — popup should still show overview/artist/genre sections without crashing)
- Two layout approaches to evaluate:
- **Categorized GridLayout** (2 columns per group, static layout)
- **Expandable sections** (collapsible per category, like the existing Tracks section) — reduces visual clutter by default

- [ ] **Loudness formatting (new):** The current UI does not display loudness. When adding it, format as `{value} dB` (e.g., `-6.0 dB`) rather than as a 0-1 percentage — ReccoBeats `loudness` is in dB (negative values), not a 0-1 scale like the other features. (There is no existing `×100` bug; this is a correct-formatting decision for the new display.)
- [ ] Replace the single-line audio features `Label` (search for "Audio Features" text in the analysis popup) with a structured layout:
  - Use a `GridLayout` (2 columns: label | value) or categorized sections
  - Categorized groups:
    - **Energy & Mood**: Danceability, Energy, Valence (with mood label), Acousticness
    - **Temporal**: Tempo (BPM), Speechiness
    - **Spectral**: Instrumentalness, Liveness
    - **Loudness**: Loudness (dB format)
    - **Key/Mode**: Dominant key + mode (e.g., "C major"), mode distribution
  - Show `'N/A'` for features where the value is `None` (don't skip the row entirely — the label is still useful)
  - Keep the "Based on N tracks with available audio data" footer that follows the current audio features label, reposition if needed
  - Ensure the popup layout handles scroll if the analysis content exceeds popup height
- [ ] Replace the existing valence percentage display with the mood label:
  - 0.00–0.20: "Melancholic"
  - 0.20–0.40: "Somber"
  - 0.40–0.60: "Neutral"
  - 0.60–0.80: "Cheerful"
  - 0.80–1.00: "Euphoric"
  - **Banding rule:** upper bound is *exclusive*, except the final band `0.80 <= valence <= 1.00` is *inclusive*. Example: `valence = 0.4` maps to "Neutral".
  - Show the mood label **instead of** the raw percentage (e.g., "Mood (Valence): Cheerful")
- [ ] Add ISRC and ReccoBeats popularity display (read from `reccobeats_metadata` aggregates):
  - **Requires Phase 2 to be deployed first** (track metadata endpoint must be implemented and working)
  - ISRC: show `isrc_available` count summary only (e.g., "ISRC data available for 45/100 tracks"). Do not display a single example ISRC without clear labeling, as it is easily mistaken for a per-track value. Per-track ISRC in a track detail view is a future feature.
  - Popularity: if `popularity_min`/`popularity_max` are present, show the range (e.g., "Popularity: 45-69"). If only 1 track has data (`min === max`), show a single value ("Popularity: 69"). If absent, omit entirely.
- [ ] **Display partial failure errors:** If the analysis result contains an `errors` array, render a non-intrusive warning/banner in the analysis popup (e.g., "Track metadata unavailable — analysis is still complete").
- [ ] **Frontend defensive check:** When rendering analysis results, check `schema_version` before accessing `audio_features.key_mode_distribution` or `reccobeats_metadata`. If these fields are missing (old cached result), render gracefully (omit the new sections) rather than crashing. If `schema_version` is present but **higher than expected** (e.g., `2.0`), the frontend should still attempt to render known fields (forward compatibility) rather than failing entirely.
- [ ] Add/update frontend tests for analysis popup rendering:
  - **Scope:** test data→display mapping (not pixel-level rendering). Assertions like "popup contains 'Audio Features' section header when `audio_features.averages` are present"
  - **Approach:** use `kivy.clock.Clock` scheduling to render the popup, then inspect widget tree for expected labels. The existing tests in `src/frontend/tests/test_ui.py` can serve as a pattern.
  - **Coverage:** at minimum — valid data renders all 9 features; missing data shows `N/A`; ReccoBeats entirely absent doesn't crash; legacy result (no `schema_version`) renders gracefully without new sections and does not crash; future `schema_version: '2.0'` still renders known fields.
  - Add explicit boundary assertions for the valence→mood bands (e.g., valence 0.20 → 'Somber', 0.40 → 'Neutral', 0.60 → 'Cheerful', 0.80 → 'Euphoric') to lock the exclusive-upper-bound / inclusive-final-band rule.

### Phase 4: OpenAPI Spec Reconciliation

The `AnalysisResponse` schema in `src/backend/docs/openapi.yaml` is entirely disconnected from the actual response shape. **Important:** the POST and GET endpoints return **different** objects, so this phase splits the schema into two:
- `POST /analysis/playlist/{id}` (200) returns `{ data: AnalysisStatusRecord }` (job_id, status, progress, queued_at…) — see `routes/analysis.ts:40-43,69-72`.
- `GET /analysis/playlist/{id}/results` (200) returns `{ data: AnalysisResult }` (the full analysis).

- [ ] **Add shared `ApiEnvelope` schema:** Define a shared `ApiEnvelope` object schema wrapping `data` (object) and `meta` (object containing a required `timestamp` date-time string) in `src/backend/docs/openapi.yaml`. Use this wrapper via `allOf` or nested properties for both response schemas below to resolve existing `meta` envelope drift.
- [ ] **Add `AnalysisStartResponse` schema:** Define it wrapping `AnalysisStatusRecord` in `data` (and including the `meta` envelope). The `AnalysisStatusRecord` schema should explicitly list all fields: `job_id` (string), `playlist_id` (string), `user_id` (string), `status` (string), `progress` (integer), `queued_at` (string, date-time), `started_at` (string, date-time, optional), `completed_at` (string, date-time, optional), `failed_at` (string, date-time, optional), `retry_after` (integer, optional), `attempt` (integer, optional), `error` (string, optional), and `updated_at` (string, date-time, optional). Point the **POST** `200` response at it.
- [ ] **Rewrite `AnalysisResultsResponse`** (the GET /results schema) wrapping `AnalysisResult` in `data` (and including the `meta` envelope):
  - Remove top-level: `average_bpm`, `energy_score`, `danceability`, `valence`, `acousticness`, `instrumentalness`, and the `analysis` wrapper (the actual response is `data: { job_id, playlist_id, overview, … }`, not `data: { analysis: { … } }`)
  - Add nested structure matching the interface (all under `data`):
    - `overview` (total_tracks, total_duration_ms, average_duration_ms, formatted_duration)
    - `artists` (unique_artists, top_artists, diversity)
    - `genre_distribution` (Record<string, { count, percentage }>)
    - `audio_features` (track_count, averages, key_mode_distribution)
    - `insights` (string[])
    - `reccobeats_metadata` (`isrc_available` (required), `popularity_min?`, `popularity_max?`, `retrieved_at` (required)) — **aggregates, not a per-track array**
    - `schema_version` (string)
    - `errors` (array of `{ source: string, message: string }`, required; empty array on full success)
  - Keep existing top-level under `data`: `playlist_id`, `job_id`, `user_id`, `status`, `computed_at`, `completed_at`. Note: `total_tracks` is nested inside `overview`, not a top-level field — do not promote it.
  - Remove entirely: `recommendations.similar_playlists` sub-schema, `SimilarPlaylist` schema
- [ ] Handle `AnalysisRequest` — simplify to an empty schema; remove `include_recommendations` and `include_audio_features`.
- [ ] **Document Route Ignored Body:** Add a comment in `src/backend/routes/analysis.ts` POST handler explaining that the route uses an empty POST and ignores any body input for strict HTTP semantics.
- [ ] Update the analysis example response in `openapi.yaml` (lines 378-413) to match the new schema:
  - **Remove the `analysis` wrapper** — the actual response is `data: { job_id, playlist_id, … }`, not `data: { analysis: { … } }`
  - The example response should use `data` with flat top-level fields matching `AnalysisResult`
- [ ] Update `src/backend/docs/api-examples.md`:
  - Rewrite the "Analyze Playlist (Basic)" response (lines 233-268) to match the actual `AnalysisResult` shape. This includes removing the current `data.analysis` wrapper — the example currently nests results under `data: { analysis: { … } }`, but the real response is `data: { job_id, playlist_id, … }` with no `.analysis` sub-wrapper. (The frontend parses `data` directly, so this structural change must propagate consistently with the OpenAPI example.)
  - Remove the entire "Analyze Playlist (with Recommendations)" section (lines 271-308)
  - **Clarify `include_recommendations` removal (doc-only):** Remove the `include_recommendations` field from the code sample in `src/backend/docs/api-examples.md` (lines 543-563).
  - Remove `include_recommendations: true` from the code sample in "Complete Examples" in `api-examples.md` (line 649).
- [ ] **Add automated OpenAPI validation test:** Create `src/backend/tests/openapi-schema.test.ts`. Since POST/GET is asynchronous via the queue, stand up a test harness that drives `AnalysisJobService.process` directly with a mocked `Env` (auth + KV + queue) to complete the job.
  - **Verification steps:**
    - Load and parse `src/backend/docs/openapi.yaml` using the `js-yaml` library.
    - Extract the response examples for both `POST /analysis/playlist/{id}` and `GET /analysis/playlist/{id}/results`.
    - Perform a recursive assertion checking that every key-path present in the OpenAPI examples exists on the live response returned by Hono endpoints.
    - Globally mock `fetch` to return ReccoBeats mock payloads mapped from `dev-docs/reccobeats-api-contract.md`.
- [ ] **End-to-End Analysis Pipeline Integration Test:** Add a test in `src/backend/tests/analysis-pipeline.test.ts` that mocks a playlist with 5 tracks, enqueues an analysis job, runs `AnalysisJobService.process()`, mocks both ReccoBeats endpoints with contract response structures, and asserts that the resulting KV record is successfully populated with the correct `AnalysisResult` properties.

### Phase 5: ReccoBeats Recommendations — Deferred

**Decision:** Deferred to future work, kept on TO_DO.md backlog.

The `GET /v1/track/recommendation` endpoint offers mood/energy-based track recommendations. This is a separate feature that:
- Would require additional UI design (where should recommendations appear?)
- Needs separate caching strategy for recommendation data
- Adds complexity to the analysis payload

**Action:** Keep tracked in `dev-docs/backlog/TO_DO.md` as a future enhancement possibility. Do not remove the investigation notes about this endpoint from the docs.

**Criteria for revisiting:**
- User feedback explicitly requests recommendations or "similar playlists"
- Analysis UI stabilizes and the popup is no longer being actively iterated on
- ReccoBeats adds playlist-level recommendations (currently only track-level)

## Cross-Cutting Concerns

### Cache Schema Versioning

When the `AnalysisResult` schema changes, existing cached results in KV (`analysis:{playlist_id}:{user_id}:results`) will have the old shape. To handle this:

- Phase 2 adds `schema_version: string` to `AnalysisResult` (value: `"1.0"`)
- The frontend checks `schema_version` defensively (Phase 3) — if the field is missing or doesn't match, the new sections are omitted gracefully. If `schema_version` is present but **higher than expected** (e.g., `2.0`), the frontend still renders known fields (forward compatibility)
- **Deployment sequence:**
  1. Deploy backend Phase 1 changes (adds aggregates to analysis results).
  2. Deploy backend Phase 2 changes (adds `schema_version`, stale-checking, and `errors[]` schema structure).
  3. Deploy frontend Phase 3 changes (adds UI widgets and defensive `schema_version`/`errors[]` parsing).
- Results KV key (`analysis:{playlist_id}:{user_id}:results`) has a **24-hour TTL** (configured in `analysis-job.ts`), so stale-format results persist for up to 24h after deployment
- **Backend-side stale check:** `GET /analysis/playlist/:id/results` should validate `schema_version` on the cached result; if it is missing or below `ANALYSIS_SCHEMA_VERSION` (compare by parsing both versions using component-wise comparison to avoid lexicographical string comparison issues), treat it as a cache miss (delete the key and return 404 so the client re-triggers analysis) rather than serving an old-format payload. This bounds the blast radius of a version bump beyond the TTL window.
- **Deployment checklist:** Consider temporarily lowering the results KV TTL to **1 hour** for the first 24h after deployment to reduce the stale cache window. Revert TTL after the rollout stabilizes.
- **Deployment ordering:** Phase 1 deploys first (adds `key_mode_distribution` without `schema_version`). Phase 2 adds `schema_version` and the backend stale check. Phase 3 frontend must tolerate **both** states: `schema_version` present (`'1.0'`) and absent (legacy). The backend stale check is only active after Phase 2 is deployed — between Phase 1 and Phase 2, old KV results serve the Phase 1 shape without `schema_version` and the frontend gracefully omits new sections.

### Error Handling Matrix

| Scenario | Behavior |
|----------|----------|
| 429 (rate limit) | Retry with `Retry-After`, up to 3 times, then throw |
| 5xx (server error) | Retry with exponential backoff, up to 3 times, then throw |
| 4xx non-429 (incl. 404) | Fail the batch immediately (outer `Promise.allSettled` treats it as rejected; that batch contributes nothing) |
| 4xx non-429 (client error) | Fail immediately, throw |
| Network timeout | Retry with `timeoutMs` (default 15s) per request via `AbortSignal`, up to 3 times, then throw |
| Malformed response | Type guard fails, throw |
| All retries exhausted | Outer catch in `analyzePlaylist` logs warning, continues with partial data |

### Performance Impact

Adding track metadata fetching doubles the number of ReccoBeats API calls (one batch series per fetch point). For a 1000-track playlist:
- Audio features: 20 batches × 3 concurrency ≈ 7 sequential rounds
- Track metadata: same (parallel via `Promise.allSettled`, so wall-clock time is the max of the two, not sum)
- Total ReccoBeats calls per analysis: 2× the batch count

This is acceptable for analysis (run asynchronously via the queue, user polls for results). **Decision: use parallel `Promise.allSettled`** (wall-clock is the max of the two chains, not the sum). If latency/rate-limit pressure becomes an issue later, the fallback is to make the two fetches **sequential** (audio features first, then track metadata), or to make the track-metadata fetch conditional on a cache miss — but those are not adopted now.

### Proactive Rate Limiting

Phase 1 adds a 50ms jitter delay between concurrent batch groups to proactively spread load and reduce the probability of hitting rate limits. This is in addition to the reactive 429 retry strategy. The jitter is small enough (~350ms total delay for a 1000-track playlist) that it doesn't meaningfully impact wall-clock time.

### Partial Results with Error Metadata

Return an `errors` array in every analysis result (required field, empty on full success):
```typescript
errors: Array<{ source: string; message: string }>;
```
On success with no partial failures, return `errors: []` so the frontend can always parse `errors` without checking for `undefined`. On partial failure, populate entries so the frontend can display a non-intrusive banner like "Track metadata unavailable — analysis is still complete."

### Rollback & Safe Deployment

If a deployment proves defective (e.g., frontend crashes on a `schema_version` mismatch, or ReccoBeats mapping corrupts data):
- **Backend:** revert the Worker to the previous deployment (Cloudflare retains prior versions). Because this plan is additive (new *optional* fields, no removed/renamed fields), a downgrade is safe — old code simply ignores fields it doesn't understand.
- **KV data:** no migration is required on rollback. Malformed results, if any, are caught by the backend-side stale check (deletes + 404s on version mismatch) or expire via the 24h TTL. A one-time cleanup Worker/cron to purge `analysis:{playlist_id}:{user_id}:results` is optional, not required.
- **Frontend:** ship the field-consuming frontend only after the backend schema change is live; an old frontend tolerates the new fields via its defensive `schema_version`/`.get()` checks, so a frontend-downgrade is also safe.
- **Ordering:** deploy backend first; avoid two schema-bumping deployments inside the 24h TTL window (keep a short freeze between breaking changes).

### Key Architectural Decisions Kept

- ReccoBeats remains best-effort (never blocks analysis completion)
- `time_signature` is Spotify-only; ReccoBeats analysis does not surface it
- Track metadata stored at summary level, not per-track (avoids bloated payload)

**Revised decision:** A shared `fetchWithRetry` utility replaces the "no shared retry utility" decision. This is cleaner than inline duplication and already justified by the existing `SpotifyService.fetchWithRetry`.

## Quality & Documentation Updates

- [ ] Update `QUALITY_SCORE.md`:
  - Change ReccoBeats integration grade from D to C (real integration exists, but test coverage still growing)
  - Change Analysis grade from C to C+ (improved aggregation logic, more endpoints)
  - Add note about track metadata endpoint integration
- [ ] Update `CHANGELOG.md` with user-facing changes:
  - Added missing audio features (instrumentalness, liveness, loudness, speechiness) to analysis display
  - Added key/mode distribution to analysis display
  - Added ISRC and ReccoBeats popularity display
  - Replaced raw valence percentage with human-readable mood labels
  - Fixed loudness display (dB instead of percentage)
  - Removed aspirational `include_recommendations` parameter from API documentation
- [ ] Update plan to completed status when done
- [ ] Uncheck the backlog item in `dev-docs/backlog/TO_DO.md` when all phases are complete

## References

- Investigation: [2026-07-05-reccobeats-enrichment-gaps.md](../investigations/2026-07-05-reccobeats-enrichment-gaps.md)
- API Contract: [reccobeats-api-contract.md](../reccobeats-api-contract.md) — verified endpoint contracts (lives at `dev-docs/reccobeats-api-contract.md`, not under `references/`)
- Assessment: `tmp/2026-07-07T174500Z-reccobeats-plan-assessment.md`
- Backend Service: `src/backend/services/analysis.ts`
- Backend Constants (extracted): `src/backend/utils/constants.ts` (new file)
- Backend Music Helpers (extracted): `src/backend/utils/music-helpers.ts` (new file)
- Backend HTTP Retry Utility: `src/backend/utils/http-retry.ts` (new file)
- Frontend UI: `src/frontend/ui/backend_playlist_card.py`
- Existing key map source: `src/backend/services/export-tracks.ts` (inline `keyMap`, to be refactored in Phase 0)
- Tests: `src/backend/tests/analysis.test.ts`
- OpenAPI Spec: `src/backend/docs/openapi.yaml`
- API Examples: `src/backend/docs/api-examples.md`
- Quality Scores: `QUALITY_SCORE.md`
- Assessments consulted:
  - `tmp/2026-07-07T073000Z-reccobeats-enrichment-integration-plan-assessment.md`
  - `tmp/2026-07-07T113000Z-reccobeats-enrichment-integration-plan-assessment.md`
  - `tmp/2026-07-07T120000Z-reccobeats-enrichment-integration-plan-assessment.md`
  - `tmp/2026-07-07T120000Z-reccobeats-enrichment-integration-plan-review.md`
  - `tmp/2026-07-07T160844Z-reccobeats-plan-assessment.md`
  - `tmp/2026-07-07T165000Z-reccobeats-enrichment-integration-plan-assessment.md`
  - `tmp/2026-07-07T174500Z-reccobeats-plan-assessment.md`
  - `tmp/2026-07-07T190000Z-reccobeats-enrichment-plan-assessment.md`
  - `tmp/2026-07-07T200000Z-reccobeats-enrichment-integration-plan-assessment.md`
  - `tmp/2026-07-08T014915Z-reccobeats-enrichment-plan-assessment.md`
  - `tmp/2026-07-08T120000Z-reccobeats-enrichment-integration-plan-assessment.md`

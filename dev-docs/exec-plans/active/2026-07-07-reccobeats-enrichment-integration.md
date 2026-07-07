# ReccoBeats Enrichment Integration — Full Playlist Analysis

**Status:** Needs review

**Date:** 2026-07-07
**Source:** [Backlog TO_DO.md#reccobeats-enrichment-gaps](../../backlog/TO_DO.md#reccobeats-enrichment-gaps)

## Goal

Fully integrate ReccoBeats enrichment for playlist analysis by displaying all retrieved audio features, adding missing endpoints, and reconciling the OpenAPI specification with actual backend implementation.

## Revision History

This plan was updated on 2026-07-07 after two independent assessments identified gaps and better alternatives. Key changes from the second assessment (E1–E6, B1–B5, G1–G5): moved constants/helpers to `src/backend/utils/`; split `AnalysisResponse` into `AnalysisStartResponse` (POST) and `AnalysisResultsResponse` (GET); replaced per-track metadata array with aggregates; mapped metadata by position instead of `href` parsing; started `schema_version` at `1.0`; scoped the shared retry util to `AnalysisService`; re-framed loudness as a new formatting decision; added the `70%` progress callback threading step; and dropped `response.clone()` as unnecessary. A third assessment (`tmp/2026-07-07T190000Z-reccobeats-enrichment-plan-assessment.md`) added further fixes. A fourth assessment (`tmp/2026-07-07T200000Z-reccobeats-enrichment-plan-assessment.md`) applied final clarifications: resolved type-guard vs aggregation-logic ambiguity (G5), specified skipped-batch semantics for track metadata (G1), added the audio-features-success+track-metadata-fail test scenario (G2), documented Phase 1→Phase 2 deployment ordering for schema_version (G3), made dead-code deletion unconditional (G4), replaced fragile line-number references with function-name searches (E1–E2), added a stagger note for parallel fetch chains (B1), and chose the live-response approach for the OpenAPI validation test (B3).

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
- **`time_signature`** is returned by ReccoBeats and exported in `export-tracks.ts`, but not aggregated in analysis. Plan adds a decision checkbox.

## Reference Documentation

- Investigation: [2026-07-05-reccobeats-enrichment-gaps.md](../investigations/2026-07-05-reccobeats-enrichment-gaps.md) — full audit of current gaps
- API Contract: [reccobeats-api-contract.md](../references/reccobeats-api-contract.md) — verified endpoint contracts
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
  - Add a comment documenting that `MUSIC_KEYS` follows the chromatic scale (index = Pitch Class 0-11) and add a unit test asserting `MUSIC_KEYS.length === 12` and `MUSIC_KEYS[0] === 'C'` to protect the ordering invariant the aggregation relies on.
- [ ] Create `src/backend/utils/music-helpers.ts` with pure helper functions (no internal imports):
  - `keyName(key: number): string` — returns `'N/A'` for out-of-range values
  - `modeName(mode: number): string` — returns `'N/A'` for non-0/1 values
- [ ] Create `src/backend/utils/http-retry.ts` with a shared `fetchWithRetry` function:
  ```typescript
  export async function fetchWithRetry(
    url: string,
    options?: RequestInit,
    config?: {
      maxRetries?: number;
      baseDelay?: number;
      shouldRetry?: (status: number) => boolean;
      timeoutMs?: number;
      onRetry?: (attempt: number, status: number, delayMs: number) => void;
    }
  ): Promise<Response>;
  ```
  - Supports 429 → read `Retry-After`, wait (cap at 15s), retry up to 3 times
  - Supports 5xx → exponential backoff (1s, 2s, 4s) up to 3 times
  - Supports 4xx (non-429) → fail immediately
  - **Per-request timeout:** pass `AbortSignal.timeout(config.timeoutMs ?? 15000)` so a hung connection fails fast instead of stalling the async queue job. An aborted request is treated as a retryable network error (retried up to `maxRetries`).
  - Response classification uses status code only; reading the body is deferred to the caller
  - **Scope:** Used by `AnalysisService` only. Do not change `SpotifyService.fetchWithRetry` behavior (keep existing behavior to avoid blast radius).
  - **Tech-debt follow-up (file a ticket):** unify `SpotifyService.fetchWithRetry` with this shared util in a later change so only one retry implementation exists; also plan broader adoption of the structured logger beyond `analysis.ts`. For now the duplication is intentional to avoid a behavior change.
- [ ] Update `export-tracks.ts` to import from `utils/constants.ts` and `utils/music-helpers.ts`: rename the inline `keyMap` (line 26) → `MUSIC_KEYS` and `modeMap` (line 27) → `MODE_NAMES`, and update all three usage sites (lines 28-31) to call the imported `keyName`/`modeName` helpers instead of the inline logic.
- [ ] Verify existing export tests still pass

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
- [ ] Extend `AudioFeatureSummary` (line 63-66) to include `key_mode_distribution?: KeyModeDistribution`
- [ ] Update `aggregateReccoBeatsAudioFeatures` (line 304) to compute key/mode distributions:
  - Filter tracks to those with valid `key` (0-11) and `mode` (0 or 1) — use `typeof f.key === 'number'` (not truthy check, since `key: 0` is valid and falsy)
  - Handle `null` explicitly: `typeof null !== 'number'` so the same check covers both null and undefined
  - For the existing 9 numeric features, the current `feature[field]` aggregation already works because these are always returned as numbers; no change needed there
  - If fewer than 2 tracks have valid key/mode data, omit `key_mode_distribution` entirely
  - Compute percentage for each of the 12 keys, determine dominant key
  - Compute major/minor percentage split, determine dominant mode
- [ ] **Type guard decision:** `key`/`mode` are optional in `ReccoBeatsAudioFeature` (lines 72-73) so `isReccoBeatsAudioFeature` (line 341) is correct as-is — the type guard does NOT check `key`/`mode` (they're optional, so absence is valid input). The *aggregation logic* (`aggregateReccoBeatsAudioFeatures`) is where the three runtime states are handled: `typeof f.key === 'number'` (valid), `f.key === undefined` (absent), `f.key === null` (explicit null) — similarly for `mode`. The type guard itself needs no change.
- [ ] **Use the shared retry utility (created in Phase 0):** Refactor `fetchReccoBeatsAudioFeaturesBatch` to delegate to `fetchWithRetry` from `../utils/http-retry` (passing a ReccoBeats-specific `shouldRetry` if needed). Do **not** change `SpotifyService.fetchWithRetry` — it keeps its existing behavior to avoid blast radius. Classification is by status code only; the response body is not read before a retry, so **no `response.clone()` is needed** (dropped as unnecessary).
- [ ] **Proactive rate limiting (jitter):** Add a ~50ms delay between concurrent batch groups inside the ReccoBeats batch fetchers to spread load proactively (in addition to the reactive 429 retry). For the parallel audio-features + track-metadata structure, the two chains are launched together via `Promise.allSettled` and their first batch groups fire simultaneously — consider a single 50ms delay before launching the second fetch chain to desynchronize the first round (natural timing differences after round 1 keep them apart).
- [ ] **Decision: `time_signature` — do not aggregate in analysis.** It's an integer 3-7 with low analytical value per-track. Adding it to averages creates noise. It remains available in per-track export via `export-tracks.ts:50`.
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
  - **Map by position, not by parsing `href`.** ReccoBeats returns `content` in the same order as the requested `ids`, so zip the request Spotify IDs with the response `content` by index. This is deterministic and avoids a fragile `href`→Spotify-ID regex. Drop the `EXTRACT_SPOTIFY_TRACK_ID_REGEX`/`extractSpotifyTrackId` idea entirely (no longer needed). Add a lightweight safety check: assert the returned `content` length matches the requested batch size; if it doesn't, log a structured warning and **skip that batch entirely** — its tracks contribute nothing to ISRC/popularity aggregates (no silent array-length mismatch). The analysis still completes with whatever data the other batches returned.
- [ ] Extend `AnalysisResult` interface (line 4-25) with **aggregates only** (do not store the full per-track array — only the displayed summaries are needed, which also keeps the 24h KV payload small and avoids leaking ReccoBeats internal UUIDs):
  ```typescript
  reccobeats_metadata?: {
    isrc_available: number;        // count of tracks with a non-empty ISRC
    popularity_min?: number;       // min across tracks with data; omit if none
    popularity_max?: number;       // max across tracks with data; omit if none
    retrieved_at: string;
  };
  ```
- [ ] Add `schema_version: string` field to `AnalysisResult` (value: `ANALYSIS_SCHEMA_VERSION`, which is `'1.0'`) — enables cache invalidation when schema changes in the future. The constant already lives in `utils/constants.ts` (Phase 0). Treat a missing `schema_version` as "legacy / pre-1.0".
- [ ] **Verify queue consumer** (`src/backend/services/analysis-job.ts`) calls `AnalysisService.analyzePlaylist` and does not have independent ReccoBeats fetch logic. The queue consumer is the only caller of `analyzePlaylist`, so changes to `analyzePlaylist` are automatically used by queue processing.
- [ ] Wire track metadata fetch into `analyzePlaylist` (line 88-176):
  - After collecting all track IDs (after line 115), initiate both ReccoBeats fetches in parallel using `Promise.allSettled()`:
  ```typescript
  const [audioFeaturesResult, metadataResult] = await Promise.allSettled([
    this.fetchReccoBeatsAudioFeatures(trackIds),
    this.fetchReccoBeatsTrackMetadata(trackIds)
  ]);
  ```
  - Extract values from fulfilled promises, default to `[]` for rejected ones
  - For each rejected promise, log a structured warning including the endpoint name, error message, and attempt count: `service: 'analysis', source: 'ReccoBeats', endpoint: 'audio-features' | 'track-metadata', error: string`
  - Pass `reccoBeatsMetadata` to `generatePlaylistInsights`
- [ ] Move the `generatePlaylistInsights` call (currently ~line 157 in `analyzePlaylist`) to **after** the `Promise.allSettled` resolves — search for `this.generatePlaylistInsights(` to locate it regardless of line-number drift from prior phases
- [ ] Add `reccobeats_metadata` field to `PlaylistInsights` interface (line 34-49) using the **aggregate** shape defined above (`isrc_available`, `popularity_min?`, `popularity_max?`, `retrieved_at`) — this is the internal return type of `generatePlaylistInsights`, and its values are spread into `AnalysisResult` at `analyzePlaylist:163-171`; without this field the metadata never reaches the response
- [ ] Update `generatePlaylistInsights` signature (currently ~line 240 in `analysis.ts`) to accept `reccoBeatsMetadata: ReccoBeatsTrackMetadata[]` as a 4th parameter; compute the aggregates (`isrc_available`, `popularity_min/max`) inside it and return them in the `reccobeats_metadata` field. Update the call site in `analyzePlaylist` to pass the fulfilled metadata result
- [ ] Make `generatePlaylistInsights` `private` — it's only called from `analyzePlaylist` and no external code depends on it. Confirm with `rg` that no test or subclass references it directly (current `analysis.test.ts` calls the public `analyzePlaylist` only) before changing visibility.
- [ ] **Thread `onProgress` into the batch fetchers (required for the 70% warm-keep emit):** Update `fetchReccoBeatsAudioFeatures` and `fetchReccoBeatsTrackMetadata` to accept an optional `onProgress?: (p: number) => Promise<void>` callback, and pass `onProgress` down from `analyzePlaylist` (or a wrapper that emits `70`). Emit `70` once after the first batch-group completes successfully (guarded so it fires at most once even across retries). Without this step the 70% emit below cannot happen.
- [ ] Update progress callback positions in `analyzePlaylist` for the parallel fetch structure:
  - 20% → tracks fetched
  - 50% → artists fetched
  - 65% → before parallel ReccoBeats fetches begin
  - 70% → once, after the first batch-group completes successfully (keep-alive signal; guarded so it fires at most once, even across retries)
  - 85% → parallel fetches complete
  - 95% → insights generated

  **Rationale for intermediate progress (70%):** If retries occur, the job status record may look stalled. Emitting `70%` after a successful (possibly retried) batch keeps the status warm. If no retries are needed, this is a no-op.
- [ ] Add backend unit tests:
  - Track metadata endpoint parsing
  - **Audio-features succeeds, track-metadata fails (HTTP 503)** — the most likely partial-failure scenario in production. Assert `status === 'completed'`, `audio_features` is populated (averages intact), and `reccobeats_metadata` is absent. No crash.
  - Track metadata returns a payload that fails `isReccoBeatsTrackMetadataResponse` (type-guard failure — mock fetch returns HTTP 200 with `{ content: [{ id: 'x' /* missing isrc, popularity */ }] }`). The per-batch fetcher throws, outer `Promise.allSettled` catches it as rejected, analysis completes with `reccobeats_metadata` absent.
  - Parallel fetch with audio-features failing, track metadata succeeding
  - Parallel fetch with both succeeding
  - Parallel fetch with both failing

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
- [ ] **Frontend defensive check:** When rendering analysis results, check `schema_version` before accessing `audio_features.key_mode_distribution` or `reccobeats_metadata`. If these fields are missing (old cached result), render gracefully (omit the new sections) rather than crashing. If `schema_version` is present but **higher than expected** (e.g., `2.0`), the frontend should still attempt to render known fields (forward compatibility) rather than failing entirely.
- [ ] Add/update frontend tests for analysis popup rendering:
  - **Scope:** test data→display mapping (not pixel-level rendering). Assertions like "popup contains 'Audio Features' section header when `audio_features.averages` are present"
  - **Approach:** use `kivy.clock.Clock` scheduling to render the popup, then inspect widget tree for expected labels. The existing tests in `src/frontend/tests/test_ui.py` can serve as a pattern.
  - **Coverage:** at minimum — valid data renders all 9 features; missing data shows `N/A`; ReccoBeats entirely absent doesn't crash
  - Add explicit boundary assertions for the valence→mood bands (e.g., valence 0.20 → 'Somber', 0.40 → 'Neutral', 0.60 → 'Cheerful', 0.80 → 'Euphoric') to lock the exclusive-upper-bound / inclusive-final-band rule.

### Phase 4: OpenAPI Spec Reconciliation

The `AnalysisResponse` schema in `src/backend/docs/openapi.yaml` is entirely disconnected from the actual response shape. **Important:** the POST and GET endpoints return **different** objects, so this phase splits the schema into two:
- `POST /analysis/playlist/{id}` (200) returns `{ data: AnalysisStatusRecord }` (job_id, status, progress, queued_at…) — see `routes/analysis.ts:40-43,69-72`.
- `GET /analysis/playlist/{id}/results` (200) returns `{ data: AnalysisResult }` (the full analysis).

- [ ] **Add `AnalysisStartResponse`** schema = `{ data: AnalysisStatusRecord }` (reuse the existing `AnalysisStatusRecord` fields) and point the **POST** `200` response at it.
- [ ] **Rewrite `AnalysisResultsResponse`** (the GET /results schema) to match `AnalysisResult` wrapped in `data`:
  - Remove top-level: `average_bpm`, `energy_score`, `danceability`, `valence`, `acousticness`, `instrumentalness`, and the `analysis` wrapper (the actual response is `data: { job_id, playlist_id, overview, … }`, not `data: { analysis: { … } }`)
  - Add nested structure matching the interface (all under `data`):
    - `overview` (total_tracks, total_duration_ms, average_duration_ms, formatted_duration)
    - `artists` (unique_artists, top_artists, diversity)
    - `genre_distribution` (Record<string, { count, percentage }>)
    - `audio_features` (track_count, averages, key_mode_distribution)
    - `insights` (string[])
    - `reccobeats_metadata` (`isrc_available`, `popularity_min?`, `popularity_max?`, `retrieved_at`) — **aggregates, not a per-track array**
    - `schema_version` (string)
  - Keep existing top-level under `data`: `playlist_id`, `job_id`, `user_id`, `status`, `computed_at`, `completed_at`. Note: `total_tracks` is nested inside `overview`, not a top-level field — do not promote it.
  - Remove entirely: `recommendations.similar_playlists` sub-schema, `SimilarPlaylist` schema
- [ ] Handle `AnalysisRequest` — route doesn't read the request body, so:
  - Simplify `AnalysisRequest` to an empty schema with a description: "Request body is optional and currently ignored. The endpoint uses empty POST for HTTP semantics only."
  - Remove `include_recommendations` and `include_audio_features` properties
  - Remove the example `requestBody` content that shows the old `include_audio_features` and `include_recommendations` fields (they are misleading now)
- [ ] Update the analysis example response in `openapi.yaml` (lines 378-413) to match the new schema:
  - **Remove the `analysis` wrapper** — the actual response is `data: { job_id, playlist_id, … }`, not `data: { analysis: { … } }`
  - The example response should use `data` with flat top-level fields matching `AnalysisResult`
- [ ] Update `src/backend/docs/api-examples.md`:
  - Rewrite the "Analyze Playlist (Basic)" response (lines 233-268) to match the actual `AnalysisResult` shape. This includes removing the current `data.analysis` wrapper — the example currently nests results under `data: { analysis: { … } }`, but the real response is `data: { job_id, playlist_id, … }` with no `.analysis` sub-wrapper. (The frontend parses `data` directly, so this structural change must propagate consistently with the OpenAPI example.)
  - Remove the entire "Analyze Playlist (with Recommendations)" section (lines 271-308)
  - Update `SpotiByeAPI.analyzePlaylist` to not send `include_recommendations` (lines 543-563)
  - Remove `include_recommendations: true` from "Complete Examples" (line 649)
- [ ] **Add automated OpenAPI validation test:** Create `src/backend/tests/openapi-schema.test.ts` that POSTs to the test app (`/analysis/playlist/:id`), polls for completion, fetches `GET /results`, and asserts the live POST and GET response shapes are structurally supersets of the spec's examples. This catches real-world drift between spec and implementation, validates both the POST/GET split and the `data` envelope, and is more reliable than static type-inference approaches. (Optional follow-up: add zod-based type inference as a second validation layer for compile-time drift detection.)

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
- **Version bump policy:** increment `ANALYSIS_SCHEMA_VERSION` only for *breaking* changes to the cached `AnalysisResult` shape (a required, renamed, or removed field). Additive optional fields do not require a bump — the frontend already tolerates missing optional fields, and the stale check only triggers on a lower/invalid version.
- Results KV key (`analysis:{playlist_id}:{user_id}:results`) has a **24-hour TTL** (`analysis-job.ts:78`), so stale-format results persist for up to 24h after deployment
- **Backend-side stale check:** `GET /analysis/playlist/{id}/results` should validate `schema_version` on the cached result; if it is missing or below `ANALYSIS_SCHEMA_VERSION`, treat it as a cache miss (delete the key and return 404 so the client re-triggers analysis) rather than serving an old-format payload. This bounds the blast radius of a version bump beyond the TTL window.
- **Deployment checklist:** Consider temporarily lowering the results KV TTL to **1 hour** for the first 24h after deployment to reduce the stale cache window. Revert TTL after the rollout stabilizes.
- **Deployment ordering:** Phase 1 deploys first (adds `key_mode_distribution` without `schema_version`). Phase 2 adds `schema_version` and the backend stale check. Phase 3 frontend must tolerate **both** states: `schema_version` present (`'1.0'`) and absent (legacy). The backend stale check is only active after Phase 2 is deployed — between Phase 1 and Phase 2, old KV results serve the Phase 1 shape without `schema_version` and the frontend gracefully omits new sections.

### Error Handling Matrix

| Scenario | Behavior |
|----------|----------|
| 429 (rate limit) | Retry with `Retry-After`, up to 3 times, then throw |
| 5xx (server error) | Retry with exponential backoff, up to 3 times, then throw |
| 404 (not found) | Log warning, skip that track, continue batch |
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

Instead of silently dropping failed fetches, consider returning an errors array in the analysis result (minor enhancement, not a blocker):
```typescript
errors?: Array<{ source: string; message: string }>;
```
This would let the frontend display a non-intrusive banner like "Track metadata unavailable — analysis is still complete."

### Rollback & Safe Deployment

If a deployment proves defective (e.g., frontend crashes on a `schema_version` mismatch, or ReccoBeats mapping corrupts data):
- **Backend:** revert the Worker to the previous deployment (Cloudflare retains prior versions). Because this plan is additive (new *optional* fields, no removed/renamed fields), a downgrade is safe — old code simply ignores fields it doesn't understand.
- **KV data:** no migration is required on rollback. Malformed results, if any, are caught by the backend-side stale check (deletes + 404s on version mismatch) or expire via the 24h TTL. A one-time cleanup Worker/cron to purge `analysis:{playlist_id}:{user_id}:results` is optional, not required.
- **Frontend:** ship the field-consuming frontend only after the backend schema change is live; an old frontend tolerates the new fields via its defensive `schema_version`/`.get()` checks, so a frontend-downgrade is also safe.
- **Ordering:** deploy backend first; avoid two schema-bumping deployments inside the 24h TTL window (keep a short freeze between breaking changes).

### Key Architectural Decisions Kept

- ReccoBeats remains best-effort (never blocks analysis completion)
- `time_signature` not aggregated in analysis (explicit decision in Phase 1)
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
- API Contract: [reccobeats-api-contract.md](../references/reccobeats-api-contract.md) — verified endpoint contracts
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
  - `tmp/2026-07-07T200000Z-reccobeats-enrichment-plan-assessment.md`

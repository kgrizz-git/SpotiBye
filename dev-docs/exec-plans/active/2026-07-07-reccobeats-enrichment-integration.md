# ReccoBeats Enrichment Integration — Full Playlist Analysis

**Status:** Needs review

**Date:** 2026-07-07
**Source:** [Backlog TO_DO.md#reccobeats-enrichment-gaps](../../backlog/TO_DO.md#reccobeats-enrichment-gaps)

## Goal

Fully integrate ReccoBeats enrichment for playlist analysis by displaying all retrieved audio features, adding missing endpoints, and reconciling the OpenAPI specification with actual backend implementation.

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
- **`loudness` is in dB**, not a 0-1 scale — UI must format it differently from other features (this is a bug fix).
- **Existing test mocks omit `key`/`mode`** — test data will need updating.
- **`isReccoBeatsAudioFeature` type guard** doesn't require `key`/`mode` (they're optional in the `ReccoBeatsAudioFeature` interface — this is correct for the current API contract; aggregation handles null/undefined instead).
- **`calculateDistribution` in `analysis.ts:369-380` is dead code** — never called. Plan now addresses it.
- **No schema versioning for cached analysis results** — KV cache will serve stale-format results after the schema changes. Plan now adds schema version tracking. Note: status key TTL is 1h (`routes/analysis.ts:58`) but **results key TTL is 24h** (`analysis-job.ts:78`), so stale results persist up to 24h.
- **`time_signature`** is returned by ReccoBeats and exported in `export-tracks.ts`, but not aggregated in analysis. Plan adds a decision checkbox.

## Reference Documentation

- Investigation: [2026-07-05-reccobeats-enrichment-gaps.md](../investigations/2026-07-05-reccobeats-enrichment-gaps.md) — full audit of current gaps
- API Contract: [reccobeats-api-contract.md](../reccobeats-api-contract.md) — verified endpoint contracts
- ReccoBeats Public API Docs: https://reccobeats.com/docs/documentation/introduction
- ReccoBeats Rate Limiting: https://reccobeats.com/docs/documentation/rate-limiting
- ReccoBeats Audio Features: https://reccobeats.com/docs/apis/get-audio-features
- ReccoBeats Track Metadata: https://reccobeats.com/docs/apis/get-tracks
- ReccoBeats Recommendations: https://reccobeats.com/docs/apis/get-tracks (see `/v1/track/recommendation`)

## Implementation Plan

### Phase 0: Shared Constants Refactor (prerequisite)

The key-to-name mapping already exists in `export-tracks.ts:26` as an inline `keyMap`, with inline usage at `export-tracks.ts:28-31`. Extract to a shared constants file so both export and analysis can use it.

- [ ] Create `src/backend/types/constants.ts` with (keeps logic helpers in the `types/` layer per ARCHITECTURE.md):
  - `MUSIC_KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']` (moved from `export-tracks.ts:26`)
  - `MODE_NAMES: Record<number, string> = { 0: 'minor', 1: 'major' }` (moved from `export-tracks.ts:27`)
  - `keyName(key: number): string` helper — returns `'N/A'` for out-of-range values (replaces inline logic at `export-tracks.ts:28-30`)
  - `modeName(mode: number): string` helper — returns `'N/A'` for non-0/1 values (replaces inline logic at `export-tracks.ts:31`)
- [ ] Update `export-tracks.ts` to import from `constants.ts` instead of using inline arrays and inline helpers
- [ ] Verify existing export tests still pass

### Phase 1: Backend Changes — Key/Mode Aggregation + Error Handling

This phase operates on `src/backend/services/analysis.ts` unless otherwise noted.

- [ ] Import shared `MUSIC_KEYS`/`MODE_NAMES`/helpers from `../types/constants`
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
- [ ] **Type guard decision:** `key`/`mode` are optional in `ReccoBeatsAudioFeature` (lines 72-73) so `isReccoBeatsAudioFeature` (line 341) is correct as-is — the type guard should NOT require them. Document this intentionally in a comment above the optional fields. The aggregation logic below handles null/undefined.
- [ ] Add retry handling to `fetchReccoBeatsAudioFeaturesBatch` (line 207):
  - On 429: read `Retry-After` header, wait that many seconds (cap at 15s — Cloudflare Workers have a 30s CPU time limit and the retry loop must leave room for the actual request), retry up to 3 times
  - On 5xx: retry with exponential backoff (1s, 2s, 4s) up to 3 times
  - On 4xx (non-429): fail immediately
  - If all retries exhausted: throw (outer catch in `analyzePlaylist` handles best-effort)
  - Do not create a shared retry utility — keep it inline (revisit if a third external API is added)
  - Add a small jitter delay (50ms) between each concurrent batch group to spread load and reduce probability of hitting rate limits proactively
- [ ] **Decision: `time_signature` — do not aggregate in analysis.** It's an integer 3-7 with low analytical value per-track. Adding it to averages creates noise. It remains available in per-track export via `export-tracks.ts:50`.
- [ ] **Address dead code:** Remove `calculateDistribution` method (line 369-380) entirely — it's never called. Its low/medium/high bucketing algorithm (for 0-1 scale features) doesn't overlap with key/mode percentage logic (count-based per 12 buckets), so there's nothing to reuse.
- [ ] Add backend unit tests for key/mode aggregation:
  - Single track with key/mode
  - All 12 keys present (distribution correctness)
  - Null/undefined key or mode on some tracks
  - All tracks missing key/mode (should omit field)
- [ ] Update existing analysis test mock data in `src/backend/tests/analysis.test.ts`:
  - Add `key: 0` and `mode: 1` to all existing mock ReccoBeats responses (both the "averaged features" test and the "chunks into batches" test)
  - Verify expected `audio_features.averages` values don't change
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
    href: string;         // Spotify track URL
    popularity: number;
  }
  ```
- [ ] Add `ReccoBeatsTrackMetadataResponse` interface (`{ content: ReccoBeatsTrackMetadata[] }`)
- [ ] Add `isReccoBeatsTrackMetadataResponse` type guard
- [ ] Add `fetchReccoBeatsTrackMetadata` method for `GET /v1/track?ids=...` endpoint
  - Use same batch size (50) and concurrency (3) as audio features
  - Apply the same retry strategy (429 + 5xx retries, 4xx fail)
- [ ] **ID mapping:** ReccoBeats returns internal UUIDs (not Spotify IDs). Map metadata back to original Spotify track IDs using the `href` field. Add a helper:
  ```typescript
  function extractSpotifyTrackId(href: string): string | null {
    const match = href.match(/\/track\/([a-zA-Z0-9]+)/);
    return match?.[1] ?? null;
  }
  ```
  Skip tracks where extraction fails (log a warning). Place this helper in `types/constants.ts`.
- [ ] Extend `AnalysisResult` interface (line 4-25) with:
  ```typescript
  reccobeats_metadata?: {
    track_metadata: ReccoBeatsTrackMetadata[];
    retrieved_at: string;
  };
  ```
- [ ] Add `schema_version: string` field to `AnalysisResult` (value: `"1.1"` initially) — enables cache invalidation when schema changes in the future. Define `ANALYSIS_SCHEMA_VERSION = '1.1'` as a constant in `types/constants.ts` (not an inline string). Version scheme: `major.minor` — increment minor for additive changes (new fields), major for breaking restructures. Current version `"1.1"` reflects additive changes to audio_features (key/mode) and new reccobeats_metadata structure.
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
  - Log individual warnings for each failure using `console.warn` with consistent format: `[ReccoBeats] {endpoint} fetch failed; continuing with partial data`
  - Pass `reccoBeatsMetadata` to `generatePlaylistInsights`
- [ ] Update `generatePlaylistInsights` call at `analysis.ts:157` to move it to **after** the `Promise.allSettled` resolves (so track metadata is available when insights are generated)
- [ ] Add `reccobeats_metadata` field to `PlaylistInsights` interface (line 34-49) — this is the internal return type of `generatePlaylistInsights`, and its values are spread into `AnalysisResult` at `analyzePlaylist:163-171`; without this field the metadata never reaches the response
- [ ] Update `generatePlaylistInsights` signature at `analysis.ts:240` to accept `reccoBeatsMetadata` as a 4th parameter; update the call at `analysis.ts:157` to pass it
- [ ] Make `generatePlaylistInsights` `private` — it's only called from `analyzePlaylist` and no external code depends on it
- [ ] Update progress callback positions in `analyzePlaylist` for the parallel fetch structure:
  - 20% → tracks fetched
  - 50% → artists fetched
  - 65% → before parallel ReccoBeats fetches begin
  - 85% → parallel fetches complete
  - 95% → insights generated
- [ ] Add backend unit tests:
  - Track metadata endpoint parsing
  - Parallel fetch with one ReccoBeats call failing, the other succeeding
  - Parallel fetch with both succeeding
  - Parallel fetch with both failing

### Phase 3: Frontend Changes — Audio Features Display

Updates `src/frontend/ui/backend_playlist_card.py` to display all features in a structured layout.

**Before starting UI work:** Create a rough layout mockup of the analysis popup showing where the new audio features sections will go. Keep it as a reference in `dev-docs/investigations/reccobeats-ui-mockup.md`. The mockup should cover:
- Happy path (all ReccoBeats data available)
- Partial data (some features missing, showing `N/A`)
- ReccoBeats entirely unavailable (audio_features undefined — popup should still show overview/artist/genre sections without crashing)
- Two layout approaches to evaluate:
- **Categorized GridLayout** (2 columns per group, static layout)
- **Expandable sections** (collapsible per category, like the existing Tracks section) — reduces visual clutter by default

- [ ] **Bug fix:** Stop multiplying `loudness` by 100 — display as `{value} dB` (e.g., `-6.0 dB`). It's not a 0-1 scale like the other features.
- [ ] Replace the single-line `Label` at lines 653-667 with a structured layout:
  - Use a `GridLayout` (2 columns: label | value) or categorized sections
  - Categorized groups:
    - **Energy & Mood**: Danceability, Energy, Valence (with mood label), Acousticness
    - **Temporal**: Tempo (BPM), Speechiness
    - **Spectral**: Instrumentalness, Liveness
    - **Loudness**: Loudness (dB format)
    - **Key/Mode**: Dominant key + mode (e.g., "C major"), mode distribution
  - Show `'N/A'` for features where the value is `None` (don't skip the row entirely — the label is still useful)
  - Keep the "Based on N tracks with available audio data" footer (line 668-675), reposition if needed
  - Ensure the popup layout handles scroll if the analysis content exceeds popup height
- [ ] Replace the existing valence percentage display with the mood label:
  - 0.00–0.20: "Melancholic"
  - 0.20–0.40: "Somber"
  - 0.40–0.60: "Neutral"
  - 0.60–0.80: "Cheerful"
  - 0.80–1.00: "Euphoric"
  - Show the mood label **instead of** the raw percentage (e.g., "Mood (Valence): Cheerful")
- [ ] Add ISRC and ReccoBeats popularity display (if available from `reccobeats_metadata`):
  - **Requires Phase 2 to be deployed first** (track metadata endpoint must be implemented and working)
  - ISRC: show as sampled data — display the first track's ISRC as an example, with a count of how many tracks have ISRC data (e.g., "ISRC: USUG12103683 (45 tracks have ISRC data)"). Per-track ISRC in a track detail view is a future feature.
  - Popularity: show min-max range across all tracks with available data (e.g., "Popularity: 45-69"). If only 1 track has data, show single value ("Popularity: 69"). If no data available, omit entirely.
- [ ] **Frontend defensive check:** When rendering analysis results, check `schema_version` before accessing `audio_features.key_mode_distribution` or `reccobeats_metadata`. If these fields are missing (old cached result), render gracefully (omit the new sections) rather than crashing.
- [ ] Add/update frontend tests for analysis popup rendering:
  - **Scope:** test data→display mapping (not pixel-level rendering). Assertions like "popup contains 'Audio Features' section header when `audio_features.averages` are present"
  - **Approach:** use `kivy.clock.Clock` scheduling to render the popup, then inspect widget tree for expected labels. The existing tests in `src/frontend/tests/test_ui.py` can serve as a pattern.
  - **Coverage:** at minimum — valid data renders all 9 features; missing data shows `N/A`; ReccoBeats entirely absent doesn't crash

### Phase 4: OpenAPI Spec Reconciliation

The `AnalysisResponse` schema in `src/backend/docs/openapi.yaml` is entirely disconnected from the actual `AnalysisResult` response shape. This phase rewrites it to match reality.

- [ ] Rewrite `AnalysisResponse` schema to match the actual `AnalysisResult` interface:
  - Remove top-level: `average_bpm`, `energy_score`, `danceability`, `valence`, `acousticness`, `instrumentalness`
  - Add nested structure matching the interface:
    - `overview` (total_tracks, total_duration_ms, average_duration_ms, formatted_duration)
    - `artists` (unique_artists, top_artists, diversity)
    - `genre_distribution` (Record<string, { count, percentage }>)
    - `audio_features` (track_count, audio_feature_averages, key_mode_distribution)
    - `insights` (string[])
    - `reccobeats_metadata` (track_metadata[], retrieved_at)
    - `schema_version` (string)
  - Keep existing top-level: `playlist_id`, `total_tracks`
  - Remove entirely: `recommendations.similar_playlists` sub-schema, `SimilarPlaylist` schema
- [ ] Handle `AnalysisRequest` — route doesn't read the request body, so:
  - Simplify `AnalysisRequest` to an empty schema with a description: "Request body is optional and currently ignored. The endpoint uses empty POST for HTTP semantics only."
  - Remove `include_recommendations` and `include_audio_features` properties
- [ ] Update the analysis example response in `openapi.yaml` (lines 378-413) to match the new schema:
  - **Remove the `analysis` wrapper** — the actual response is `data: { job_id, playlist_id, ... }`, not `data: { analysis: { ... } }`
  - The example response should use `data` with flat top-level fields matching `AnalysisResult`
- [ ] Update `src/backend/docs/api-examples.md`:
  - Rewrite the "Analyze Playlist (Basic)" response (lines 233-268) to match the actual `AnalysisResult` shape
  - Remove the entire "Analyze Playlist (with Recommendations)" section (lines 271-308)
  - Update `SpotiByeAPI.analyzePlaylist` to not send `include_recommendations` (lines 543-563)
  - Remove `include_recommendations: true` from "Complete Examples" (line 649)

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

- Phase 2 adds `schema_version: string` to `AnalysisResult` (value: `"1.1"`)
- The frontend checks `schema_version` defensively (Phase 3) — if the field is missing or doesn't match, the new sections are omitted gracefully
- Results KV key (`analysis:{playlist_id}:{user_id}:results`) has a **24-hour TTL** (`analysis-job.ts:78`), so stale-format results persist for up to 24h after deployment. The `schema_version` field enables graceful handling regardless.

### Error Handling Matrix

| Scenario | Behavior |
|----------|----------|
| 429 (rate limit) | Retry with `Retry-After`, up to 3 times, then throw |
| 5xx (server error) | Retry with exponential backoff, up to 3 times, then throw |
| 404 (not found) | Log warning, skip that track, continue batch |
| 4xx non-429 (client error) | Fail immediately, throw |
| Network timeout | Retry with 5s timeout per request, up to 3 times, then throw |
| Malformed response | Type guard fails, throw |
| All retries exhausted | Outer catch in `analyzePlaylist` logs warning, continues with partial data |

### Performance Impact

Adding track metadata fetching doubles the number of ReccoBeats API calls (one batch series per fetch point). For a 1000-track playlist:
- Audio features: 20 batches × 3 concurrency ≈ 7 sequential rounds
- Track metadata: same (parallel via `Promise.allSettled`, so wall-clock time is the max of the two, not sum)
- Total ReccoBeats calls per analysis: 2× the batch count

This is acceptable for analysis (run asynchronously via the queue, user polls for results). If latency becomes an issue, consider:
- Reducing concurrency to avoid rate limit contention between the two parallel fetch chains
- Making track metadata fetch conditional (e.g., only when cache miss on `reccobeats_metadata`)

### Proactive Rate Limiting

Phase 1 adds a 50ms jitter delay between concurrent batch groups to proactively spread load and reduce the probability of hitting rate limits. This is in addition to the reactive 429 retry strategy. The jitter is small enough (~350ms total delay for a 1000-track playlist) that it doesn't meaningfully impact wall-clock time.

### Partial Results with Error Metadata

Instead of silently dropping failed fetches, consider returning an errors array in the analysis result:
```typescript
errors?: Array<{ source: string; message: string }>;
```
This would let the frontend display a non-intrusive banner like "Track metadata unavailable — analysis is still complete." This is an enhancement, not a blocker.

### Key Architectural Decisions Kept

- ReccoBeats remains best-effort (never blocks analysis completion)
- No shared retry utility (keep inline unless a third external API is added)
- `time_signature` not aggregated in analysis (explicit decision in Phase 1)
- Track metadata stored at summary level, not per-track (avoids bloated payload)

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
- API Contract: [reccobeats-api-contract.md](../reccobeats-api-contract.md)
- Backend Service: `src/backend/services/analysis.ts`
- Backend Constants (extracted): `src/backend/types/constants.ts` (new file)
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

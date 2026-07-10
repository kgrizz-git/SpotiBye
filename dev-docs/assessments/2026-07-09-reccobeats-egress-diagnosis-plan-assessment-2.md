# Assessment v2: ReccoBeats Egress Diagnosis & Frontend-Fetch Fallback Plan

**Date:** 2026-07-09
**Prior assessment:** [`2026-07-09-reccobeats-egress-diagnosis-plan-assessment.md`](./2026-07-09-reccobeats-egress-diagnosis-plan-assessment.md)

This is a second-look assessment focusing on errors (incorrect line references, naming mismatches), gaps not covered by the prior assessment, and implementation detail gaps discovered by verifying codebase references.

---

## Errors Found

### 1. Wrong line numbers for `_describe_error_source` (Plan Phase 1, step 1)

**Plan says:** `backend_playlist_card_utils.py:14-15`

**Actual:** Lines 14-15 are the `_ERROR_SOURCE_LABELS` dict entries (`reccobeats:audio-features` and `reccobeats:track-metadata`). `_describe_error_source()` is at **line 31**. The plan should reference both:
- `_ERROR_SOURCE_LABELS` dict: lines 12-16 (existing label map)
- `_describe_error_source()` function: line 31 (needs optional `message` parameter)
- Call site in popup: `backend_playlist_card_analysis_popup.py:383` (currently passes only `source`, not `message`)

### 2. `analysis.ts:301` is shape validation, not an error-logging boundary (Plan Phase 5, step 1)

**Plan says:** "Add boundary logging (`analysis.ts:301`)"

**Actual:** Line 301 is `if (!this.isReccoBeatsAudioFeaturesResponse(rawData))` — shape validation, *after* the JSON parse. The plan correctly describes the intent (log response text before JSON parse) but pins it to the wrong line. The actual insertion point should be **around line 300**, after `response.json()` and before the shape-validation guard on line 301.

### 3. `spotify.ts:150-157` references call site, not definition (Plan Phase 3, Retry-After)

**Plan says:** "mirror `spotify.ts:150-157`"

**Actual:** Lines 150-157 are the `Retry-After` call site inside `fetchWithRetry`. The function definition is at **lines 224-247**. Both references are useful, but quoting the call site alone doesn't help someone implementing the frontend utility — they need the parsing logic from lines 224-247.

### 4. Function name mismatch: `parse_retry_after` vs `parseRetryAfter` (Plan Phase 3, last bullet)

**Plan says:** `parse_retry_after()` utility in `src/frontend/utils/network_utils.py`

**Actual:** The backend function is named `parseRetryAfter` (camelCase, `spotify.ts:224`). The Python frontend will use snake_case (`parse_retry_after`), which is correct for Python conventions, but the plan should explicitly note the naming divergence and not claim it "mirrors" the backend exactly.

---

## Gaps (not covered by prior assessment)

### 1. No `src/shared/` strategy for enrichment schema

The plan proposes a `PUT /enrichment` endpoint validated against `CachedRawEnrichment` (defined in `src/backend/types/analysis.ts:95`). The frontend must send data matching this shape. Currently there's no shared schema between frontend and backend. Options:
- Duplicate the schema definition in Python frontend (drift risk)
- Move `CachedRawEnrichment` (or a wire subset) to `src/shared/` so both sides import from a common source
- Define the Zod schema in the backend and export it as OpenAPI/doc for the frontend to consume

**Recommendation:** At minimum, document the wire shape in `reccobeats-api-contract.md` and add a validation step in the frontend before sending.

### 2. `AnalysisResult` type update not mentioned (Plan Phase 4, step 1)

Adding `needs_enrichment: boolean` and `missing_track_ids: string[]` to `GET /analysis/playlist/<id>/results` requires updating `AnalysisResult` in `src/backend/types/analysis.ts:64-79`. The plan's backend checklist doesn't include this. The TypeScript compiler will catch it, but it should be an explicit step.

### 3. PUT endpoint auth verification not specified (Plan Phase 4, step 2)

The `PUT /analysis/playlist/<id>/enrichment` endpoint writes to a playlist-scoped KV key. No step verifies the caller owns playlist `<id>`. The backend's existing auth middleware (likely `requireAuth`) should apply, but verifying playlist ownership requires an additional check (fetch the playlist's owner from Spotify or from the stored analysis metadata). Without this, one user could pollute another user's enrichment cache.

**Recommendation:** Add auth verification step: verify `userId` from auth token matches the playlist owner (or the KV key is already scoped to `userId:playlistId`, which `analysis:playlist:<id>:raw-enrichment` is not).

### 4. Phase 2 can run in parallel with Phase 1

Phase 2 (Coverage Quantification) only requires a laptop with network access — not any code changes. It can run concurrently with Phase 1 (error message display changes). The plan doesn't note this parallelism opportunity, which could save 2-3 hours in the timeline.

### 5. No dry-run / verify-before-caching mode (Plan Phase 4)

The frontend fetch has no "test reachability without writing" mode. If a user's first fetch attempt fails (network timeout, ReccoBeats block page), it would still pollute both caches with error data. A dry-run fetch that validates ReccoBeats is reachable and returns valid JSON before committing to dual-write would be safer.

**Recommendation:** Add a `dry_run: bool = False` parameter to `fetch_reccobeats_enrichment_direct()` or a separate `ping_reccobeats()` method.

### 6. Session-tracking infrastructure undefined (Plan Phase 4, privacy notice)

The plan calls for a "per-session confirmation dialog on first fetch." The frontend has no session-state infrastructure. This needs to be defined:
- Where is "session" tracked? (member variable on a screen class? global module-level flag?)
- When does a "session" reset? (app restart? playlist switch?)
- Is the opt-in Setting persisted or per-session?

**Recommendation:** Add a `_reccobeats_privacy_accepted_session: bool = False` member to the analysis screen or the `ReccoBeatsBackendService` class.

### 7. `RECCOBEATS_JITTER_DELAY_MS` not accessible to frontend (Plan Phase 3, abuse controls)

The plan says "mirror Worker's ... `RECCOBEATS_JITTER_DELAY_MS`" but this constant lives in `src/backend/utils/constants.ts:11` (value: 50ms). The Python frontend has no access to it. Either:
- Duplicate the constant in the frontend's config
- Move it to `src/shared/` (if a shared constants layer exists)
- Document that the frontend should define its own equivalent

### 8. Partial KV write failure handling not defined (Plan Phase 4, dual-cache write)

The dual-cache write (KV + local disk) can partially fail. If KV write succeeds but disk write fails (permissions, disk full), the user loses the local backup silently. If disk write succeeds but KV write fails (auth, network), the user has local data but backend cache stays stale. Neither scenario is handled.

**Recommendation:** Define behavior for each partial-failure case. At minimum, log a warning when one half fails and show a "Results saved locally only" or "Backend cache update failed" message.

### 9. Frontend-to-backend schema version coordination (Plan Phase 4, step 2)

The `PUT /enrichment` endpoint validates `schema_version`. The frontend must know what version to send. Is it:
- Hardcoded in the frontend Python code? (drift risk if backend updates schema)
- Fetched from a backend endpoint? (adds a round-trip)
- Passed in the `GET /analysis/playlist/<id>/results` response alongside `needs_enrichment`?

**Recommendation:** Include `expected_enrichment_schema_version` in the `GET /results` response alongside `needs_enrichment`, so the frontend always sends the version the backend expects.

### 10. No `missing_track_ids` computation logic defined (Plan Phase 3/4)

The plan says `needs_enrichment` should trigger when "cached raw-enrichment exists but has fewer entries than `track_ids.length`" and should include `missing_track_ids: string[]`. But the computation logic isn't defined:
- Which stored field is compared? `audio_features.length`? `track_metadata.length`? Both?
- What if `audio_features` has 40 of 50 tracks but `track_metadata` has 45 of 50? Are `missing_track_ids` the union, intersection, or per-category?

**Recommendation:** Define `missing_track_ids` as the symmetric set difference between `track_ids` and the union of track IDs present in either `audio_features` or `track_metadata` from the cached envelope. Document this in the design doc (Phase 3).

### 11. Integration test: how to simulate Worker egress failure (Plan Phase 4, testing)

The plan lists an integration test: "Simulate Worker egress failure → frontend fetches → both caches populated." Without Worker egress actually failing, this requires test infrastructure decisions:
- Use `wrangler dev --remote` with a test Worker whose `fetchReccoBeatsAudioFeatures` throws?
- Or mock the backend responses at the HTTP level?

**Recommendation:** Add a test-only `?simulate_egress_failure=true` query param to the analysis endpoint or write a backend-side test (`vitest`) that verifies the `needs_enrichment` signal is set when enrichment throws.

### 12. Existing `errors` field already carries messages — UI just doesn't display them

The `AnalysisResult.errors[]` already has `{ source, message }` (confirmed at `types/analysis.ts:77`). The popup at `backend_playlist_card_analysis_popup.py:383` only displays `_describe_error_source(source)`, which maps to a static string from `_ERROR_SOURCE_LABELS`. The plan's Phase 1 correctly identifies this gap. However, the popup line 383 currently does:

```python
f"Partial data: {_describe_error_source(source)}"
```

After the change, it should display something like:

```python
f"Partial data: {_describe_error_source(source, message)}"
```

The plan should explicitly note **both** files to change:
- `backend_playlist_card_utils.py:31` — `_describe_error_source` signature
- `backend_playlist_card_analysis_popup.py:383` — call site

---

## Suggestions for Improvement

1. **Add a pre-implementation checklist to Phase 3 (design)** that verifies all type/interface updates are identified before Phase 4 coding begins. This catches the `AnalysisResult` type update and schema coordination issues early.

2. **Add a "feature flag integration" step to Phase 4** explaining exactly how `ENABLE_CLIENT_RECCOBEATS` env var (or new `FeatureFlags` entry in `backend_config.py:102`) flows from config → `ReccoBeatsBackendService` → UI toggle visibility.

3. **Add a rollback checklist as a Phase 4 sub-item**: "If frontend fetch causes issues, disable via `SPOTIBYE_ENABLE_CLIENT_RECCOBEATS=false` env var" — this makes the kill switch actionable.

4. **Consider adding `expected_enrichment_schema_version` to the `GET /results` response** so the frontend always sends the correct version to `PUT /enrichment`, eliminating schema drift.

5. **Clarify the Phase 2 batch-testing script language/environment.** The plan says "Test all track IDs against api.reccobeats.com from laptop IP" but doesn't specify whether to use curl, a Python script, or the existing frontend codebase. Recommend using a standalone Python script (`scripts/test_reccobeats_coverage.py`) that reuses the same batching/concurrency constants as the Worker.

6. **The `parseRetryAfter` logic in `spotify.ts:224-247` handles both integer seconds and HTTP-date formats.** The frontend utility should handle both cases too, and the plan should explicitly call this out (not just "mirror").

7. **The `CachedRawEnrichment` type includes `cached_at` (ISO string) and `track_count`.** The `PUT /enrichment` plan says payload includes `fetched_at` and `schema_version` but doesn't mention `track_count`. The payload shape should be made consistent with the actual type.

---

## Summary of New Findings

| # | Category | Severity |
|---|----------|----------|
| E1 | Wrong line numbers for `_describe_error_source` | Low (cosmetic) |
| E2 | `analysis.ts:301` line misattribution | Low (intent is correct) |
| E3 | `spotify.ts` reference is call site, not definition | Low |
| E4 | `parse_retry_after` vs `parseRetryAfter` naming | Low |
| G1 | No shared schema strategy for enrichment wire format | Medium |
| G2 | `AnalysisResult` type update not listed | Medium (compiler will catch) |
| G3 | PUT endpoint missing playlist-ownership auth check | High (security) |
| G4 | Phase 1/2 can parallelize (not noted) | Low (optimization) |
| G5 | No dry-run mode before dual-write | Medium |
| G6 | Session-tracking undefined for privacy dialog | Medium |
| G7 | `RECCOBEATS_JITTER_DELAY_MS` not accessible to frontend | Low |
| G8 | Partial KV/disk write failure undefined | Medium |
| G9 | Schema version coordination frontend→backend undefined | Medium |
| G10 | `missing_track_ids` computation logic underspecified | Medium |
| G11 | Integration test simulation strategy undefined | Low |
| G12 | Popup call site update not explicitly listed | Low |

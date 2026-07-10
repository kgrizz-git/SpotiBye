# ReccoBeats Egress Diagnosis & Frontend-Fetch Fallback

**Created:** 2026-07-09  
**Status:** Completed — current fix shipped locally; frontend-direct fetch deferred as optional follow-up  
**Follow-up backlog:** [`dev-docs/backlog/TO_DO.md`](../../backlog/TO_DO.md) (optional user-choice client-side ReccoBeats fetch)  
**Investigation:** [`../investigations/2026-07-09-reccobeats-enrichment-failure.md`](../../investigations/2026-07-09-reccobeats-enrichment-failure.md)  
**Related:** [`../reccobeats-api-contract.md`](../../reccobeats-api-contract.md), [`2026-07-05-reccobeats-enrichment-gaps.md`](../../investigations/2026-07-05-reccobeats-enrichment-gaps.md)

---

## Problem Statement

A user running playlist analysis on the **development** backend saw no audio-feature data at all, with popup banners:
- `Partial data: audio features unavailable`
- `Partial data: track metadata unavailable`

The integration code is correct and deployed (`release_sha = 863ac88`). Live testing from a non-datacenter IP shows ReccoBeats returns data for _some_ tracks (no API key needed), but catalog coverage looks partial. The banners indicate the **Worker-side fetch is rejecting** (not returning empty `200`). The initial hypothesis was Cloudflare datacenter egress failure; Phase 2 instead identified the concrete failure as oversized 50-ID ReccoBeats batches.

If egress later proves blocked for some users, the deferred optional fallback is a **frontend-side fetch**: the Python desktop app fetches ReccoBeats data from the user's machine (bypassing Cloudflare egress and CORS), then dual-writes to the backend KV cache and local disk cache.

---

## Goals

1. **Diagnose the Worker egress failure** definitively (IPv6 vs. IP ban vs. other)
2. **Quantify ReccoBeats catalog coverage** with a real sample from actual playlists
3. **Implement frontend-side fetch fallback** if egress is blocked
4. **Improve debuggability** so future failures are immediately diagnosable

---

## Phases

### Phase 1: Immediate Diagnosis (Highest ROI)

**Goal:** Surface hidden error messages to turn guessing into immediate diagnosis.

- [x] **Add error message display to popup**
  - [x] Update `_describe_error_source()` in `src/frontend/ui/backend_playlist_card_utils.py:31` to accept optional `message` parameter
  - [x] Update call site in `src/frontend/ui/backend_playlist_card_analysis_popup.py:383` to pass `errors[].message` from results
  - [x] Test with simulated errors (429, timeout, invalid shape)
- [x] **Run IPv6 egress check**
  - [x] `dig AAAA api.reccobeats.com` — check for dead/misconfigured AAAA record
  - [x] `curl -6 https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B` from dual-stack machine (simulates Worker egress)
  - [x] One-liner Worker fetch (`wrangler dev --remote`) to test egress from Cloudflare
- [x] **Document findings** in the investigation file

**Exit criteria:** Error messages visible in UI; IPv6 reachability confirmed or ruled out.

**Estimated effort:** 1-2 hours

**Note:** Phase 2 (Coverage Quantification) can run in parallel — it requires only a laptop with network access, no code changes.

---

### Phase 2: Coverage Quantification

**Goal:** Measure actual ReccoBeats catalog coverage with a clean experiment that matches Worker batch behavior.

- [x] **Create standalone test script** (`scripts/test_reccobeats_coverage.py`)
  - [x] Reuse Worker's batching/concurrency constants (`BATCH_SIZE=50`, `CONCURRENCY=3`)
  - [x] Handle both integer seconds and HTTP-date `Retry-After` formats (mirror `spotify.ts:224-247`)
- [x] **Pull actual track IDs** from the failing playlist (`03YbVT4UhOxLrOAcpyCEqT`) via `GET /playlists/<id>/tracks`
- [x] **Test all track IDs** against `api.reccobeats.com` from laptop IP
  - [x] Batch in **50s** (Worker's real batch size, `analysis.ts:24`) — do NOT test one-at-a-time
  - [x] Log explicit states per batch: `throw` (egress failure) vs `200 []` (uncovered) vs `200 [data]` (covered)
  - [x] **Document batch behavior:** Does ReccoBeats return partial `content` for mixed-known/unknown tracks, or fail the entire batch?
- [x] **Report coverage %**: "X of Y tracks (Z%) returned data"
- [ ] **Optional deferred:** Test 2-3 additional playlists across eras/genres for broader sample

**Phase 2 finding (2026-07-10):** Current Worker batch size 50 is invalid for ReccoBeats. ReccoBeats returns HTTP 400 with `size must be between 1 and 40` for 50-ID `/audio-features` and `/track` batches. Re-running the same 106-track failing playlist with batch size 40 returned data for 64/106 tracks (60.38%) on both endpoints, with no throw batches. Coverage is partial but usable once batch size is corrected. Implementation should use `BATCH_SIZE=30`, not 40, to stay comfortably below the current upstream cap with minimal extra request overhead.

**Exit criteria:** Coverage percentage documented; batch behavior understood; decision on whether coverage is "partial but usable" or "too sparse to rely on."

**Estimated effort:** 2-3 hours (can run in parallel with Phase 1)

---

### Phase 3: Frontend-Fetch Design (Deferred Optional Follow-Up)

**Goal:** Preserve the frontend-fetch + dual-cache workaround notes as future design material.

**Status:** Deferred. Phase 1/2 showed Cloudflare Worker egress can reach ReccoBeats and identified the immediate production bug as oversized 50-ID ReccoBeats batches. Do not implement this phase as part of the current fix unless backend-side enrichment still fails after the `BATCH_SIZE=30` deployment and cache-retry behavior. Track future exploration as a user-choice enhancement in [`dev-docs/backlog/TO_DO.md`](../../backlog/TO_DO.md): "Explore optional user-choice client-side ReccoBeats fetch."

- [ ] **Create detailed design doc** covering:
  - [ ] API shape: `GET /analysis/playlist/<id>/results` gains:
    - `needs_enrichment: boolean`
    - `missing_track_ids: string[]` (request `track_ids` minus Spotify IDs extracted from cached enrichment `href` fields)
    - `schema_version: string` remains the single schema-version source; frontend writes this value back in the enrichment payload
  - [ ] Type updates checklist:
    - [ ] `AnalysisResult` in `src/backend/types/analysis.ts:64-79` includes `needs_enrichment` and `missing_track_ids`
    - [ ] `ReccoBeatsTrackMetadata` in `src/backend/types/analysis.ts` includes the observed track-level `href?: string` field from the ReccoBeats contract
    - [ ] `CachedRawEnrichment` remains `{ audio_features, track_metadata, schema_version: string, cached_at, track_count }`; do not add `fetched_at` or a separate `expected_enrichment_schema_version` unless the raw-enrichment schema intentionally diverges from `ANALYSIS_SCHEMA_VERSION`
    - [ ] Frontend result parsing and UI tests account for `needs_enrichment` and `missing_track_ids`
  - [ ] Track-ID source strategy:
    - [ ] Store the Spotify track IDs used for enrichment in a companion KV key written by the analysis job, or in `AnalysisResult` as an internal field that is omitted from the public API response unless intentionally exposed
    - [ ] Do not make `GET /results` refetch playlist tracks just to compute `missing_track_ids`; the route currently has only cached analysis data and should remain cheap
  - [ ] Frontend fetch method in `ReccoBeatsBackendService` (`src/frontend/services/reccobeats_backend.py`)
    - Include `dry_run: bool = False` parameter to test reachability without writing
    - Dry-run response shape: `{ "reachable": bool, "tested_track_ids": string[], "status_code": int | None, "error": str | None }`
    - Handle both integer seconds and HTTP-date `Retry-After` formats with an explicit retry loop; `@retry_on_network_error` does not retry `RateLimitError` by default
  - [ ] Backend endpoint: `PUT /analysis/playlist/<id>/enrichment`
    - **Auth verification:** Verify caller owns playlist `<id>` (fetch playlist owner from Spotify or stored analysis metadata)
    - Accept raw JSON envelope matching `CachedRawEnrichment` type: `{ audio_features, track_metadata, schema_version, cached_at, track_count }`
    - Write to `analysis:playlist:<id>:raw-enrichment` KV key, resetting TTL to 24h from write time
    - Validate payload `schema_version` matches current `ANALYSIS_SCHEMA_VERSION`
    - Return `204 No Content` on success
  - [ ] Dual-write strategy:
    - Local disk cache via `get_cache_manager().get_cache_path()` (not hardcoded path)
    - Disk-write failure handling: local cache writes must return a clear success/failure result or raise a named exception; no silent fallback
    - **Partial failure handling:** If KV write fails but disk succeeds → "Results saved locally only" warning; if disk fails but KV succeeds → "Backend cache updated" warning; if both fail → error banner with retry option
    - Add "Backend cache updated" UI indicator after successful write
  - [ ] Race/dedup handling (last-write-wins is acceptable)
  - [ ] Partial data merging strategy:
    - Extract Spotify track ID with a shared backend utility, e.g. `spotifyTrackIdFromHref(href: string): string | null`
    - Use track-level `href` from both `audio_features` and `track_metadata`; add `href?: string` to the metadata type because the verified contract includes it
    - Merge by Spotify track ID; client-fetched entries fill gaps, and newer client entries may replace older cached entries for the same ID within the same write
  - [ ] **TTL semantics:** Frontend writes reset TTL to 24h from fetch time (fresh fetch = fresh 24h window)
  - [ ] **`needs_enrichment` lifecycle:** After a successful `PUT /enrichment`, the next analysis/result read should see a valid raw-enrichment cache and return `needs_enrichment: false` unless the cached envelope is stale, invalid, or still missing requested tracks.
  - [ ] Privacy gating:
    - Add `_reccobeats_privacy_accepted_session: bool` member to analysis screen or service
    - Define "session" scope as process lifetime: a Python instance attribute resets on app restart, not playlist switch, and is not persisted to disk
    - Opt-in toggle + per-session "Fetch from this device" button
  - [ ] Feature flag integration:
    - Add `FeatureFlags.ENABLE_CLIENT_RECCOBEATS` to `src/frontend/config/backend_config.py`
    - Document kill switch: `SPOTIBYE_ENABLE_CLIENT_RECCOBEATS=false` env var
    - Add rollback checklist to Phase 4
  - [ ] Constants coordination:
    - Add `RECCOBEATS_JITTER_DELAY_MS = 50` or equivalent to `PerformanceSettings` in `src/frontend/config/backend_config.py`
  - [ ] Schema strategy:
    - Document wire shape in `reccobeats-api-contract.md`
    - Document that `schema_version` is a string and is reused for both analysis results and raw-enrichment payload validation until a separate raw-enrichment schema is needed
- [ ] **Review design** with user before implementation

**Exit criteria if revived:** Design doc complete and approved; all type/interface updates identified; auth verification strategy defined.

**Estimated effort:** 3-4 hours

---

### Phase 4: Frontend-Fetch Implementation (Deferred Optional Follow-Up)

**Goal:** Implement the frontend-fetch fallback end-to-end only if revived from the backlog.

**Status:** Deferred. The current implementation path should stop after backend batch-size correction, stale ReccoBeats-error cache retry, verification on the dev backend, and final investigation cleanup. If this phase is revived later, make it an explicit user-choice option, not automatic fallback behavior.

#### Backend Changes

- [ ] **Add `needs_enrichment` signal** to `GET /analysis/playlist/<id>/results`
  - [x] Change ReccoBeats `BATCH_SIZE` in `src/backend/services/analysis.ts` from 50 to 30 before deeper fallback work; Phase 2 showed ReccoBeats rejects 50-ID batches with HTTP 400 (`size must be between 1 and 40`), and 30 leaves headroom below the current upstream cap
  - [x] Add frontend/backend-cache retry path for existing schema-current results that contain `reccobeats:*` errors: clear local analysis cache, call `DELETE /analysis/playlist/<id>`, and enqueue a fresh analysis once
  - [ ] Update `AnalysisResult` type in `src/backend/types/analysis.ts:64-79` to include:
    - `needs_enrichment: boolean`
    - `missing_track_ids: string[]`
  - [ ] Add a backend utility to extract Spotify IDs from ReccoBeats `href` values (`https://open.spotify.com/track/<id>`); do not compare ReccoBeats UUID `id` values to Spotify track IDs
  - [ ] Update `ReccoBeatsTrackMetadata` to include `href?: string` so metadata entries can participate in missing-ID computation
  - [ ] Persist the original Spotify track IDs used during analysis (prefer a companion KV key; otherwise use an internal `AnalysisResult` field omitted from the public response unless intentionally exposed) so `GET /results` can compute missing IDs without refetching playlist tracks
  - [ ] Compute `missing_track_ids` as `track_ids` minus the union of Spotify IDs extracted from cached `audio_features[].href` and `track_metadata[].href`
  - [ ] Set `needs_enrichment` when (a) `errors[]` for `reccobeats:*` is non-empty, OR (b) cached raw-enrichment is absent/invalid/stale, OR (c) `missing_track_ids.length > 0`
  - [ ] Set `needs_enrichment: false` after a successful client write once the raw-enrichment cache validates for the requested track set
- [ ] **Add `PUT /analysis/playlist/<id>/enrichment` endpoint**
  - [ ] **Auth verification:** Verify caller owns playlist `<id>` (fetch playlist owner from Spotify or stored analysis metadata)
  - [ ] Accept raw JSON envelope matching `CachedRawEnrichment` type: `{ audio_features, track_metadata, schema_version, cached_at, track_count }`
  - [ ] Write to `analysis:playlist:<id>:raw-enrichment` KV key (`analysis.ts:238-245`), **resetting TTL to 24h from write time**
  - [ ] Validate payload `schema_version` matches current `ANALYSIS_SCHEMA_VERSION`
  - [ ] Return `204 No Content` on success
  - [ ] Return a clear 4xx/5xx JSON error on validation/auth/KV write failure; partial dual-write handling belongs in the frontend because local disk is not visible to the Worker
  - [ ] Update `src/backend/docs/openapi.yaml` with `PUT /analysis/playlist/{id}/enrichment`, the new `AnalysisResult` fields, and the `CachedRawEnrichment` request schema

#### Frontend Changes

- [ ] **Add fetch method to `ReccoBeatsBackendService`** (`src/frontend/services/reccobeats_backend.py`)
  ```python
  def fetch_reccobeats_enrichment_direct(
      self,
      track_ids: list[str],
      batch_size: int = 50,
      timeout: int = 15,
      dry_run: bool = False,
  ) -> dict:
      """Fetch audio-features + track metadata from user's machine.
      
      Args:
          dry_run: If True, test reachability and return
              {"reachable": bool, "tested_track_ids": list[str],
               "status_code": int | None, "error": str | None}
              without writing backend KV or local disk cache.
      """
  ```
  - [ ] Batch requests (50 per batch)
  - [ ] **Add `parse_retry_after()` utility** to `src/frontend/utils/network_utils.py`
    - [ ] Handle both integer seconds and HTTP-date formats (mirror `spotify.ts:224-247`)
  - [ ] Respect `Retry-After` headers using a custom retry loop around direct `requests.get`; include `RateLimitError` only if `@retry_on_network_error` is intentionally expanded and covered by tests
  - [ ] Reuse existing `@handle_network_errors` for backend calls where appropriate; do not rely on it to preserve direct ReccoBeats `Retry-After` semantics
- [ ] **Add dual-cache write with partial failure handling**
  - [ ] Write to backend KV via new `PUT /enrichment` endpoint
  - [ ] Write to local disk cache using `get_cache_manager()` (not hardcoded path)
  - [ ] Ensure local cache writes surface failure explicitly (named exception or boolean result)
  - [ ] **Partial failure handling:**
    - If KV fails but disk succeeds → log warning, show "Results saved locally only" banner
    - If disk fails but KV succeeds → log warning, show "Backend cache updated" banner
    - If both writes fail → show error banner and preserve fetched data in memory only until user dismisses/retries
  - [ ] Add "Caching results..." progress indicator during write (fire-and-forget is too silent for 30+ sec operations)
- [ ] **Add UI affordance**
  - [ ] "Retry enrichment from this device" button on partial-data banners
  - [ ] Settings toggle: "Enable client-side ReccoBeats fetch" (opt-in, clearly labeled)
  - [ ] Per-session confirmation dialog on first fetch (privacy notice: sends IP to ReccoBeats)
    - [ ] Add `_reccobeats_privacy_accepted_session: bool` member to analysis screen or service
    - [ ] Session scope is process lifetime: reset on app restart, not playlist switch; store in memory only
  - [ ] "Backend cache updated" success indicator after write completes
- [ ] **Add feature flag integration**
  - [ ] Add `FeatureFlags.ENABLE_CLIENT_RECCOBEATS` in `src/frontend/config/backend_config.py`, backed by `SPOTIBYE_ENABLE_CLIENT_RECCOBEATS`
  - [ ] Gate UI toggle visibility behind flag
  - [ ] Document rollback: `SPOTIBYE_ENABLE_CLIENT_RECCOBEATS=false` env var disables feature
- [ ] **Add constants**
  - [ ] Define `RECCOBEATS_JITTER_DELAY_MS = 50` (or equivalent) in `PerformanceSettings`

#### Testing

- [ ] **Backend tests**
  - [ ] `PUT /enrichment` writes correct KV shape (all `CachedRawEnrichment` fields present)
  - [ ] Schema validation rejects malformed payloads
  - [ ] `needs_enrichment` signal set correctly on errors/empty cache
  - [ ] `needs_enrichment` returns to `false` after successful `PUT /enrichment` and a valid cached envelope
  - [ ] `GET /results` computes `missing_track_ids` from persisted analysis-time track IDs without refetching playlist tracks
  - [ ] **Auth verification:** Test that user cannot enrich another user's playlist
  - [ ] Test `missing_track_ids` computation from `href`, including ReccoBeats UUIDs that do not match Spotify IDs and metadata entries with/without `href`
  - [ ] OpenAPI schema test covers the new endpoint and response fields
- [ ] **Frontend tests**
  - [ ] `fetch_reccobeats_enrichment_direct` batches correctly
  - [ ] `parse_retry_after()` handles both integer seconds and HTTP-date formats
  - [ ] Direct ReccoBeats 429 responses respect `Retry-After` and retry with bounded attempts
  - [ ] Dry-run returns the documented reachability shape and performs no writes
  - [ ] Network errors retry with backoff
  - [ ] Dual-write handles partial failures (KV fail/disk success and vice versa)
  - [ ] Dual-write handles both-write failure with an error state
  - [ ] UI button appears on `needs_enrichment`
  - [ ] Privacy dialog appears once per session
  - [ ] Feature flag gates UI toggle visibility
- [ ] **Integration test**
  - [ ] Simulate Worker egress failure:
    - Option A: Use `wrangler dev --remote` with test Worker that throws on ReccoBeats fetch
    - Option B: Mock backend responses at HTTP level with `?simulate_egress_failure=true` query param
  - [ ] Verify frontend fetches → both caches populated → re-analysis uses cached data
  - [ ] Verify dry-run mode tests reachability without writing

**Exit criteria if revived:** All tests pass; feature flag gated; privacy notice in place; auth verification tested.

**Estimated effort:** 8-12 hours

---

### Phase 5: Cleanup & Hardening

**Goal:** Small, high-value fixes independent of the main workaround.

- [x] **Add boundary logging** (`analysis.ts:300`, before shape validation)
  - [x] Capture response body as **text** (truncate to ~500 chars), log it, **then** attempt JSON parse and shape validation on line 301
  - [x] Log to distinguish block page from empty JSON envelope
- [x] **Add IPv6 reachability check to dev workflow/script**
  - [x] `dig AAAA api.reccobeats.com` + `curl -6 https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B` from dual-stack machine (simulates Worker egress)
- [x] **Update investigation doc** with final resolution and lessons learned
- [x] **Changelog entry** for user-visible changes shipped in the current fix (improved error messages, smaller backend ReccoBeats batches, stale ReccoBeats-error cache retry)

**Exit criteria:** Debuggability improved; dev workflow has IPv6 check; changelog updated.

**Estimated effort:** 2-3 hours

---

## Open Questions

1. **Race handling:** If two users enrich the same playlist simultaneously, is last-write-wins acceptable? (Likely yes — both write identical raw JSON.)
2. **Partial data merging:** How to merge client-provided partial data with any Worker-provided partial data? (Proposed: merge by Spotify track ID extracted from `href`; client entries fill gaps and may replace older entries for the same ID in the same cache write.)
3. **Privacy notice wording:** What's the right balance of transparency without alarming users? (Proposed: "This sends your IP address directly to ReccoBeats.com — no API key required.")
4. **Abuse controls:** What rate-limit should we enforce client-side to avoid triggering ReccoBeats abuse detection? (Proposed: mirror Worker's `CONCURRENCY=3`, `BATCH_SIZE=30`, `RECCOBEATS_JITTER_DELAY_MS`.)
5. **Cache path strategy:** Should we use `get_cache_manager().get_cache_path()` for the local cache (consistent with existing cache infrastructure) or a new dedicated path? (Proposed: use existing cache manager for consistency.)
6. **Schema version divergence:** Is raw-enrichment versioning ever expected to diverge from `ANALYSIS_SCHEMA_VERSION`? (Proposed: no; reuse `schema_version: string` until there is a concrete separate compatibility need.)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ReccoBeats adds auth/rate-limiting later | Breaks frontend fetch | Feature flag kill switch; monitor error rates |
| Users decline privacy consent | Enrichment remains broken for some | Clear UX explanation; offer "skip" option |
| Catalog coverage too sparse | Feature provides little value even if working | Quantify in Phase 2; consider fallback recommendations if coverage < 50% |
| Client fetch triggers ReccoBeats abuse detection | IP bans for aggressive users | Client-side rate limiting; jitter; respect `Retry-After` |
| Cross-layer complexity exceeds estimate | Backend route, KV write, Kivy UI state, auth validation, OpenAPI, and network retry utility all change together | Keep each piece independently testable; 8h is achievable only if backend, utility, and UI tests can be run in isolation |

---

## Success Metrics

- [x] Error messages in popup allow immediate diagnosis of future failures
- [x] Decision made on frontend fetch fallback
  - Phase 1/2 showed Worker egress works for the known-good sample and the concrete failure was oversized 50-ID batches. Frontend-direct fetch is deferred as an optional backlog item, not implemented in the current fix.
- [x] Coverage percentage documented and decision made on ReccoBeats reliability
- [x] No user-visible regressions in playlist analysis flow
- [x] Changelog updated with user-visible changes

---

## References

- **Investigation:** [`../investigations/2026-07-09-reccobeats-enrichment-failure.md`](../../investigations/2026-07-09-reccobeats-enrichment-failure.md)
- **API Contract:** [`../reccobeats-api-contract.md`](../../reccobeats-api-contract.md)
- **Prior Audit:** [`../investigations/2026-07-05-reccobeats-enrichment-gaps.md`](../../investigations/2026-07-05-reccobeats-enrichment-gaps.md)
- **Backend Code:** `src/backend/services/analysis.ts:184-235` (enrichment fetch + `errors[]` push)
- **Frontend Code:** `src/frontend/services/reccobeats_backend.py` (ReccoBeatsBackendService)
- **UI Utils:** `src/frontend/ui/backend_playlist_card_utils.py:14-15` (`_describe_error_source`)

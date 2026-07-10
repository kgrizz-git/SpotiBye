# Assessment: ReccoBeats Egress Diagnosis & Frontend-Fetch Fallback Plan

**Date:** 2026-07-09  
**Status:** Complete  

## Summary

The plan is well-structured and technically sound. It correctly identifies the core problem (banners = rejection, not empty 200), separates egress failure from catalog coverage concerns, and proposes a viable desktop-app-specific solution.

## Strengths

1. **Correct diagnosis framing** — Banners appear only on fetch rejection (`Promise.allSettled` rejection path), not on empty `200` responses. This is accurately reflected in both documents.

2. **Desktop-app advantage recognized** — The plan correctly notes the Python desktop app bypasses CORS, making frontend fetch cleaner than it would be for a browser app.

3. **Good phase separation** — Phases 1-5 are logically ordered with clear exit criteria.

4. **Risk mitigation considered** — Feature flags, rate limiting, privacy gating, and coverage thresholds are all addressed.

## Gaps & Improvements

### 1. Coverage Quantification Methodology Needs Clarification

**Issue:** Phase 2 says "Test all track IDs" from the failing playlist, but the investigation shows 7 tracks were tested individually, not in batches.

**Impact:** The API may behave differently for 50-track batches vs. single IDs (truncation, partial responses, different error modes).

**Recommendation:** 
- Test actual playlist track IDs in **real batches of 50** (matching Worker's `BATCH_SIZE`)
- Document the exact batch behavior: does ReccoBeats return partial `content` for mixed-known/unknown tracks, or fail the entire batch?

### 2. Missing: Cache Key Namespacing Violation

**Issue:** The proposed `PUT /analysis/playlist/<id>/enrichment` writes to `analysis:playlist:<id>:raw-enrichment` which omits `userId` (per `analysis.ts:238-245`). However, the plan doesn't address that this key is already namespaced without user scope.

**Impact:** Low — this is intentional sharing behavior. But Phase 4 step 1 says "Set when `errors[]` for `reccobeats:*` is non-empty OR cached raw-enrichment has empty `content` for some present tracks" — this requires checking the existing cache, which means the frontend would need to know which tracks were missing.

**Recommendation:** Add clearer logic for `needs_enrichment` — it should trigger when:
- There are `reccobeats:*` errors (egress failed)
- OR the raw cache exists but has fewer entries than expected (partial coverage)

### 3. Retry-After Implementation for Frontend Fetch

**Issue:** Phase 4 step 1 mentions "Respect `Retry-After` headers" but the frontend `reccobeats_backend.py` currently has no `Retry-After` parsing logic. The backend uses `src/backend/services/spotify.ts:150-157` for this.

**Recommendation:** Either:
- Add `parse_retry_after` utility to frontend `network_utils.py`
- Or reference the existing `parseRetryAfter` in the plan as a pattern to follow

### 4. Missing: Cache Warm-up Race Condition

**Issue:** The plan proposes dual-write (local + KV) but doesn't address the race where:
1. User A starts analysis → egress fails → gets `needs_enrichment: true`
2. User A fetches from frontend → writes to KV
3. User B starts analysis → cache is now warm → no `needs_enrichment`
4. User A's write completes after User B's fetch began

**Impact:** Mild — last-write-wins is acceptable per open questions, but the UX could briefly show inconsistent state.

**Recommendation:** Add a "Backend cache updated" success indicator in the UI, or poll for cache invalidation after frontend write.

### 5. TTL Consistency Ambiguity

**Issue:** Phase 3 mentions "24h TTL consistency" but doesn't specify whether the frontend write should:
- Honor the existing TTL (24h from first fetch)
- Reset TTL to 24h from frontend fetch time
- Check if existing cache is older and only write if fresher

**Recommendation:** Specify that frontend writes reset the TTL (fresh fetch = fresh 24h window), matching typical cache semantics.

### 6. Missing: Local Cache Path Handling

**Issue:** Plan references `~/.spotibye/cache/analysis_<playlist_id>.json` but:
- The existing `CacheService` uses `get_cache_manager()` with different paths
- No migration strategy if users have old cache files

**Recommendation:** Use `get_cache_manager().get_cache_path()` or equivalent, not hardcoded paths. Or document this is a new path separate from legacy cache.

### 7. IPv6 Test Command Needs Refinement

**Issue:** Plan says `dig AAAA api.reccobeats.com` but Workers don't just need AAAA records — they need **working IPv6 connectivity**. A dead AAAA record would cause Worker fetch to fail, but testing AAAA alone won't confirm connectivity.

**Recommendation:** Clarify: `dig AAAA api.reccobeats.com` + `curl -6 https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B` from a dual-stack machine to simulate Worker egress.

### 8. Boundary Logging Should Include Response Text (Not Just Bytes)

**Issue:** Phase 5 says "capture first ~500 bytes of response body on shape mismatch" but `analysis.ts:301` throws before reading the body if `!response.ok`.

**Recommendation:** Actually, the check should be at `response.json()` time (`rawData` assignment). Capture the body as text, truncate to 500 chars, log it, THEN attempt JSON parse and shape validation.

### 9. Missing: Validation Schema for PUT /enrichment

**Issue:** Phase 4 step 2 mentions "Validate schema version and response shape" but doesn't specify the Zod schema or type guards needed.

**Recommendation:** Define `ZodReccoBeatsRawEnrichment` schema explicitly, or reference `CachedRawEnrichment` type.

### 10. Progress Callback Missing from Backend PUT

**Issue:** Phase 4 step 2 doesn't mention progress updates. The frontend fetch could take 30+ seconds for large playlists; users need feedback.

**Recommendation:** Either:
- Add no progress (fire-and-forget write)
- Or add a simple "Caching results..." indicator

## Additional Observations

- The code citations are accurate (updated in investigation per the commentary)
- Error message surfacing is correctly prioritized as highest-ROI
- The `errors[].message` already exists in `AnalysisResult` type; only frontend display is missing
- The existing `@handle_network_errors` decorator in frontend wraps exceptions but may not preserve `Retry-After` semantics

## Conclusion

The plan is solid but needs refinement in batch testing methodology, TTL/cache semantics, and response logging. The core approach (frontend fetch fallback) is appropriate given the desktop nature of the app.

**Recommended action:** Proceed with Phase 1 (error message display), then clarify the coverage testing batch behavior before implementing the frontend fetch.
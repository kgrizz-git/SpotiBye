# Assessment: ReccoBeats Wiring Plan & Implementation Status

**Date:** 2026-06-26T00:37:07-04:00
**Target Plan:** `docs/exec-plans/active/2026-06-21-reccobeats-wiring.md`

## 1. Plan Verification & Progress Status
The ReccoBeats wiring plan has successfully outlined and guided the migration from the old Python-monolith API calls to a Cloudflare Worker backend approach. 

- **Track A (Spotify Analysis):** Implemented successfully. `AnalysisService.analyzePlaylist` properly paginates using `rawCount` and extracts `overview`, `artists`, and `genre_distribution`.
- **Track B (ReccoBeats Spike & Adapter):** The API contract is documented accurately at `dev-docs/reccobeats-api-contract.md`. The backend code targets the correct public endpoint `GET /v1/audio-features`.
- **Track C (Cleanup):** Stale key references have been cleaned up and the old typo host `api.recocbeats.com` is no longer used.
- **Track D (Queue Hardening):** Implemented to handle background processing asynchronously.

However, the UI verification steps in the plan remain unchecked:
- `[ ] Double-clicking a playlist card opens the Playlist Analysis popup.`
- `[ ] Duration and artist sections populate.`
- `[ ] Genre distribution either populates or shows "No genre data available" without failing the job.`

## 2. Identified Bugs & Errors

### Backend Bug: URI Too Long (HTTP 414 Risk)
In `src/backend/services/analysis.ts`, the `fetchReccoBeatsAudioFeatures(trackIds: string[])` method appends all unique track IDs to the query string of a single GET request:
```typescript
const url = new URL(`${this.reccoBeatsUrl}/audio-features`);
for (const trackId of uniqueIds) {
  url.searchParams.append('ids', trackId);
}
```
If a playlist contains many tracks (e.g., 300+ tracks), appending all IDs to the URL will generate a very long query string that may exceed typical HTTP server or proxy limits (usually ~8KB). This could result in a `414 URI Too Long` error.
**Recommendation:** The backend should chunk the `uniqueIds` array into smaller batches (e.g., 50 at a time) and make multiple requests to `api.reccobeats.com`, aggregating the `content` arrays before returning.

### Frontend Integration Consideration
In `src/frontend/services/reccobeats_backend.py`, the legacy stub `get_multiple_track_audio_features_safe` raises a `NotImplementedError`. While the new `backend_playlist_card.py` is supposed to parse the flat JSON returned by the backend queue, any accidental usage of the old legacy methods elsewhere in the UI will crash the app. The unchecked verification steps suggest that the frontend UI integration needs an end-to-end runtime test.

## 3. ReccoBeats API Usage Status
- **Usage Model:** SpotiBye is no longer using ReccoBeats for genre distribution. Instead, it uses ReccoBeats exclusively for retrieving audio features (`danceability`, `energy`, etc.) based on Spotify track IDs. 
- **Data Persistence:** The worker does not persist raw ReccoBeats responses. It computes averages and stores a compact `audio_features` summary in the KV store result payload.
- **Fault Tolerance:** The backend implementation is robust to ReccoBeats failures. If the `fetchReccoBeatsAudioFeatures` call fails (e.g., due to the URL length bug mentioned above, or rate limits), the `try...catch` block gracefully catches the error and allows the analysis job to complete using only the Spotify metadata.

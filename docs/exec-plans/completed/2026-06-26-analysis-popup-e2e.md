# Analysis Popup End-to-End Wiring Plan

> **Linked from:** [TO_DO.md](../../dev-docs/TO_DO.md) · **Ties off:** [ReccoBeats wiring plan](2026-06-21-reccobeats-wiring.md) unchecked verification items
>
> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Mark steps complete (`- [x]`) as work is finished.

**Goal:** Make the playlist analysis popup fully functional end-to-end: fix the backend batching bug, render audio-feature data from ReccoBeats, update loading-state copy, guard against legacy stubs, and verify the complete flow.

**Prerequisite:** All backend tracks (A–D) from the [ReccoBeats wiring plan](2026-06-21-reccobeats-wiring.md) are complete. This plan covers the remaining UI integration and one backend bug.

---

## Current State

The analysis popup flow works as follows:

1. User double-clicks/long-presses a playlist card → `show_detailed_playlist_window()` opens popup
2. Background thread calls `adapter.analyze_playlist()` → `ReccoBeatsBackendService.analyze_playlist()` → `BackendClient.analyze_playlist()` (POST)
3. `ReccoBeatsBackendService._poll_analysis_completion()` polls `GET /status` with exponential backoff (2s→10s, 300s timeout)
4. On `completed` → fetches `GET /results` → returns flat `AnalysisResult` to popup
5. `_update_analysis_ui()` renders overview (duration), genre distribution, and artist analysis

**What's broken or missing:**

| Issue | Impact |
|---|---|
| `fetchReccoBeatsAudioFeatures()` puts all track IDs in one GET URL | HTTP 414 for playlists with 300+ tracks |
| `_update_analysis_ui()` ignores `audio_features` key | Danceability/energy/tempo/valence data is fetched but never shown |
| Loading text says "Retrieving analysis from ReccoBeats API..." | Misleading — analysis is Spotify-backed with best-effort ReccoBeats enrichment |
| `reccobeats_backend.py` has `NotImplementedError` stubs | Dead code but should be cleaned up or documented as intentionally dead |

---

## Step 1 — Fix ReccoBeats URL Batching (Backend)

**Files:**
- Modify: `src/backend/services/analysis.ts` — `fetchReccoBeatsAudioFeatures()`
- Modify: `src/backend/tests/analysis.test.ts`

**Problem:** All track IDs are appended to a single `GET /v1/audio-features?ids=...&ids=...` URL. For 300+ tracks with 22-char Spotify IDs, the query string exceeds ~8KB URL limits → HTTP 414.

- [x] Chunk `uniqueIds` into batches of 50 IDs per request inside `fetchReccoBeatsAudioFeatures()`
- [x] Make parallel requests (bounded concurrency, e.g. 3 concurrent) for each batch
- [x] Concatenate `content` arrays from all batch responses before aggregating
- [x] Add a test case with >50 mocked track IDs to verify batching occurs (assert multiple fetch calls)
- [x] Add a test case verifying that aggregated averages are correct across batches

**Implementation sketch:**

```typescript
private async fetchReccoBeatsAudioFeatures(
  trackIds: string[]
): Promise<ReccoBeatsAudioFeature[]> {
  const uniqueIds = [...new Set(trackIds.filter(Boolean))];
  if (uniqueIds.length === 0) return [];

  const BATCH_SIZE = 50;
  const batches: string[][] = [];
  for (let i = 0; i < uniqueIds.length; i += BATCH_SIZE) {
    batches.push(uniqueIds.slice(i, i + BATCH_SIZE));
  }

  const allFeatures: ReccoBeatsAudioFeature[] = [];

  // Process batches with bounded concurrency
  const CONCURRENCY = 3;
  for (let i = 0; i < batches.length; i += CONCURRENCY) {
    const chunk = batches.slice(i, i + CONCURRENCY);
    const results = await Promise.all(chunk.map(batch => this.fetchReccoBeatsAudioFeaturesBatch(batch)));
    for (const features of results) {
      allFeatures.push(...features);
    }
  }

  return allFeatures;
}

private async fetchReccoBeatsAudioFeaturesBatch(
  batchIds: string[]
): Promise<ReccoBeatsAudioFeature[]> {
  const url = new URL(`${this.reccoBeatsUrl}/audio-features`);
  for (const trackId of batchIds) {
    url.searchParams.append('ids', trackId);
  }
  // ... existing fetch + validation logic ...
}
```

---

## Step 2 — Render Audio Features in the Popup (Frontend)

**Files:**
- Modify: `src/frontend/ui/backend_playlist_card.py` — `_update_analysis_ui()`

**Problem:** The backend returns an optional `audio_features` key with this shape:

```json
{
  "audio_features": {
    "track_count": 42,
    "averages": {
      "danceability": 0.65,
      "energy": 0.78,
      "valence": 0.55,
      "tempo": 122,
      "acousticness": 0.12,
      "instrumentalness": 0.03,
      "liveness": 0.15,
      "loudness": -6.2,
      "speechiness": 0.05
    }
  }
}
```

The popup currently shows genre distribution and artist analysis but has no section for audio features.

- [x] After the artist analysis section in `_update_analysis_ui()`, add an "Audio Features" section
- [x] Read `results.get("audio_features", {})` and extract `averages` dict
- [x] Display the most useful subset as a compact section: danceability, energy, valence (mood), tempo (BPM), acousticness
- [x] Format 0–1 values as percentages (e.g. `0.65` → `65%`) and tempo as integer BPM
- [x] If `audio_features` is absent or empty, either skip the section entirely or show "Audio features unavailable"
- [x] Do not display `liveness`, `loudness`, `speechiness` by default — these are less meaningful to most users. Keep the section concise.

**Implementation sketch:**

```python
# Audio features (from ReccoBeats, best-effort)
audio_features = results.get("audio_features") or {}
averages = audio_features.get("averages") or {}
if averages:
    analysis_container.add_widget(_section_header("Audio Features:"))
    feature_labels = [
        ("Danceability", averages.get("danceability")),
        ("Energy", averages.get("energy")),
        ("Mood (Valence)", averages.get("valence")),
        ("Acousticness", averages.get("acousticness")),
    ]
    parts = []
    for label, val in feature_labels:
        if val is not None:
            parts.append(f"{label}: {val * 100:.0f}%")
    tempo = averages.get("tempo")
    if tempo is not None:
        parts.append(f"Tempo: {int(tempo)} BPM")
    if parts:
        analysis_container.add_widget(_small_label(" · ".join(parts)))
    track_count = audio_features.get("track_count", 0)
    if track_count:
        analysis_container.add_widget(
            _small_label(
                f"Based on {track_count} tracks with available audio data",
                color=(0.55, 0.55, 0.55, 1),
            )
        )
```

---

## Step 3 — Fix Loading Message Copy

**Files:**
- Modify: `src/frontend/ui/backend_playlist_card.py` — `_build_analysis_popup_content()`

- [x] Change line 481 from `"Retrieving analysis from ReccoBeats API..."` to `"Analyzing playlist..."`
- [x] This is a single string replacement — the analysis is Spotify-backed with best-effort ReccoBeats enrichment, not a ReccoBeats API call

---

## Step 4 — Guard or Clean Up Legacy Stubs

**Files:**
- Audit: `src/frontend/services/reccobeats_backend.py`

- [x] Verify that `get_multiple_track_audio_features_safe()` (raises `NotImplementedError`) is never called from production code
  - Expected result: only called by `get_multiple_track_audio_features()` (self-delegation) and test cases
  - If confirmed unreachable, no code change needed — just document in this step
- [x] Verify that the analysis popup flow only reaches `ReccoBeatsBackendService.analyze_playlist()` → `_poll_analysis_completion()` → `BackendClient` methods, never the legacy stubs
- [x] If stubs are confirmed dead, add a brief comment at the top of the class noting they exist only for compatibility and are not called in production

---

## Step 5 — End-to-End Verification

These are the unchecked items from the [ReccoBeats wiring plan](2026-06-21-reccobeats-wiring.md) verification checklist.

- [x] Double-clicking a playlist card opens the Playlist Analysis popup
- [x] Duration and artist sections populate with real data
- [x] Genre distribution either populates or shows "No genre data available" without failing the job
- [x] Audio features section appears when ReccoBeats returns data, or is absent/skipped gracefully
- [x] For a large playlist (200+ tracks), analysis completes without HTTP 414 errors
- [x] Popup loading text says "Analyzing playlist..." (not "ReccoBeats API")

**How to verify:**
1. Run `cd src/backend && npm run test:run && npm run lint` — all backend tests pass
2. Run `KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v` — frontend tests pass
3. Launch the app, log in, select a playlist, double-click — observe popup behavior

---

## Completion Criteria

When all steps are checked:

1. Move this plan to `docs/exec-plans/completed/`
2. Move the [ReccoBeats wiring plan](2026-06-21-reccobeats-wiring.md) to `docs/exec-plans/completed/` (all its items are now covered)
3. Update [TO_DO.md](../../dev-docs/TO_DO.md) — mark the "Analysis popup e2e wiring" and related items complete
4. Update `CHANGELOG.md` with the user-visible change (audio features now visible in analysis popup)

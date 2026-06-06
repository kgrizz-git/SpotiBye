# Playlist Analysis Popup — State & Opportunities

Covers what the analysis popup currently shows, what Spotify data is available but unused, and the current ReccoBeats status.

---

## What was broken and what was fixed

The double-click / long-press on a playlist card used to open a two-step flow:

1. **Playlist Analysis popup** — metadata, genre distribution, artist analysis, "Show Tracks" button
2. **Tracks window** — full track listing, opened by "Show Tracks"

During the v2 extraction refactor the `BackendPlaylistCard` lost this flow and went directly to the track list with no analysis panel.

**Fixed in:** [src/frontend/ui/backend_playlist_card.py](src/frontend/ui/backend_playlist_card.py)

Restored flow:
- `show_detailed_playlist_window()` opens the **Playlist Analysis** popup
- Left panel: playlist cover, image dimensions, technical details (Owner ID, Playlist ID, Version/snapshot_id)
- Right panel: name, creator, URLs, type, track count + duration, genre distribution, artist analysis
- "Show Tracks" button (top-right of popup) opens a separate tracks window with title, subtitle, and track table
- Analysis data loads in the background via `adapter.analyze_playlist()`; shows "Retrieving analysis from ReccoBeats API..." until it arrives or fails

---

## Spotify audio features — available but unused

The backend exposes a per-track audio features endpoint that is fully wired but never called from the analysis popup.

**Backend route:** `GET /spotify/tracks/:id/audio-features`
→ [src/backend/routes/spotify.ts:193](src/backend/routes/spotify.ts#L193)

**Python client method:** `BackendClient.get_track_audio_features(track_id)`
→ [src/frontend/services/backend_client.py](src/frontend/services/backend_client.py)

### What this returns (per track)

| Field | Description |
|---|---|
| `danceability` | 0–1, how suitable for dancing |
| `energy` | 0–1, intensity and activity |
| `tempo` | BPM (float) |
| `valence` | 0–1, musical positivity / mood |
| `acousticness` | 0–1 confidence it's acoustic |
| `instrumentalness` | 0–1 likelihood of no vocals |
| `speechiness` | 0–1 presence of spoken words |
| `loudness` | Average dB (typically −60 to 0) |
| `key` | Pitch class 0–11 (C=0, C#=1, …) |
| `mode` | 0 = minor, 1 = major |
| `time_signature` | Estimated time signature |
| `duration_ms` | Track length in milliseconds |

### What we could show in the analysis popup

Averaging `danceability`, `energy`, `valence`, and `tempo` across all tracks in a playlist gives a useful summary without needing ReccoBeats:

- **Total duration** — sum of all `duration_ms` (currently shown as "Tracks: N", no duration)
- **Average BPM** — mean `tempo`
- **Energy / Danceability / Mood** — mean values as percentage bars or numbers
- **Key distribution** — most common key across the playlist

### Deprecation caveat

Spotify deprecated the `/audio-features` endpoint for new app registrations in late 2024. Apps that already have access retain it. Worth checking whether the deployed credentials still have access before building UI around it.

---

## ReccoBeats status — not actually fetching

The genre distribution and artist analysis shown in the original screenshots came from v2's **standalone mode**, which called ReccoBeats directly from Python. The backend-mode analysis pipeline has multiple blockers.

### Blocker 1 — URL typo

[src/backend/services/analysis.ts:5](src/backend/services/analysis.ts#L5):
```ts
private reccoBeatsUrl = 'https://api.recocbeats.com/v1';
//                                     ^^^^^ missing an 'o'
```
The correct hostname is `reccobeats.com`. All `POST /analyze` calls go to the wrong domain and fail.

### Blocker 2 — Cloudflare Workers fire-and-forget

[src/backend/routes/analysis.ts:50](src/backend/routes/analysis.ts#L50) launches analysis without `await`:
```ts
analysisService.analyzePlaylist(...).catch(error => { ... });
return c.json({ status: 'processing' });
```
Cloudflare Workers terminate the moment the response is sent. The background promise is killed immediately — the analysis never runs regardless of the URL.

### Blocker 3 — Results never written to KV

Even if the above two were fixed, `AnalysisService.analyzePlaylist()` returns results but the route handler discards the return value — it is never written to the `analysis:{id}:{userId}:results` KV key, so `GET /results` always returns 404.

### Blocker 4 — `reccobeats.ts` stub is dead code

[src/backend/services/reccobeats.ts](src/backend/services/reccobeats.ts) is a test-only stub (`throw new Error('not implemented')` in non-test environments) and is never imported by any route. It is not the live integration path.

**Full detail and suggested fixes for all four:** see [backend-analysis-routes.md](backend-analysis-routes.md).

### Summary table

| Concern | Status |
|---|---|
| Backend route exists for analysis | ✅ |
| ReccoBeats URL correct | ❌ typo (`recocbeats` vs `reccobeats`) |
| Analysis actually executes in Workers | ❌ fire-and-forget killed at response time |
| Results written to KV | ❌ return value discarded |
| `/results` endpoint returns real data | ❌ always 404 |
| `reccobeats.ts` used in production | ❌ test stub only |
| Standalone (v2) ReccoBeats path | ✅ works, direct Python → ReccoBeats |

---

## `RECOCOBEATS` env var typo

Across tests and `.env` files the environment variable is consistently spelled `RECOCOBEATS_API_KEY` (extra `O`), while `README.md` uses `RECCOBEATS_API_KEY`. Neither name is read by `AnalysisService` anyway (it has a hardcoded URL), but this should be normalised when the analysis pipeline is properly wired.

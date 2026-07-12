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
- Analysis data loads in the background via `adapter.analyze_playlist()`. The current loading copy still says "Retrieving analysis from ReccoBeats API...", but backend-mode analysis is presently Spotify-backed.

---

## Spotify audio features — restricted / unused

The backend still exposes a per-track audio features endpoint, but the analysis popup does not use it and backend playlist analysis must not depend on it.

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

### Access caveat

Spotify restricted the `/audio-features` endpoint for many apps. Do not build playlist analysis UI that depends on this endpoint unless access is explicitly verified for the deployed credentials.

---

## Current backend analysis status

The genre distribution and artist analysis shown in the original screenshots came from v2's **standalone mode**, which called ReccoBeats directly from Python. Backend-mode analysis currently uses Spotify playlist item metadata plus best-effort Spotify artist metadata.

### What works now

- `POST /analysis/playlist/:id` queues analysis and stores queued status in the `ANALYSIS_STATUS` Durable Object.
- The Cloudflare Queues consumer runs analysis outside the initial HTTP request and can retry failed deliveries.
- Completed results are written to KV at `analysis:{playlistId}:{userId}:results`.
- `GET /analysis/playlist/:id/results` returns cached results after completion; it only returns 404 when no result exists.
- Playlist tracks are paginated with Spotify's raw page count, so local/unavailable filtered items do not stop pagination early.
- Artist metadata is fetched individually with `GET /artists/{id}` because Spotify removed the `GET /artists?ids=...` batch endpoint for affected apps.
- Genre distribution is best-effort. Spotify artist `genres` are deprecated, and analysis now completes with an empty `genre_distribution` if artist metadata fails.
- ReccoBeats audio features are fetched best-effort from `GET https://api.reccobeats.com/v1/audio-features?ids=<spotify_track_id>` and aggregated into a compact `audio_features` summary when available.

### ReccoBeats scope

`AnalysisService.analyzePlaylist()` uses ReccoBeats only for stored audio-feature lookup. It does not call uploaded-audio extraction and does not call the unverified `POST /v1/analyze` path.

The old `src/backend/services/reccobeats.ts` stub has been deleted. Do not reference it as the live integration path.

The verified API contract is tracked in [reccobeats-api-contract.md](reccobeats-api-contract.md).

### Summary table

| Concern | Status |
|---|---|
| Backend route exists for analysis | ✅ |
| Analysis executes in Workers | ✅ via Cloudflare Queues consumer |
| Results written to KV | ✅ |
| `/results` endpoint returns real data | ✅ after completion |
| Spotify artist batch endpoint used | ❌ replaced with individual `GET /artists/{id}` |
| Genre distribution | Best-effort via deprecated Spotify artist `genres` |
| ReccoBeats live backend integration | ✅ best-effort stored audio features |
| `reccobeats.ts` used in production | ❌ deleted |

---

## `RECOCOBEATS` env var typo

Older docs and tests used `RECOCOBEATS_API_KEY` / `RECCOBEATS_API_KEY`, but ReccoBeats public API access does not require a key. Active backend config no longer requires either variable.

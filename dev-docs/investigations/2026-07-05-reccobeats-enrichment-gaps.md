# ReccoBeats Enrichment Gaps — Playlist Analysis Popup

**Date:** 2026-07-05
**Context:** Audit of ReccoBeats API endpoints versus what SpotiBye retrieves and displays in the backend-mode playlist analysis popup (`src/frontend/ui/backend_playlist_card.py`).

## What We Currently Display

The popup renders a single-line "Audio Features" section like:

> Danceability: 60% · Energy: 80% · Mood (Valence): 45% · Acousticness: 30% · Tempo: 120 BPM

All five values are crammed into one `Label` widget with " · " separators (`backend_playlist_card.py:653-667`). There is no per-feature row layout.

### What "Mood (Valence)" Means

`valence` is a standard audio feature (0.0–1.0) measuring **musical positivity**:
- **0.0** = sad, melancholic, dark
- **1.0** = happy, euphoric, cheerful

A value of 0.45 (displayed as "45%") is actually slightly on the sad/negative side, but a user has no way to know that from the raw percentage. We should translate this into human-readable labels (e.g., "Melancholic", "Upbeat") or at least add a tooltip/note explaining the scale.

Suggested translation bands:
- 0.00–0.20: "Melancholic"
- 0.20–0.40: "Somber"
- 0.40–0.60: "Neutral"
- 0.60–0.80: "Cheerful"
- 0.80–1.00: "Euphoric"

## What We Currently Retrieve

The backend (`src/backend/services/analysis.ts`) fetches **all 9** audio-feature fields from `GET /v1/audio-features` and aggregates them into `audio_features.averages`:

- `acousticness`
- `danceability`
- `energy`
- `instrumentalness`
- `liveness`
- `loudness`
- `speechiness`
- `tempo`
- `valence`

Additionally, ReccoBeats returns `key` and `mode` per track, but the backend does **not** aggregate them into the `audio_features` summary, so they never reach the UI.

## Historical Context: Spotify Audio Features (Pre-Split)

Before the frontend/backend architecture split, SpotiBye was a monolithic Python/Kivy app under `src/spotify_playlist_exporter_v2/`. In that era:

- **Spotify provided per-track audio features** via `GET /audio-features/{id}` and batch `GET /audio-features?ids=...`.
- The app fetched these from Spotify, stored them per-track in a local JSON disk cache (`~/.spotibye/cache/`), and displayed all 11 features per track in the cache explorer UI.
- The legacy `cache_explorer.py` UI (still present at `src/frontend/ui/cache_explorer.py`) shows: Danceability, Energy, Valence, Tempo, Acousticness, Instrumentalness, Liveness, Speechiness, Key, Mode, and Loudness.

## The February 2026 Migration

Spotify's Development Mode migration (February 2026) removed or severely restricted the `/audio-features` endpoint family. The backend code explicitly notes this at `src/backend/services/analysis.ts:152`:

> *"Spotify /audio-features was removed in the Feb 2026 API migration."*

After the migration, playlist analysis switched to **ReccoBeats** as a best-effort replacement for audio features. The backend still maintains a `GET /spotify/tracks/:id/audio-features` route, but playlist analysis no longer depends on it.

Other Spotify changes around the same time:
- `GET /artists?ids=...` (batch artist endpoint) was removed; we now fetch artists individually.
- `GET /playlists/{id}/tracks` was renamed to `/playlists/{id}/items`.
- `popularity` and `email` fields were removed from Development Mode responses.

Full details: [`dev-docs/investigations/february-2026-spotify-migration-findings.md`](february-2026-spotify-migration-findings.md)

## ReccoBeats API Endpoints — Full Inventory

We currently call **only one** ReccoBeats endpoint. Here is the complete public API:

| Endpoint | Method | Description | We Use It |
|----------|--------|-------------|-----------|
| `/v1/track/recommendation` | GET | Mood/energy-based track recommendations | ❌ No |
| `/v1/track/:id` | GET | Single track metadata | ❌ No |
| `/v1/track?ids=...` | GET | Batch track metadata (ISRC, popularity, ReccoBeats UUID) | ❌ No |
| `/v1/track/:id/album` | GET | Track's album | ❌ No |
| `/v1/track/:id/audio-features` | GET | Single track audio features | ❌ No |
| `/v1/audio-features?ids=...` | GET | **Batch audio features lookup** | ✅ Yes |
| `/v1/artists/:id` | GET | Artist details | ❌ No |
| `/v1/albums/:id` | GET | Album details | ❌ No |
| `/v1/analysis/audio-features` | POST | Upload audio file (5MB max, 30s max) for feature extraction | ❌ No |

## Missing Features & Endpoints

### Not displayed (but retrieved)
- **Instrumentalness, Liveness, Loudness, Speechiness** — aggregated by backend, omitted from popup UI.
- **Key, Mode** — returned by ReccoBeats but not aggregated by backend or displayed.

### Not retrieved at all
- **ISRC** — available from `GET /v1/track`, absent from app.
- **ReccoBeats Popularity** — available from `GET /v1/track`, absent from app.
- **Track Recommendations** — `GET /v1/track/recommendation` offers mood/energy filtering, never explored.

### Documented but not implemented
Our OpenAPI spec (`src/backend/docs/openapi.yaml`) and API examples document an `include_recommendations` flag and a response field with `energy_score` and `similar_playlists` (e.g., "Energy Boost"). This feature does **not** exist in the actual backend routes or services.

## Summary Table

| Capability | Status |
|------------|--------|
| `GET /v1/audio-features` (batch) | ✅ Used |
| `GET /v1/track` (batch metadata) | ❌ Not called — misses `isrc` and ReccoBeats `popularity` |
| `GET /v1/track/recommendation` | ❌ Not called — mood/energy-based recommendations unexplored |
| Instrumentalness, Liveness, Loudness, Speechiness | ✅ Retrieved, ❌ **Not displayed** |
| Key, Mode | ✅ Retrieved, ❌ **Not aggregated or displayed** |
| ISRC, ReccoBeats Popularity | ❌ **Not retrieved, not displayed** |
| `recommendations` / `energy_score` / similar playlists | ❌ **Documented in OpenAPI but not implemented** |

## References

- `src/backend/services/analysis.ts` — backend aggregation logic (note at line 152 about Spotify removal)
- `src/frontend/ui/backend_playlist_card.py` — popup UI rendering (lines 653-667)
- `src/frontend/ui/cache_explorer.py` — legacy UI that showed all 11 features per track
- `dev-docs/reccobeats-api-contract.md` — verified endpoint contracts
- `dev-docs/investigations/february-2026-spotify-migration-findings.md` — Spotify API migration details
- `src/backend/docs/openapi.yaml` — aspirational recommendations schema
- `src/backend/docs/api-examples.md` — unimplemented recommendations examples

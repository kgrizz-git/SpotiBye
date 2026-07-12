# ReccoBeats API Contract

> **Agent entry point for ReccoBeats.** Before changing analysis enrichment, export
> audio-feature mapping, or per-track caching, read this file. Live shapes and
> omission semantics here override older assumptions in TypeScript types when they
> disagree (see [Type drift](#type-drift-vs-live-api)).

**Last verified live:** 2026-07-12 (no-auth `curl` against production API)  
**Earlier verify:** 2026-06-19 (initial wiring)

## Sources

- Public docs introduction: https://reccobeats.com/docs/documentation/introduction
- Request/response conventions: https://reccobeats.com/docs/documentation/request-and-response
- Rate limits: https://reccobeats.com/docs/documentation/rate-limiting
- Multiple tracks endpoint: https://reccobeats.com/docs/apis/get-tracks
- Track audio features endpoint: https://reccobeats.com/docs/apis/get-track-audio-features
- Multiple audio features endpoint: https://reccobeats.com/docs/apis/get-audio-features
- Uploaded-audio feature extraction endpoint: https://reccobeats.com/docs/documentation/Analysis/audio-features-extraction
- Coverage probe script: `scripts/test_reccobeats_coverage.py`
- Active plan using this contract: [`exec-plans/active/2026-07-12-per-track-reccobeats-cache-and-enrichment-refresh.md`](exec-plans/active/2026-07-12-per-track-reccobeats-cache-and-enrichment-refresh.md)

## Base URL And Auth

- Base URL: `https://api.reccobeats.com`
- API version path: `/v1`
- Authentication: **none** required for public API access
- Prefer repeated `ids` query params (not comma-separated) to avoid escaping ambiguity

Do **not** call `https://api.recocbeats.com` (typo host).  
Do **not** call unverified `POST /v1/analyze`.

## Critical join-key rules (agents: read this first)

| Field | Meaning |
|-------|---------|
| `id` | **ReccoBeats UUID** — never use as a Spotify track ID or export/cache key |
| `href` (track-level) | Spotify track URL — **only reliable Spotify join key** |
| `artists[].href` | Spotify **artist** URL — not a track ID |

**Observed `href` format (2026-07-12):**

```text
https://open.spotify.com/track/{22-char-spotify-id}
```

Parse Spotify ID as the path segment after `/track/` (strip query/hash). Reference: `extract_spotify_id_from_href` in `scripts/test_reccobeats_coverage.py`.

**Both** `GET /v1/audio-features` and `GET /v1/track` return track-level `href` on successful rows. Do not invent a ReccoBeats-UUID→Spotify mapping for cache keys when `href` is present.

**No `time_signature`** on audio-features responses. Export / UI must not expect it from ReccoBeats.

## Omission semantics (batch + miss detection)

Verified 2026-07-12:

| Situation | HTTP | `content` |
|-----------|------|-----------|
| Known good Spotify ID | 200 | One object with track-level `href` |
| Valid-shaped ID with no ReccoBeats data | 200 | Row **omitted** (or empty array if alone) |
| Fake / unknown IDs only | 200 | `"content": []` |
| Mixed known + missing in one batch | 200 | Only known rows; missing IDs **omitted** (not `null` placeholders) |

**Miss set for caching / coverage:**

```text
requested_spotify_ids − { parseSpotifyId(row.href) for each row in content }
```

Do **not** assume `content.length === requested.length` or positional alignment.  
`fetchReccoBeats*Batch` must map via `href`, not by array index or ReccoBeats `id`.

**Negative-cache implication:** IDs that return no row after a successful 200 should get a short-TTL “absent” sentinel (see active per-track cache plan), or every open will re-hit ReccoBeats for permanent misses (local files, unavailable recordings, gaps in ReccoBeats coverage).

### Probe examples (2026-07-12)

```bash
# Hit
curl -sS "https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B"
curl -sS "https://api.reccobeats.com/v1/track?ids=01K4zKU104LyJ8gMb7227B"

# Miss (valid Spotify ID shape, empty content)
curl -sS "https://api.reccobeats.com/v1/audio-features?ids=4cOdK2wGLETKBW3PvgPWoT"

# Mixed: returns only the known track
curl -sS "https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B&ids=0000000000000000000000"
```

## Identifier Support

ReccoBeats accepts Spotify track IDs in the `ids` query parameter for track metadata and stored audio features.

## Track metadata — `GET /v1/track`

```http
GET https://api.reccobeats.com/v1/track?ids=01K4zKU104LyJ8gMb7227B
```

Observed response shape (2026-07-12; fields beyond the 2026-06-19 sample noted):

```json
{
  "content": [
    {
      "id": "70b85474-5c5e-4430-a309-f1d71ee5cb23",
      "trackTitle": "Nothing New (feat. Phoebe Bridgers) (Taylor’s Version) (From The Vault)",
      "artists": [
        {
          "id": "c7b330b5-a62e-420c-bf02-943ca6bb8746",
          "name": "Taylor Swift",
          "href": "https://open.spotify.com/artist/06HL4z0CvFAxyc27GXpf02"
        },
        {
          "id": "1d86b797-24d1-444b-85a0-8cccdc32bbd8",
          "name": "Phoebe Bridgers",
          "href": "https://open.spotify.com/artist/1r1uxoy19fzMxunt3ONAkG"
        }
      ],
      "durationMs": 258812,
      "isrc": "USUG12103683",
      "ean": null,
      "upc": null,
      "href": "https://open.spotify.com/track/01K4zKU104LyJ8gMb7227B",
      "availableCountries": "AR,AU,AT,...",
      "popularity": 69
    }
  ]
}
```

| Field | Required for SpotiBye use | Notes |
|-------|---------------------------|--------|
| `id` | yes (string) | ReccoBeats UUID |
| `href` | **yes for join** | Spotify track URL |
| `trackTitle` | yes | |
| `artists[]` | yes | each: `id`, `name`, `href` (artist) |
| `durationMs` | yes | |
| `isrc` | optional | |
| `popularity` | optional | ReccoBeats popularity, not Spotify |
| `ean` / `upc` | optional | often `null` |
| `availableCountries` | optional | comma-separated country codes |

## Audio features — `GET /v1/audio-features`

```http
GET https://api.reccobeats.com/v1/audio-features?ids=01K4zKU104LyJ8gMb7227B
```

Observed response shape:

```json
{
  "content": [
    {
      "id": "70b85474-5c5e-4430-a309-f1d71ee5cb23",
      "href": "https://open.spotify.com/track/01K4zKU104LyJ8gMb7227B",
      "isrc": "USUG12103683",
      "acousticness": 0.817,
      "danceability": 0.606,
      "energy": 0.377,
      "instrumentalness": 0.0,
      "key": 0,
      "liveness": 0.154,
      "loudness": -9.455,
      "mode": 1,
      "speechiness": 0.0275,
      "tempo": 101.96,
      "valence": 0.446
    }
  ]
}
```

| Field | Notes |
|-------|--------|
| `key` | Pitch class 0–11 (same convention as Spotify) |
| `mode` | 0 = minor, 1 = major |
| `time_signature` | **Not returned** — do not map from ReccoBeats |

## Type drift vs live API

As of 2026-07-12 SpotiBye code:

- `ReccoBeatsAudioFeature` in `src/backend/types/analysis.ts` requires `href` — matches live API.
- `ReccoBeatsTrackMetadata` comment says Spotify ID is in `href` if present, but the **interface and `isReccoBeatsTrackMetadata` do not require/read track-level `href`**. Live `/v1/track` **does** return `href`. Treat this as implementation drift to fix when wiring per-track cache (plan B0).
- Batch fetch helpers currently concatenate `content` without mapping rows back to requested Spotify IDs via `href` — unsafe for per-track KV keys and for export.

## Uploaded Audio Extraction

`POST /v1/analysis/audio-features` accepts an uploaded audio file as `multipart/form-data`, with `audioFile` as the required body parameter. This is not viable for SpotiBye playlist analysis because Spotify audio cannot be downloaded for upload to ReccoBeats.

## Genre Distribution

No verified ReccoBeats endpoint returns genre distribution. Keep backend genre distribution sourced from Spotify artist metadata, and treat it as best-effort because Spotify marks artist `genres` deprecated.

## Rate Limits

The public docs say rate limits are enforced internally, 429 responses are possible, and clients should check `Retry-After`. The exact request threshold is not published. Keep batch sizes under ReccoBeats’ upstream ID cap (SpotiBye analysis uses batches below 40).

## Backend Decision

Use the **audio features lookup** + **track metadata** paths:

- Extract Spotify track IDs from playlist items.
- Query `GET /v1/audio-features` and `GET /v1/track` with repeated `ids` query parameters.
- Map each returned row to a Spotify ID via track-level `href`.
- Treat ReccoBeats data as best-effort; compute miss sets from omitted IDs.
- Keep Spotify overview, artist, and genre sections available even if ReccoBeats fails or returns partial data.

## See Also

- [`exec-plans/active/2026-07-12-per-track-reccobeats-cache-and-enrichment-refresh.md`](exec-plans/active/2026-07-12-per-track-reccobeats-cache-and-enrichment-refresh.md) — per-track cache + hotfix plan (includes this verification)
- [`investigations/2026-07-05-reccobeats-enrichment-gaps.md`](investigations/2026-07-05-reccobeats-enrichment-gaps.md) — historical audit of display/aggregation gaps
- [`investigations/2026-07-09-reccobeats-enrichment-failure.md`](investigations/2026-07-09-reccobeats-enrichment-failure.md) — Worker egress / reliability
- [`backlog/TO_DO.md`](backlog/TO_DO.md) — export migration and optional client-side fetch

# ReccoBeats API Contract

Verified on 2026-06-19 for backend playlist analysis wiring.

## Sources

- Public docs introduction: https://reccobeats.com/docs/documentation/introduction
- Request/response conventions: https://reccobeats.com/docs/documentation/request-and-response
- Rate limits: https://reccobeats.com/docs/documentation/rate-limiting
- Multiple tracks endpoint: https://reccobeats.com/docs/apis/get-tracks
- Track audio features endpoint: https://reccobeats.com/docs/apis/get-track-audio-features
- Multiple audio features endpoint: https://reccobeats.com/docs/apis/get-audio-features
- Uploaded-audio feature extraction endpoint: https://reccobeats.com/docs/documentation/Analysis/audio-features-extraction

## Base URL And Auth

- Base URL: `https://api.reccobeats.com`
- API version path: `/v1`
- Authentication: none required for public API access.

## Identifier Support

ReccoBeats accepts Spotify track IDs in the `ids` query parameter for track metadata and stored audio features.

Verified request:

```http
GET https://api.reccobeats.com/v1/track?ids=01K4zKU104LyJ8gMb7227B
```

Observed response shape:

```json
{
  "content": [
    {
      "id": "70b85474-5c5e-4430-a309-f1d71ee5cb23",
      "trackTitle": "Nothing New (feat. Phoebe Bridgers) (Taylor's Version) (From The Vault)",
      "artists": [
        {
          "id": "c7b330b5-a62e-420c-bf02-943ca6bb8746",
          "name": "Taylor Swift",
          "href": "https://open.spotify.com/artist/06HL4z0CvFAxyc27GXpf02"
        }
      ],
      "durationMs": 258812,
      "isrc": "USUG12103683",
      "href": "https://open.spotify.com/track/01K4zKU104LyJ8gMb7227B",
      "popularity": 69
    }
  ]
}
```

The `id` field is a ReccoBeats UUID. The original Spotify track URL is available in `href`.

## Audio Features Lookup

Use this endpoint for playlist-level ReccoBeats enrichment:

```http
GET https://api.reccobeats.com/v1/audio-features?ids=<spotify_track_id>
```

The public docs also allow array query parameters as repeated `ids` values or comma-separated values. Prefer repeated `ids` parameters because they avoid comma escaping ambiguity.

Verified request:

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
      "instrumentalness": 0,
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

## Uploaded Audio Extraction

`POST /v1/analysis/audio-features` accepts an uploaded audio file as `multipart/form-data`, with `audioFile` as the required body parameter. This is not viable for SpotiBye playlist analysis because Spotify audio cannot be downloaded for upload to ReccoBeats.

## Genre Distribution

No verified ReccoBeats endpoint returns genre distribution. Keep backend genre distribution sourced from Spotify artist metadata, and treat it as best-effort because Spotify marks artist `genres` deprecated.

## Rate Limits

The public docs say rate limits are enforced internally, 429 responses are possible, and clients should check `Retry-After`. The exact request threshold is not published.

## Backend Decision

Use the **audio features lookup** path:

- Extract Spotify track IDs from playlist items.
- Query `GET /v1/audio-features` with repeated `ids` query parameters.
- Treat ReccoBeats data as best-effort.
- Aggregate returned numeric audio-feature fields into a compact `audio_features` section.
- Keep Spotify overview, artist, and genre sections available even if ReccoBeats fails or returns partial data.

Do not call `https://api.recocbeats.com`.
Do not call unverified `POST /v1/analyze`.

## See Also

- [`dev-docs/investigations/2026-07-05-reccobeats-enrichment-gaps.md`](investigations/2026-07-05-reccobeats-enrichment-gaps.md) — full audit of which ReccoBeats endpoints we use vs. skip, what we display vs. retrieve, Spotify `/audio-features` history, and unimplemented backend features.

# Spotify Web API Reference

> Key information about the Spotify Web API endpoints used in SpotiBye. Agents: read this before modifying anything in `services/spotify.ts` or `routes/spotify.ts`.

---

## Base URL

```
https://api.spotify.com/v1
```

All requests require `Authorization: Bearer <access_token>`.

---

## Endpoints Used

### Playlists

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/me/playlists` | List current user's playlists. Paginated (`limit`, `offset`). |
| `GET` | `/playlists/{id}` | Get a single playlist object. |
| `GET` | `/playlists/{id}/items` | Get tracks/episodes in a playlist. Paginated. **See migration note below.** |

### Tracks & Audio Features

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tracks/{id}` | Get a single track. |
| `GET` | `/audio-features/{id}` | **Removed/restricted** in the Feb 2026 Dev Mode migration. Still called by `SpotifyService.getAudioFeatures` / the export path (dead code — see `TO_DO.md`'s export migration item); do not add new callers. Playlist analysis uses ReccoBeats instead (`services/analysis.ts`). |
| `GET` | `/audio-features?ids=...` | Same removal status as above; still called by `SpotifyService.getMultipleAudioFeatures` (dead export path only). |

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `https://accounts.spotify.com/api/token` | Exchange auth code or refresh token. |
| `GET` | `https://accounts.spotify.com/authorize` | PKCE authorization redirect. |

---

## Pagination

All list endpoints return a `Paging` object:

```json
{
  "href": "...",
  "items": [...],
  "limit": 20,
  "next": "...",
  "offset": 0,
  "previous": null,
  "total": 150
}
```

Fetch subsequent pages by incrementing `offset` or following `next`.

---

## Rate Limits

- No official rate limit is published. In practice, ~180 requests/minute is safe.
- On 429, response includes `Retry-After: <seconds>`. Back off and retry.
- The backend currently has **no explicit retry logic** — this is a known gap (see tech-debt-tracker #2).

---

## February 2026 Migration Notes

> **Critical — agents must read this before touching playlist endpoints.**
> Full details: [`february-2026-spotify-migration-findings.md`](../investigations/february-2026-spotify-migration-findings.md)

Key breaking changes for apps in **Development Mode**:

1. **Endpoint rename:** `/playlists/{id}/tracks` → `/playlists/{id}/items`
2. **Response shape change:** Nested field renamed from `.track` to `.item` in playlist item responses
3. **`popularity` field removed** from Track objects in Development Mode
4. **`/audio-features` endpoints removed/restricted.** Playlist analysis (`services/analysis.ts`) uses ReccoBeats (`api.reccobeats.com/v1/audio-features`, `/v1/track`) instead. `SpotifyService.getAudioFeatures`/`getMultipleAudioFeatures` remain only for the export path's dead `include_audio_features` flag — see [`february-2026-spotify-migration-findings.md`](../investigations/february-2026-spotify-migration-findings.md) and `TO_DO.md`'s export-migration backlog item.

**Current status (as of May 2026):** Some changes were paused or partially reversed. A possible "developer tier" is under discussion. Treat all playlist endpoint code as potentially requiring updates. The `SpotifyPlaylistTrackItem` type in `types/spotify.ts` should normalize both old and new shapes.

---

## Known Quirks

- The `/me/playlists` endpoint does not return collaborative playlists the user follows but does not own.
- `audio-features` returns `null` for some tracks (podcasts, local files). Always null-check.
- Token expiry is 3600 seconds. The backend handles refresh in `services/spotify-auth.ts`.
- Client Credentials flow (no user auth) can access public playlists — potentially useful for future features, but not currently implemented.

---

## Scopes Required

```
playlist-read-private
playlist-read-collaborative
user-read-private
user-read-email
```

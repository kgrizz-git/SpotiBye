# Spotify API — Available Data for Playlist Enrichment

What the Spotify Web API currently provides that could improve the Playlist Analysis popup. Verified against Spotify developer docs as of May 2026.

---

## Endpoint access status (as of Nov 27, 2024)

Spotify split their Web API into two tiers after a crackdown on automation/AI abuse:

| Tier | Who can use it |
|---|---|
| **Standard** | All registered apps |
| **Extended** | Apps with 250K+ MAU, legally registered business, available in key Spotify markets ([source](https://developer.spotify.com/blog/2025-04-15-updating-the-criteria-for-web-api-extended-access)) |

**SpotiBye will not qualify for extended access.** Do not build UI that depends on restricted endpoints. They return 403 silently.

### Restricted (extended access only — do not use)

| Endpoint | What it gave us |
|---|---|
| `GET /audio-features` | danceability, energy, tempo, valence, key, etc. |
| `GET /audio-analysis` | beat/bar/section-level data |
| `GET /recommendations` | seed-based track recommendations |
| `GET /artists/{id}/related-artists` | related artist suggestions |

### Standard (available — build on these)

Everything below is unrestricted and should be reliable long-term.

---

## Data available from standard endpoints

### Already in track objects (no extra API calls)

Every item from `GET /playlists/{id}/items` includes:

| Field | What it enables |
|---|---|
| `track.duration_ms` | Total playlist duration — sum all tracks |
| `track.popularity` | 0–100 per track; average shows playlist "mainstream-ness" |
| `track.explicit` | Explicit count / percentage |
| `track.album.release_date` | Release era distribution by decade |
| `track.artists[].id` | IDs needed to fetch full artist objects |

### From full artist objects (individual calls — standard tier)

`GET /artists/{id}` returns a full artist object. De-duplicate artist IDs and use bounded concurrency; do not use the removed batch endpoint `GET /artists?ids=...`.
The inline `SpotifyArtist` type in track objects only has `id`, `name`, `external_urls`, `uri`.
The full artist object adds:

| Field | What it enables |
|---|---|
| `genres[]` | **Genre distribution** — aggregate across all artists in playlist |
| `popularity` | Artist-level score (less useful than track popularity for aggregation) |

`genres` is Spotify's own taxonomy: strings like `"electronic"`, `"techno"`, `"berlin techno"`, `"indie pop"`. Aggregating these across all artists in a playlist is the best available standard-tier source for genre data — and does not require ReccoBeats.

---

## What to show in the popup

Priority order:

| Feature | Data source | Effort |
|---|---|---|
| **Genre distribution** | Artist `genres[]` via individual fetches | Medium |
| **Total duration** | `track.duration_ms` sum | Trivial — already computed in `generatePlaylistInsights()` |
| **Release era** | `track.album.release_date` decade grouping | Trivial |
| **Avg popularity** | `track.popularity` mean | Trivial |
| **Explicit count** | `track.explicit` count | Trivial |

---

## Implementation plan — genre distribution

This is the highest-value addition. It does not depend on ReccoBeats, extended access, or any other in-flight work.

It does overlap with the ReccoBeats wiring plan ([plans/reccobeats-wiring.md](plans/reccobeats-wiring.md)): specifically, genre distribution should be part of the normalized KV result schema defined in Phase 2-A of that plan. The two can be done together or in sequence.

### Step 1 — Add `SpotifyArtistFull` type

**File:** [src/backend/types/spotify.ts](../src/backend/types/spotify.ts)

The existing `SpotifyArtist` interface (used inline in tracks) lacks `genres`. Add a full artist type:

```ts
export interface SpotifyArtistFull {
  id: string;
  name: string;
  genres: string[];
  popularity: number;
  external_urls: { spotify: string };
  uri: string;
}
```

### Step 2 — Add `getArtist()` / `getArtists()` to `SpotifyService`

**File:** [src/backend/services/spotify.ts](../src/backend/services/spotify.ts)

```ts
async getArtist(artistId: string): Promise<SpotifyArtistFull> {
  const response = await this.fetchWithRetry(`${this.baseUrl}/artists/${artistId}`);
  const rawData = await response.json();
  parseSpotifyResponse<Record<string, unknown>>(rawData, ['id', 'name']);
  return rawData as SpotifyArtistFull;
}

async getArtists(artistIds: string[]): Promise<SpotifyArtistFull[]> {
  const uniqueIds = [...new Set(artistIds.filter(Boolean))];
  return this.fetchWithConcurrency(uniqueIds, (id) => this.getArtist(id), 5);
}
```

### Step 3 — Add genre aggregation to `AnalysisService`

**File:** [src/backend/services/analysis.ts](../src/backend/services/analysis.ts)

Add a private helper:

```ts
private aggregateGenres(artists: SpotifyArtistFull[]): Record<string, { count: number; percentage: number }> {
  const raw: Record<string, number> = {};
  for (const artist of artists) {
    for (const genre of artist.genres) {
      raw[genre] = (raw[genre] ?? 0) + 1;
    }
  }
  const total = Object.values(raw).reduce((s, n) => s + n, 0);
  if (total === 0) return {};

  return Object.fromEntries(
    Object.entries(raw)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 15)
      .map(([genre, count]) => [genre, { count, percentage: Math.round((count / total) * 1000) / 10 }])
  );
}
```

Then in `generatePlaylistInsights()`, add an `artists` parameter and call it:

```ts
async generatePlaylistInsights(
  tracks: any[],
  artistData: SpotifyArtistFull[] = []
): Promise<any> {
  // ... existing code ...
  return {
    overview: { ... },
    artists: {
      unique_artists: Object.keys(artistCounts).length,
      top_artists: topArtists,
      diversity: totalTracks > 0 ? Object.keys(artistCounts).length / totalTracks : 0,
    },
    genre_distribution: this.aggregateGenres(artistData),
    insights: this.generateInsightsFromMetadata(tracks, genreDistribution)
  };
}
```

### Step 4 — Wire artist fetch into `analyzePlaylist()`

**File:** [src/backend/services/analysis.ts](../src/backend/services/analysis.ts)

After collecting all track items, extract unique artist IDs and fetch them:

```ts
// Collect unique artist IDs from all tracks
const artistIdSet = new Set<string>();
for (const item of allItems) {
  for (const artist of item.track.artists) {
    if (artist.id) artistIdSet.add(artist.id);
  }
}
let artistData: SpotifyArtistFull[] = [];
try {
  artistData = await spotifyService.getArtists([...artistIdSet]);
} catch {
  // Genre distribution is best-effort because Spotify artist genres are deprecated.
  artistData = [];
}

const spotifyInsights = await this.generatePlaylistInsights(
  allItems.map(item => item.track),
  artistData
);
```

This goes alongside the pagination fixes in the ReccoBeats wiring plan.

### Step 5 — Python popup already handles it

**File:** [src/frontend/ui/backend_playlist_card.py](../src/frontend/ui/backend_playlist_card.py)

`_update_analysis_ui()` already reads `results.get('genre_distribution', {})` and renders it. No Python changes needed as long as the KV result schema uses the key `genre_distribution` with the shape `{genre: {count, percentage}}`.

---

## February 2026 developer mode change

As of February 2026, Spotify's dev mode requires a **Premium account** and limits test users to 5 (down from 25). This affects local development but not production.

[Source: Spotify developer blog, 2026-02-06](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security)

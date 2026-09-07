/**
 * Canonical Spotify / ReccoBeats fixtures for backend tests.
 *
 * Replaces the near-identical inline `track()` / `spotifyTrack()` factories
 * that were copy-pasted across `analysis.test.ts`, `analysis-pipeline.test.ts`
 * and `openapi-schema.test.ts`, plus the `vi.fn()`-based ReccoBeats fetch
 * mocks duplicated between the latter two files.
 *
 * Design notes:
 * - Options objects (not positional parameters): the three inline factories
 *   each had a different positional signature, which is exactly why they
 *   diverged. Named options keep call sites self-documenting.
 * - Defaults mirror the pipeline/OpenAPI happy path (`durationMs: 200000`,
 *   `artistId: artist-<id>`). Analysis-style tests that assert on durations
 *   or ReccoBeats artist-href joins must pass explicit `artistId` /
 *   `durationMs` (all current call sites do).
 * - ReccoBeats payloads stay per-test: the `/v1/track` metadata arrays differ
 *   between callers in semantically meaningful ways (artist href join keys),
 *   so only the mock *structure* is shared. The audio-features arrays were
 *   byte-identical in both callers, so they share a default.
 * - No shared mutable state: every helper returns a fresh object / mock.
 */
import { vi } from 'vitest';
import { SpotifyService } from '../../services/spotify';
import type { SpotifyArtistFull, SpotifyTrack } from '../../types/spotify';

export interface SpotifyTrackFixtureOptions {
  id?: string;
  name?: string;
  artistId?: string;
  artistName?: string;
  durationMs?: number;
}

export const createSpotifyTrack = (options: SpotifyTrackFixtureOptions = {}): SpotifyTrack => {
  const {
    id = 'track1',
    artistId = `artist-${id}`,
    artistName = `Artist ${id}`,
    durationMs = 200000,
  } = options;
  return {
    id,
    name: options.name ?? `Track ${id}`,
    artists: [
      {
        id: artistId,
        name: artistName,
        external_urls: { spotify: `https://open.spotify.com/artist/${artistId}` },
        uri: `spotify:artist:${artistId}`,
      },
    ],
    album: {
      id: `album-${id}`,
      name: `Album ${id}`,
      artists: [],
      images: [],
      release_date: '2026-01-01',
      total_tracks: 1,
      external_urls: { spotify: `https://open.spotify.com/album/${id}` },
      uri: `spotify:album:${id}`,
    },
    duration_ms: durationMs,
    explicit: false,
    popularity: 50,
    external_urls: { spotify: `https://open.spotify.com/track/${id}` },
    uri: `spotify:track:${id}`,
    preview_url: null,
  };
};

export const createSpotifyArtist = (id: string, name: string): SpotifyArtistFull => ({
  id,
  name,
  genres: ['pop'],
  popularity: 60,
  external_urls: { spotify: `https://open.spotify.com/artist/${id}` },
  uri: `spotify:artist:${id}`,
});

/**
 * Stubs `SpotifyService` playlist-track and artist lookups for a fixed track
 * list. `total`/`rawCount` always equal `tracks.length` and every item uses
 * `added_by: null` (the only shape analysis tests need; pagination tests with
 * per-page totals mock the service directly).
 */
export const mockPlaylistTracks = (
  tracks: SpotifyTrack[],
  artists: SpotifyArtistFull[] | Error = [],
): void => {
  vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
    total: tracks.length,
    rawCount: tracks.length,
    items: tracks.map((track) => ({ added_by: null, track })),
  });
  const artistsSpy = vi.spyOn(SpotifyService.prototype, 'getArtists');
  if (artists instanceof Error) {
    artistsSpy.mockRejectedValue(artists);
  } else {
    artistsSpy.mockResolvedValue(artists);
  }
};

/** Track-metadata payload shared verbatim by the pipeline and OpenAPI tests. */
export const defaultReccoBeatsTrackMetadata = (): unknown[] => [
  {
    id: 'm1',
    href: 'https://open.spotify.com/track/track1',
    trackTitle: 'Track 1',
    artists: [{ id: 'a1', name: 'Artist 1', href: 'https://open.spotify.com/artist/artist1' }],
    durationMs: 200000,
    isrc: 'ISRC1',
    popularity: 55,
  },
  {
    id: 'm2',
    href: 'https://open.spotify.com/track/track2',
    trackTitle: 'Track 2',
    artists: [{ id: 'a2', name: 'Artist 2', href: 'https://open.spotify.com/artist/artist2' }],
    durationMs: 200000,
    popularity: 75,
  },
];

/** Audio-features payload shared verbatim by the pipeline and OpenAPI tests. */
export const defaultReccoBeatsAudioFeatures = (): unknown[] => [
  {
    id: 'r1',
    href: 'https://open.spotify.com/track/track1',
    acousticness: 0.1,
    danceability: 0.2,
    energy: 0.3,
    instrumentalness: 0.1,
    liveness: 0.1,
    loudness: -5,
    speechiness: 0.1,
    tempo: 100,
    valence: 0.4,
    key: 0,
    mode: 1,
    isrc: 'ISRC1',
  },
  {
    id: 'r2',
    href: 'https://open.spotify.com/track/track2',
    acousticness: 0.2,
    danceability: 0.3,
    energy: 0.4,
    instrumentalness: 0.2,
    liveness: 0.2,
    loudness: -6,
    speechiness: 0.2,
    tempo: 110,
    valence: 0.5,
    key: 0,
    mode: 1,
  },
];

export interface ReccoBeatsFetchFixture {
  /** Per-test `/v1/track` metadata content (join keys differ per caller). */
  trackMetadata: unknown[];
  /** Defaults to {@link defaultReccoBeatsAudioFeatures}. */
  audioFeatures?: unknown[];
}

export const createReccoBeatsFetchMock = (fixture: ReccoBeatsFetchFixture) => {
  const audioFeatures = fixture.audioFeatures ?? defaultReccoBeatsAudioFeatures();
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    const content = url.pathname === '/v1/track' ? fixture.trackMetadata : audioFeatures;
    return new Response(JSON.stringify({ content }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
};

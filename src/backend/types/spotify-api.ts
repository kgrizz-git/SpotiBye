/**
 * Spotify API response types and boundary validators.
 *
 * All raw Spotify API responses must be validated at boundaries before
 * internal use. Aligns with Golden Principle #1.
 */
import type { SpotifyPlaylist } from './spotify';
export interface SpotifyUserResponse {
  id: string;
  display_name: string | null;
  email: string;
  country: string;
  images: Array<{ url: string; height?: number | null; width?: number | null }>;
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
  scope: string;
}

export interface SpotifyPlaylistsResponse {
  href: string;
  items: Array<{
    id: string;
    name: string;
    description: string | null;
    public: boolean | null;
    collaborative: boolean;
    owner: { id: string; display_name?: string };
    tracks?: { href: string; total: number };
    images: Array<{ url: string }>;
    external_urls: { spotify: string };
    uri: string;
  }>;
  limit: number;
  next: string | null;
  offset: number;
  previous: string | null;
  total: number;
}

export interface SpotifyPlaylistResponse {
  id: string;
  name: string;
  description: string | null;
  public: boolean | null;
  collaborative: boolean;
  owner: { id: string; display_name?: string };
  tracks?: { href: string; total: number };
  items?: Array<{
    added_at?: string;
    added_by?: { id: string };
    is_local?: boolean;
    track?: SpotifyTrackResponse;
    album?: SpotifyAlbumResponse;
  }>;
  images: Array<{ url: string }>;
  external_urls: { spotify: string };
  uri: string;
}

export interface SpotifyTrackResponse {
  id: string;
  name: string;
  artists: Array<{ id: string; name: string }>;
  album: SpotifyAlbumResponse;
  duration_ms: number;
  explicit: boolean;
  popularity: number | null;
  external_urls: { spotify: string };
  uri: string;
  preview_url: string | null;
}

export interface SpotifyAlbumResponse {
  id: string;
  name: string;
  artists: Array<{ id: string; name: string }>;
  images: Array<{ url: string; height?: number | null; width?: number | null }>;
  release_date: string;
  total_tracks: number;
  external_urls: { spotify: string };
  uri: string;
}

export interface SpotifyArtistsResponse {
  artists: Array<{
    id: string;
    name: string;
    genres: string[];
    popularity: number;
    external_urls: { spotify: string };
    uri: string;
  }>;
}

export interface SpotifyAudioFeaturesResponse {
  audio_features: Array<SpotifyAudioFeaturesData | null>;
}

export interface SpotifyAudioFeaturesData {
  id: string;
  acousticness: number;
  danceability: number;
  energy: number;
  instrumentalness: number;
  liveness: number;
  loudness: number;
  speechiness: number;
  valence: number;
  tempo: number;
  mode: number;
  key: number;
  time_signature: number;
  track_href: string;
  analysis_url: string;
  type: string;
  uri: string;
}

/**
 * Boundary validator — parses and validates raw API responses at layer boundaries.
 * Aligns with Golden Principle #1: Parse data shapes at boundaries.
 */
export function parseSpotifyResponse<T>(
  data: unknown,
  expectedKeys: string[],
): asserts data is T {
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid Spotify response shape: expected object');
  }
  const record = data as Record<string, unknown>;
  for (const key of expectedKeys) {
    if (!(key in record)) {
      throw new Error(`Missing required field: ${key}`);
    }
  }
}

/**
 * Validate individual playlist items at the boundary. Spotify occasionally
 * returns a partial item (missing `id` or `name`) which would crash downstream
 * callers; rather than 500 the whole response we drop the bad item and log a
 * warning. Best-effort: never throws.
 */
export function parsePlaylistItems(
  items: unknown,
  context = 'playlists',
): SpotifyPlaylist[] {
  if (!Array.isArray(items)) {
    return [];
  }

  const valid: SpotifyPlaylist[] = [];
  items.forEach((item, index) => {
    if (
      item &&
      typeof item === 'object' &&
      typeof (item as Record<string, unknown>).id === 'string' &&
      typeof (item as Record<string, unknown>).name === 'string'
    ) {
      valid.push(item as SpotifyPlaylist);
    } else {
      console.warn(
        `parsePlaylistItems: dropping malformed item at ${context}[${index}]`,
      );
    }
  });
  return valid;
}

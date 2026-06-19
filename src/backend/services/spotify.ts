/**
 * Spotify API client — the ONLY place in the backend that calls api.spotify.com.
 *
 * Golden Principle #2: All Spotify API calls go through this file.
 * Do not call api.spotify.com from routes, middleware, or any other service.
 *
 * References:
 *   - docs/references/spotify-api-reference.md  — endpoints, pagination, rate limits
 *   - docs/february-2026-spotify-migration-findings.md — critical: /tracks → /items rename
 */
import type {
  SpotifyPlaylist,
  SpotifyTrack,
  SpotifyAudioFeatures,
  SpotifyPlaylistTrackItem,
  SpotifyArtistFull,
} from '../types/spotify';
import type {
  SpotifyPlaylistsResponse,
  SpotifyPlaylistResponse,
  SpotifyTrackResponse,
  SpotifyAudioFeaturesResponse,
} from '../types/spotify-api';
import { parseSpotifyResponse } from '../types/spotify-api';

export interface NormalizedPlaylistItemsResponse {
  href?: string;
  total: number;
  // Number of raw entries Spotify returned for this page, before filtering out
  // local/unavailable items. Pagination must advance by this, not items.length.
  rawCount: number;
  items: Array<SpotifyPlaylistTrackItem & { track: SpotifyTrack }>;
}

export class SpotifyService {
  private accessToken: string;
  private baseUrl = 'https://api.spotify.com/v1';

  constructor(accessToken: string) {
    this.accessToken = accessToken;
  }

  async getUserPlaylists(limit: number = 50, offset: number = 0): Promise<SpotifyPlaylist[]> {
    const url = new URL(`${this.baseUrl}/me/playlists`);
    url.searchParams.set('limit', limit.toString());
    url.searchParams.set('offset', offset.toString());

    const response = await this.fetchWithRetry(url.toString());
    const rawData = await response.json();
    parseSpotifyResponse<SpotifyPlaylistsResponse>(rawData, ['items', 'total']);

    return rawData.items as SpotifyPlaylist[];
  }

  async getPlaylist(playlistId: string): Promise<SpotifyPlaylist> {
    const response = await this.fetchWithRetry(`${this.baseUrl}/playlists/${playlistId}`);
    const rawData = await response.json();
    parseSpotifyResponse<SpotifyPlaylistResponse>(rawData, ['id', 'name', 'owner']);
    return rawData as SpotifyPlaylist;
  }

  async getPlaylistTracks(playlistId: string, limit: number = 50, offset: number = 0): Promise<NormalizedPlaylistItemsResponse> {
    const url = new URL(`${this.baseUrl}/playlists/${playlistId}/items`);
    url.searchParams.set('limit', limit.toString());
    url.searchParams.set('offset', offset.toString());

    const response = await this.fetchWithRetry(url.toString());
    const rawData = await response.json();
    parseSpotifyResponse<Record<string, unknown>>(rawData, ['items', 'total']);
    return this.normalizePlaylistItemsResponse(rawData);
  }

  private normalizePlaylistItemsResponse(data: any): NormalizedPlaylistItemsResponse {
    const rawItems = Array.isArray(data?.items) ? data.items : [];

    const items = rawItems
      .map((entry: any) => {
        const normalizedTrack = entry?.track ?? entry?.item;
        if (!normalizedTrack?.id) {
          return null;
        }

        return {
          ...entry,
          track: normalizedTrack,
        };
      })
      .filter((entry: any): entry is SpotifyPlaylistTrackItem & { track: SpotifyTrack } => Boolean(entry));

    return {
      href: data?.href,
      total: typeof data?.total === 'number' ? data.total : items.length,
      rawCount: rawItems.length,
      items,
    };
  }

  async getTrack(trackId: string): Promise<SpotifyTrack> {
    const response = await this.fetchWithRetry(`${this.baseUrl}/tracks/${trackId}`);
    const rawData = await response.json();
    parseSpotifyResponse<SpotifyTrackResponse>(rawData, ['id', 'name', 'artists', 'album']);
    return rawData as SpotifyTrack;
  }

  async getAudioFeatures(trackId: string): Promise<SpotifyAudioFeatures> {
    const response = await this.fetchWithRetry(`${this.baseUrl}/audio-features/${trackId}`);
    const rawData = await response.json();
    parseSpotifyResponse<Record<string, unknown>>(rawData, ['id']);
    return rawData as unknown as SpotifyAudioFeatures;
  }

  async getArtist(artistId: string): Promise<SpotifyArtistFull> {
    const response = await this.fetchWithRetry(`${this.baseUrl}/artists/${artistId}`);
    const rawData = await response.json();
    parseSpotifyResponse<Record<string, unknown>>(rawData, ['id', 'name']);
    return rawData as unknown as SpotifyArtistFull;
  }

  async getArtists(artistIds: string[]): Promise<SpotifyArtistFull[]> {
    const uniqueIds = [...new Set(artistIds.filter(Boolean))];
    return this.fetchWithConcurrency(uniqueIds, (id) => this.getArtist(id), 5);
  }

  async getMultipleAudioFeatures(trackIds: string[]): Promise<SpotifyAudioFeatures[]> {
    const url = new URL(`${this.baseUrl}/audio-features`);
    url.searchParams.set('ids', trackIds.join(','));

    const response = await this.fetchWithRetry(url.toString());
    const rawData = await response.json();
    parseSpotifyResponse<SpotifyAudioFeaturesResponse>(rawData, ['audio_features']);

    return rawData.audio_features as unknown as SpotifyAudioFeatures[];
  }

  private async fetchWithRetry(url: string, retries: number = 3): Promise<Response> {
    for (let i = 0; i < retries; i++) {
      try {
        const response = await fetch(url, {
          headers: {
            'Authorization': `Bearer ${this.accessToken}`
          }
        });

        if (response.status === 429) {
          // Rate limited - wait and retry
          const retryAfter = parseInt(response.headers.get('Retry-After') || '1');
          await this.sleep(retryAfter * 1000);
          continue;
        }

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return response;
      } catch (error) {
        if (i === retries - 1) throw error;

        // Exponential backoff
        const delay = Math.pow(2, i) * 1000;
        await this.sleep(delay);
      }
    }

    throw new Error('Max retries exceeded');
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private async fetchWithConcurrency<T>(
    items: string[],
    fetchFn: (item: string) => Promise<T>,
    concurrency: number = 5
  ): Promise<T[]> {
    const results: T[] = [];
    let nextIndex = 0;

    const workers = Array.from(
      { length: Math.min(concurrency, items.length) },
      async () => {
        while (nextIndex < items.length) {
          const currentIndex = nextIndex;
          nextIndex += 1;
          results[currentIndex] = await fetchFn(items[currentIndex]);
        }
      }
    );

    await Promise.all(workers);
    return results;
  }
}

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
  SpotifyPlaylistTrackItem,
  SpotifyArtistFull,
} from '../types/spotify';
import type {
  SpotifyPlaylistsResponse,
  SpotifyPlaylistResponse,
  SpotifyTrackResponse,
} from '../types/spotify-api';
import { parsePlaylistItems, parseSpotifyResponse } from '../types/spotify-api';

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

    return parsePlaylistItems(rawData.items, 'user-playlists');
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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- raw JSON response boundary; shape is partially validated by parseSpotifyResponse before this call
  private normalizePlaylistItemsResponse(data: any): NormalizedPlaylistItemsResponse {
    const rawItems = Array.isArray(data?.items) ? data.items : [];

    const items = rawItems
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- entries are raw API objects not yet narrowed to SpotifyPlaylistTrackItem
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- filter type guard asserts the narrowed shape; entry is raw API data
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


  async getArtist(artistId: string): Promise<SpotifyArtistFull> {
    const response = await this.fetchWithRetry(`${this.baseUrl}/artists/${artistId}`);
    const rawData = await response.json();
    parseSpotifyResponse<Record<string, unknown>>(rawData, ['id', 'name']);
    return asArtistFull(rawData);
  }

  async getArtists(artistIds: string[]): Promise<SpotifyArtistFull[]> {
    // Cloudflare Workers have a hard limit of 50 subrequests (fetches) per invocation.
    // Since the Spotify batch artists endpoint was removed, we must fetch individually.
    // To stay safely under the limit, we only fetch metadata for the top 40 unique artists.
    const uniqueIds = [...new Set(artistIds.filter(Boolean))].slice(0, 40);
    return this.fetchWithConcurrency(uniqueIds, (id) => this.getArtist(id), 5);
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
          // Rate limited - wait and retry. `Retry-After` is either an integer
          // (seconds) or an HTTP-date. NaN would cause a 0ms busy spin.
          const retryAfter = parseRetryAfter(
            response.headers.get('Retry-After')
          );
          await this.sleep(retryAfter * 1000);
          continue;
        }

        if (!response.ok) {
          // Read the body so diagnostic details (e.g. Spotify's JSON error
          // message) are not discarded. Non-429 errors are not retried
          // because (a) 4xx is deterministic and (b) consuming the body
          // would prevent reading it again on retry.
          const body = await response.text();
          throw new Error(`HTTP ${response.status}: ${body}`);
        }

        return response;
      } catch (error) {
        // Non-recoverable: 4xx response (or other non-429 failure) was
        // already thrown with a meaningful message — propagate immediately.
        if (error instanceof Error && error.message.startsWith('HTTP ')) {
          throw error;
        }

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

/**
 * Parse the `Retry-After` header value into a non-negative integer of
 * seconds to wait. Per RFC 9110, the header is either an integer
 * (delta-seconds) or an HTTP-date. Returns 1 second as a safe fallback
 * when the value is missing or unparseable.
 *
 * Exported for direct unit testing.
 */
export function parseRetryAfter(header: string | null | undefined): number {
  if (!header) {
    return 1;
  }

  const trimmed = header.trim();
  if (!trimmed) {
    return 1;
  }

  // Pure integer form (most common).
  if (/^\d+$/.test(trimmed)) {
    return Math.max(0, parseInt(trimmed, 10));
  }

  // HTTP-date form. `Date.parse` returns NaN for invalid input.
  const ms = Date.parse(trimmed);
  if (!Number.isNaN(ms)) {
    const seconds = Math.ceil((ms - Date.now()) / 1000);
    return Math.max(0, seconds);
  }

  return 1;
}

/**
 * Typed wrappers that replace `as unknown as T` casts at the boundary.
 * Each one does a minimal shape check; if the shape is wrong, the wrapper
 * throws instead of silently returning a malformed value.
 */
function asArtistFull(raw: unknown): SpotifyArtistFull {
  if (
    !raw ||
    typeof raw !== 'object' ||
    typeof (raw as { id?: unknown }).id !== 'string' ||
    typeof (raw as { name?: unknown }).name !== 'string'
  ) {
    throw new Error('Invalid artist shape: missing string id or name');
  }
  return raw as SpotifyArtistFull;
}

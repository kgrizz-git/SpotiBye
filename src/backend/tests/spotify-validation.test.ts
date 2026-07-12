import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { SpotifyService } from '../services/spotify';
import { parsePlaylistItems } from '../types/spotify-api';

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

describe('parsePlaylistItems', () => {
  it('drops items missing a string id and logs a warning', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const items = [
      { id: 'good', name: 'Valid' },
      { name: 'Missing id' },
      { id: 'missing-name' },
      null,
      { id: 'good2', name: 'Also valid' },
    ];

    const result = parsePlaylistItems(items, 'test');

    expect(result).toHaveLength(2);
    expect(result.map((p) => p.id)).toEqual(['good', 'good2']);
    expect(warn).toHaveBeenCalled();
  });

  it('returns an empty array when given a non-array', () => {
    const result = parsePlaylistItems(null, 'test');
    expect(result).toEqual([]);
  });

  it('returns an empty array when all items are malformed (does not throw)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const result = parsePlaylistItems([null, {}, { name: 'no id' }], 'test');
    expect(result).toEqual([]);
    expect(warn).toHaveBeenCalled();
  });

  it('returns the full array when all items are valid', () => {
    const items = [
      { id: '1', name: 'A' },
      { id: '2', name: 'B' },
    ];
    expect(parsePlaylistItems(items, 'test')).toHaveLength(2);
  });
});

describe('SpotifyService typed wrappers (BM-6)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('getArtist throws when the response is missing a string id or name', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ id: 'artist-1', name: 42 })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');

    await expect(service.getArtist('artist-1')).rejects.toThrow(
      /Invalid artist shape/
    );
  });

  it('getArtist returns the parsed object on a valid response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: 'artist-1',
        name: 'Artist',
        genres: ['pop'],
        popularity: 50,
        external_urls: { spotify: 'https://open.spotify.com/artist/artist-1' },
        uri: 'spotify:artist:artist-1',
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');
    const artist = await service.getArtist('artist-1');

    expect(artist.id).toBe('artist-1');
    expect(artist.name).toBe('Artist');
  });
});

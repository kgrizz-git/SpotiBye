import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SpotifyService } from '../services/spotify';

const artistResponse = (id: string) => ({
  id,
  name: `Artist ${id}`,
  genres: ['electronic'],
  popularity: 50,
  external_urls: { spotify: `https://open.spotify.com/artist/${id}` },
  uri: `spotify:artist:${id}`,
});

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

describe('SpotifyService artist metadata', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('fetches artists individually instead of using the removed batch endpoint', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));

      if (url.pathname === '/v1/artists') {
        return jsonResponse({
          artists: [artistResponse('artist1'), artistResponse('artist2')],
        });
      }

      return jsonResponse(artistResponse(url.pathname.split('/').at(-1) ?? 'unknown'));
    });
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');
    const artists = await service.getArtists(['artist1', 'artist2']);

    expect(artists.map((artist) => artist.id)).toEqual(['artist1', 'artist2']);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'https://api.spotify.com/v1/artists/artist1',
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://api.spotify.com/v1/artists/artist2',
      expect.any(Object)
    );
    expect(
      fetchMock.mock.calls.some(([input]) => String(input).includes('/artists?ids='))
    ).toBe(false);
  });

  it('deduplicates artist IDs before fetching individual artist metadata', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      return jsonResponse(artistResponse(url.pathname.split('/').at(-1) ?? 'unknown'));
    });
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');
    const artists = await service.getArtists(['artist1', 'artist1']);

    expect(artists.map((artist) => artist.id)).toEqual(['artist1']);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.spotify.com/v1/artists/artist1',
      expect.any(Object)
    );
  });

  it('preserves Retry-After handling for individual artist requests', async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response('', {
        status: 429,
        statusText: 'Too Many Requests',
        headers: { 'Retry-After': '1' },
      }))
      .mockResolvedValueOnce(jsonResponse(artistResponse('artist1')));
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');
    const artistsPromise = service.getArtists(['artist1']);

    await vi.advanceTimersByTimeAsync(1000);

    await expect(artistsPromise).resolves.toEqual([artistResponse('artist1')]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'https://api.spotify.com/v1/artists/artist1',
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://api.spotify.com/v1/artists/artist1',
      expect.any(Object)
    );
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SpotifyService, parseRetryAfter } from '../services/spotify';

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

describe('SpotifyService error response handling', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('preserves the response body in thrown errors for non-429 failures (BE-LOG-2)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { message: 'Invalid access token' } }), {
        status: 401,
        statusText: 'Unauthorized',
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');

    let caught: Error | undefined;
    try {
      await service.getArtists(['artist1']);
    } catch (err) {
      caught = err as Error;
    }
    expect(caught).toBeDefined();
    expect(caught!.message).toMatch(/^HTTP 401:/);
    expect(caught!.message).toMatch(/Invalid access token/);
  });
});

describe('parseRetryAfter', () => {
  it('parses an integer-seconds header', () => {
    expect(parseRetryAfter('120')).toBe(120);
    expect(parseRetryAfter('0')).toBe(0);
  });

  it('parses an integer-seconds header with whitespace', () => {
    expect(parseRetryAfter('  60  ')).toBe(60);
  });

  it('parses an HTTP-date header into a future-second delta', () => {
    const future = new Date(Date.now() + 5000);
    const result = parseRetryAfter(future.toUTCString());
    expect(result).toBeGreaterThanOrEqual(4);
    expect(result).toBeLessThanOrEqual(6);
  });

  it('clamps a past HTTP-date to zero seconds', () => {
    const past = new Date(Date.now() - 10_000);
    expect(parseRetryAfter(past.toUTCString())).toBe(0);
  });

  it('falls back to 1 second for a missing header', () => {
    expect(parseRetryAfter(null)).toBe(1);
    expect(parseRetryAfter(undefined)).toBe(1);
  });

  it('falls back to 1 second for an empty or whitespace header', () => {
    expect(parseRetryAfter('')).toBe(1);
    expect(parseRetryAfter('   ')).toBe(1);
  });

  it('falls back to 1 second for an unparseable header', () => {
    expect(parseRetryAfter('not-a-date')).toBe(1);
    expect(parseRetryAfter('abc123')).toBe(1);
  });
});

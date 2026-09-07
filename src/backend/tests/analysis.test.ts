import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { Hono } from 'hono';
import { analysisRoutes } from '../routes/analysis';
import { AnalysisService } from '../services/analysis';
import { SpotifyService } from '../services/spotify';
import { CacheService } from '../services/cache';
import { AnalysisStatusStore } from '../services/analysis-status-object';
import type { Env } from '../types/env';
import { kvNamespace } from './helpers/kv';
import { createSpotifyTrack } from './helpers/spotify';
import { buildAuthenticatedRequest, setupRouteContext } from './helpers/hono';

vi.mock('../middleware/auth', () => ({
  authMiddleware: vi.fn().mockImplementation((c, next) => {
    // Mock authenticated user
    c.set('user', {
      id: 'test-user-id',
      email: 'test@example.com',
      name: 'Test User',
      session_id: 'test-session-id'
    });
    c.set('session_id', 'test-session-id');
    c.set('access_token', 'test-access-token');
    return next();
  })
}));

describe('AnalysisService', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => (
      new Response(JSON.stringify({ content: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('completes playlist analysis without genre data when Spotify artist metadata fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 1,
      rawCount: 1,
      items: [
        {
          added_by: null,
          track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 180000 }),
        },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockRejectedValue(
      new Error('HTTP 403: Forbidden')
    );

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(result.status).toBe('completed');
    expect(result.overview).toMatchObject({
      total_tracks: 1,
      total_duration_ms: 180000,
      average_duration_ms: 180000,
      formatted_duration: '3m 0s',
    });
    expect(result.artists).toMatchObject({
      unique_artists: 1,
      diversity: 1,
      top_artists: [{ artist: 'Artist 1', count: 1 }],
    });
    expect(result.genre_distribution).toEqual({});
    expect(warnSpy).toHaveBeenCalledWith(
      'Failed to fetch Spotify artist metadata; continuing without genre insights',
      expect.objectContaining({
        playlistId: 'playlist1',
        artistCount: 1,
        error: 'HTTP 403: Forbidden',
      })
    );
  });

  it('keeps successful Spotify artist genres when one artist metadata lookup returns 404', async () => {
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 2,
      rawCount: 2,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 180000 }) },
        { added_by: null, track: createSpotifyTrack({ id: 'track2', artistId: 'artist404', artistName: 'Missing Artist', durationMs: 180000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockRejectedValue(
      new Error('HTTP 404: {"error":{"status":404,"message":"Resource not found"}}')
    );
    vi.spyOn(SpotifyService.prototype, 'getArtist')
      .mockResolvedValueOnce({
        id: 'artist1',
        name: 'Artist 1',
        genres: ['indie rock'],
        popularity: 50,
        external_urls: { spotify: 'https://open.spotify.com/artist/artist1' },
        uri: 'spotify:artist:artist1',
      })
      .mockRejectedValueOnce(new Error('HTTP 404: {"error":{"status":404,"message":"Resource not found"}}'));

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(result.status).toBe('completed');
    expect(result.genre_distribution).toEqual({
      'indie rock': { count: 1, percentage: 100 },
    });
    expect(result.errors).toEqual(
      expect.arrayContaining([
        {
          source: 'spotify:artists',
          message: 'Spotify artist metadata partially available: resolved 1 of 2 artists; 1 failed.',
        },
      ])
    );
  });

  it('records a ReccoBeats coverage warning when audio features are unavailable for every track', async () => {
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 2,
      rawCount: 2,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 180000 }) },
        { added_by: null, track: createSpotifyTrack({ id: 'track2', artistId: 'artist2', artistName: 'Artist 2', durationMs: 180000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect((result as any).audio_features).toBeUndefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([
        {
          source: 'reccobeats:coverage',
          message: 'Audio features available for 0 of 2 tracks.',
        },
      ])
    );
  });

  it('does not expose null or blank artist names in top artists', async () => {
    const trackWithInvalidArtists = createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 180000 });
    trackWithInvalidArtists.artists = [
      { id: 'artist1', name: 'Artist 1', external_urls: { spotify: 'https://open.spotify.com/artist/artist1' }, uri: 'spotify:artist:artist1' },
      { id: 'artist-null', name: null as unknown as string, external_urls: { spotify: 'https://open.spotify.com/artist/artist-null' }, uri: 'spotify:artist:artist-null' },
      { id: 'artist-blank', name: '   ', external_urls: { spotify: 'https://open.spotify.com/artist/artist-blank' }, uri: 'spotify:artist:artist-blank' },
    ];
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 1,
      rawCount: 1,
      items: [{ added_by: null, track: trackWithInvalidArtists }],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(result.artists?.top_artists).toEqual([{ artist: 'Artist 1', count: 1 }]);
    expect(result.artists?.unique_artists).toBe(1);
  });

  it('continues paginating by raw Spotify page count when normalized items are filtered out', async () => {
    const getPlaylistTracksSpy = vi
      .spyOn(SpotifyService.prototype, 'getPlaylistTracks')
      .mockResolvedValueOnce({
        total: 150,
        rawCount: 100,
        items: [
          {
            added_by: null,
            track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 120000 }),
          },
        ],
      })
      .mockResolvedValueOnce({
        total: 150,
        rawCount: 50,
        items: [
          {
            added_by: null,
            track: createSpotifyTrack({ id: 'track2', artistId: 'artist2', artistName: 'Artist 2', durationMs: 240000 }),
          },
        ],
      });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(getPlaylistTracksSpy).toHaveBeenCalledTimes(2);
    expect(getPlaylistTracksSpy).toHaveBeenNthCalledWith(1, 'playlist1', 100, 0);
    expect(getPlaylistTracksSpy).toHaveBeenNthCalledWith(2, 'playlist1', 100, 100);
    expect(result.overview?.total_tracks).toBe(2);
    expect(result.overview?.total_duration_ms).toBe(360000);
    expect(result.artists?.unique_artists).toBe(2);
  });

  it('adds averaged ReccoBeats audio features when lookup succeeds', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      expect(url.origin).toBe('https://api.reccobeats.com');
      expect(url.searchParams.getAll('ids')).toEqual(['track1', 'track2']);

      if (url.pathname === '/v1/track') {
        return new Response(JSON.stringify({ content: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      expect(url.pathname).toBe('/v1/audio-features');
      return new Response(JSON.stringify({
        content: [
          {
            id: 'recco-1',
            href: 'https://open.spotify.com/track/track1',
            acousticness: 0.2,
            danceability: 0.4,
            energy: 0.6,
            instrumentalness: 0,
            liveness: 0.1,
            loudness: -8,
            speechiness: 0.03,
            tempo: 100,
            valence: 0.5,
          },
          {
            id: 'recco-2',
            href: 'https://open.spotify.com/track/track2',
            acousticness: 0.4,
            danceability: 0.8,
            energy: 0.2,
            instrumentalness: 0.2,
            liveness: 0.3,
            loudness: -4,
            speechiness: 0.07,
            tempo: 120,
            valence: 0.7,
          },
        ],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 2,
      rawCount: 2,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 120000 }) },
        { added_by: null, track: createSpotifyTrack({ id: 'track2', artistId: 'artist2', artistName: 'Artist 2', durationMs: 240000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect((result as any).audio_features).toEqual({
      track_count: 2,
      averages: {
        acousticness: 0.3,
        danceability: 0.6,
        energy: 0.4,
        instrumentalness: 0.1,
        liveness: 0.2,
        loudness: -6,
        speechiness: 0.05,
        tempo: 110,
        valence: 0.6,
      },
    });
  });

  it('keeps Spotify analysis results when ReccoBeats audio features fail', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.stubGlobal('fetch', vi.fn(async () => (
      new Response('temporarily unavailable', {
        status: 503,
        statusText: 'Service Unavailable',
      })
    )));
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 1,
      rawCount: 1,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 180000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(result.status).toBe('completed');
    expect(result.overview?.total_tracks).toBe(1);
    expect(result.artists?.unique_artists).toBe(1);
    expect((result as any).audio_features).toBeUndefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ source: 'reccobeats:audio-features' }),
      ])
    );
    expect(result.errors).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ source: 'reccobeats:coverage' }),
      ])
    );
    expect(warnSpy).toHaveBeenCalledWith(
      'Failed to fetch ReccoBeats audio features; continuing with Spotify-only analysis',
      expect.objectContaining({
        playlistId: 'playlist1',
        trackCount: 1,
        error: 'ReccoBeats API error: HTTP 503: Service Unavailable',
      })
    );
  });

  it('logs a body preview when ReccoBeats returns invalid JSON', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.stubGlobal('fetch', vi.fn(async () => (
      new Response('<html>blocked</html>', {
        status: 200,
        headers: { 'Content-Type': 'text/html' },
      })
    )));
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 1,
      rawCount: 1,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 180000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(result.status).toBe('completed');
    expect(result.errors).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: 'reccobeats:audio-features',
          message: 'Invalid ReccoBeats audio-features response JSON',
        }),
        expect.objectContaining({
          source: 'reccobeats:track-metadata',
          message: 'Invalid ReccoBeats track response JSON',
        }),
      ])
    );
    expect(warnSpy).toHaveBeenCalledWith(
      'Invalid ReccoBeats JSON response',
      expect.objectContaining({
        endpoint: 'audio-features',
        status: 200,
        batchSize: 1,
        bodyPreview: '<html>blocked</html>',
      })
    );
    expect(warnSpy).toHaveBeenCalledWith(
      'Invalid ReccoBeats JSON response',
      expect.objectContaining({
        endpoint: 'track',
        status: 200,
        batchSize: 1,
        bodyPreview: '<html>blocked</html>',
      })
    );
  });

  it('logs a body preview when ReccoBeats JSON has an invalid response shape', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    vi.stubGlobal('fetch', vi.fn(async () => (
      new Response(JSON.stringify({ error: 'blocked' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    )));
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 1,
      rawCount: 1,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 180000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(result.status).toBe('completed');
    expect(result.errors).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: 'reccobeats:audio-features',
          message: 'Invalid ReccoBeats audio features response shape',
        }),
        expect.objectContaining({
          source: 'reccobeats:track-metadata',
          message: 'Invalid ReccoBeats track metadata response shape',
        }),
      ])
    );
    expect(warnSpy).toHaveBeenCalledWith(
      'Invalid ReccoBeats audio features response shape',
      expect.objectContaining({
        endpoint: 'audio-features',
        status: 200,
        batchSize: 1,
        bodyPreview: '{"error":"blocked"}',
      })
    );
    expect(warnSpy).toHaveBeenCalledWith(
      'Invalid ReccoBeats track metadata response shape',
      expect.objectContaining({
        endpoint: 'track',
        status: 200,
        batchSize: 1,
        bodyPreview: '{"error":"blocked"}',
      })
    );
  });

  it('chunks track IDs into batches of 30 and aggregates correct averages across batches', async () => {
    const tracksList = Array.from({ length: 75 }, (_, i) => ({
      added_by: null,
      track: createSpotifyTrack({ id: `track${i + 1}`, artistId: `artist${i + 1}`, artistName: `Artist ${i + 1}`, durationMs: 120000 }),
    }));

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      expect(url.origin).toBe('https://api.reccobeats.com');
      const ids = url.searchParams.getAll('ids');
      expect(ids.length).toBeLessThanOrEqual(30);

      if (url.pathname === '/v1/track') {
        return new Response(JSON.stringify({ content: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      expect(url.pathname).toBe('/v1/audio-features');
      const content = ids.map((id) => ({
        id: `recco-${id}`,
        href: `https://open.spotify.com/track/${id}`,
        acousticness: 0.2,
        danceability: 0.4,
        energy: 0.6,
        instrumentalness: 0.1,
        liveness: 0.1,
        loudness: -6,
        speechiness: 0.05,
        tempo: 100,
        valence: 0.5,
      }));

      return new Response(JSON.stringify({ content }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 75,
      rawCount: 75,
      items: tracksList,
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    const audioFeatureCalls = fetchMock.mock.calls.filter(
      ([input]) => new URL(String(input)).pathname === '/v1/audio-features'
    );
    expect(audioFeatureCalls).toHaveLength(3);

    const firstBatchCallUrl = new URL(String(audioFeatureCalls[0][0]));
    expect(firstBatchCallUrl.searchParams.getAll('ids').length).toBe(30);

    const secondBatchCallUrl = new URL(String(audioFeatureCalls[1][0]));
    expect(secondBatchCallUrl.searchParams.getAll('ids').length).toBe(30);

    const thirdBatchCallUrl = new URL(String(audioFeatureCalls[2][0]));
    expect(thirdBatchCallUrl.searchParams.getAll('ids').length).toBe(15);

    const trackMetadataCalls = fetchMock.mock.calls.filter(
      ([input]) => new URL(String(input)).pathname === '/v1/track'
    );
    expect(trackMetadataCalls).toHaveLength(3);
    expect(
      trackMetadataCalls.map(([input]) => new URL(String(input)).searchParams.getAll('ids').length)
    ).toEqual([30, 30, 15]);

    expect((result as any).audio_features).toEqual({
      track_count: 75,
      averages: {
        acousticness: 0.2,
        danceability: 0.4,
        energy: 0.6,
        instrumentalness: 0.1,
        liveness: 0.1,
        loudness: -6,
        speechiness: 0.05,
        tempo: 100,
        valence: 0.5,
      },
    });
  });

  it('emits multiple monotonic progress updates during multi-group ReccoBeats enrichment', async () => {
    const tracksList = Array.from({ length: 120 }, (_, i) => ({
      added_by: null,
      track: createSpotifyTrack({ id: `track${i + 1}`, artistId: `artist${i + 1}`, artistName: `Artist ${i + 1}`, durationMs: 120000 }),
    }));

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      const ids = url.searchParams.getAll('ids');

      if (url.pathname === '/v1/track') {
        return new Response(JSON.stringify({
          content: ids.map((id) => ({
            id: `metadata-${id}`,
            href: `https://open.spotify.com/track/${id}`, trackTitle: `Track ${id}`,
            artists: [],
            durationMs: 120000,
            popularity: 50,
          })),
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

      expect(url.pathname).toBe('/v1/audio-features');
      return new Response(JSON.stringify({
        content: ids.map((id) => ({
          id: `recco-${id}`,
          href: `https://open.spotify.com/track/${id}`,
          acousticness: 0.2,
          danceability: 0.4,
          energy: 0.6,
          instrumentalness: 0.1,
          liveness: 0.1,
          loudness: -6,
          speechiness: 0.05,
          tempo: 100,
          valence: 0.5,
        })),
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });

    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: tracksList.length,
      rawCount: tracksList.length,
      items: tracksList,
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const progressValues: number[] = [];
    const service = new AnalysisService('access-token');
    await service.analyzePlaylist('playlist1', 'user1', 'job1', async (progress) => {
      progressValues.push(progress);
    });

    expect(progressValues).toEqual([...progressValues].sort((a, b) => a - b));
    expect(progressValues).toEqual(expect.arrayContaining([65, 85, 95]));

    const enrichmentProgressValues = progressValues.filter(
      (progress) => progress > 65 && progress < 85
    );
    expect(enrichmentProgressValues.length).toBeGreaterThanOrEqual(2);
  });

  it('aggregates key/mode distribution when at least 2 tracks have valid key and mode', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/v1/track') {
        return new Response(JSON.stringify({ content: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      const feature = (id: string, key?: number, mode?: number) => ({
        id: `recco-${id}`,
        href: `https://open.spotify.com/track/${id}`,
        acousticness: 0.1, danceability: 0.1, energy: 0.1, instrumentalness: 0.1,
        liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.1,
        ...(key !== undefined ? { key } : {}),
        ...(mode !== undefined ? { mode } : {}),
      });
      return new Response(JSON.stringify({
        content: [
          feature('track1', 0, 1),
          feature('track2', 0, 1),
          feature('track3'),
        ],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 3,
      rawCount: 3,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 120000 }) },
        { added_by: null, track: createSpotifyTrack({ id: 'track2', artistId: 'artist2', artistName: 'Artist 2', durationMs: 120000 }) },
        { added_by: null, track: createSpotifyTrack({ id: 'track3', artistId: 'artist3', artistName: 'Artist 3', durationMs: 120000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect((result as any).audio_features.key_mode_distribution).toEqual({
      key_percentages: { C: 100 },
      dominant_key: 'C',
      dominant_key_percentage: 100,
      mode_percentages: { major: 100, minor: 0 },
      dominant_mode: 'major',
    });
  });

  it('omits key_mode_distribution when fewer than 2 tracks have a valid key/mode pair', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/v1/track') {
        return new Response(JSON.stringify({ content: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(JSON.stringify({
        content: [
          {
            id: 'recco-1', href: 'https://open.spotify.com/track/track1',
            acousticness: 0.1, danceability: 0.1, energy: 0.1, instrumentalness: 0.1,
            liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.1,
            key: 0, mode: 1,
          },
          {
            id: 'recco-2', href: 'https://open.spotify.com/track/track2',
            acousticness: 0.1, danceability: 0.1, energy: 0.1, instrumentalness: 0.1,
            liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.1,
          },
        ],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 2,
      rawCount: 2,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 120000 }) },
        { added_by: null, track: createSpotifyTrack({ id: 'track2', artistId: 'artist2', artistName: 'Artist 2', durationMs: 120000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect((result as any).audio_features.key_mode_distribution).toBeUndefined();
  });

  it('aggregates ReccoBeats track metadata into reccobeats_metadata (ISRC count, popularity range)', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/v1/track') {
        return new Response(JSON.stringify({
          content: [
            {
              id: 'm1', href: 'https://open.spotify.com/track/track1', trackTitle: 'Track 1',
              artists: [{ id: 'a1', name: 'Artist 1', href: 'https://open.spotify.com/artist/a1' }],
              durationMs: 120000, isrc: 'ISRC1', popularity: 40,
            },
            {
              id: 'm2', href: 'https://open.spotify.com/track/track2', trackTitle: 'Track 2',
              artists: [{ id: 'a2', name: 'Artist 2', href: 'https://open.spotify.com/artist/a2' }],
              durationMs: 120000, popularity: 80,
            },
          ],
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
      return new Response(JSON.stringify({
        content: [
          {
            id: 'r1', href: 'https://open.spotify.com/track/track1',
            acousticness: 0.1, danceability: 0.1, energy: 0.1, instrumentalness: 0.1,
            liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.1,
            isrc: 'ISRC1',
          },
          {
            id: 'r2', href: 'https://open.spotify.com/track/track2',
            acousticness: 0.1, danceability: 0.1, energy: 0.1, instrumentalness: 0.1,
            liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.1,
            isrc: null,
          },
        ],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 2,
      rawCount: 2,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 120000 }) },
        { added_by: null, track: createSpotifyTrack({ id: 'track2', artistId: 'artist2', artistName: 'Artist 2', durationMs: 120000 }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect((result as any).reccobeats_metadata).toMatchObject({
      isrc_available: 1,
      popularity_min: 40,
      popularity_max: 80,
    });
    expect((result as any).reccobeats_metadata.retrieved_at).toEqual(expect.any(String));
  });

  it('records a partial error when ReccoBeats track metadata fails but audio features succeed', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/v1/track') {
        return new Response('boom', { status: 500, statusText: 'Internal Server Error' });
      }
      return new Response(JSON.stringify({
        content: [
          {
            id: 'r1', href: 'https://open.spotify.com/track/track1',
            acousticness: 0.1, danceability: 0.1, energy: 0.1, instrumentalness: 0.1,
            liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.1,
          },
        ],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 1,
      rawCount: 1,
      items: [{ added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 120000 }) }],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect((result as any).audio_features).toBeDefined();
    expect(result.errors).toEqual(
      expect.arrayContaining([expect.objectContaining({ source: 'reccobeats:track-metadata' })])
    );
    expect(result.schema_version).toBe('1.1');
    expect(warnSpy).toHaveBeenCalledWith(
      'Failed to fetch ReccoBeats track metadata; continuing without metadata aggregates',
      expect.objectContaining({ playlistId: 'playlist1' })
    );
  });

  it('serves ReccoBeats enrichment from the global per-track cache without fetching', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 1,
      rawCount: 1,
      items: [{ added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 120000 }) }],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const cacheKv = kvNamespace({
      'global:reccobeats:audio-features:track1': {
        id: 'r1', href: 'https://open.spotify.com/track/track1',
        acousticness: 0.1, danceability: 0.1, energy: 0.1, instrumentalness: 0.1,
        liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.1,
        isrc: 'ISRC1',
      },
      'global:reccobeats:track-metadata:track1': {
        id: 'm1',
        href: 'https://open.spotify.com/track/track1',
        trackTitle: 'Track 1',
        artists: [{ id: 'a1', name: 'Artist 1', href: 'https://open.spotify.com/artist/a1' }],
        durationMs: 120000, isrc: 'ISRC1', popularity: 50,
      },
    });
    const cache = new CacheService(cacheKv);

    const service = new AnalysisService('access-token', cache);
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(fetchMock).not.toHaveBeenCalled();
    expect((result as any).audio_features.track_count).toBe(1);
    expect((result as any).reccobeats_metadata.isrc_available).toBe(1);
    expect(result.unique_track_count).toBe(1);
    expect(result.audio_features_resolved_count).toBe(1);
    expect(result.track_metadata_resolved_count).toBe(1);
    expect(result.enrichment_resolved_track_count).toBe(1);
  });

  it('writes fetched ReccoBeats enrichment to the global per-track cache', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/v1/track') {
        return new Response(JSON.stringify({ content: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(JSON.stringify({
        content: [
          {
            id: 'r1', href: 'https://open.spotify.com/track/track1',
            acousticness: 0.1, danceability: 0.1, energy: 0.1, instrumentalness: 0.1,
            liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.1,
          },
        ],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 1,
      rawCount: 1,
      items: [{ added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1', durationMs: 120000 }) }],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const cacheKv = kvNamespace();
    const cache = new CacheService(cacheKv);

    const service = new AnalysisService('access-token', cache);
    await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(cacheKv.put).toHaveBeenCalledWith(
      'global:reccobeats:audio-features:track1',
      expect.stringContaining('"href":"https://open.spotify.com/track/track1"'),
      { expirationTtl: 15_552_000 }
    );
    expect(cacheKv.put).toHaveBeenCalledWith(
      'global:reccobeats:absent:track-metadata:track1',
      expect.stringContaining('"absent":true'),
      { expirationTtl: 604_800 }
    );
  });
});

describe('Analysis Routes', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;
  let statusStore: AnalysisStatusStore;

  beforeEach(() => {
    ({ app, env: mockEnv } = setupRouteContext('/analysis', analysisRoutes));
    statusStore = new AnalysisStatusStore(mockEnv.ANALYSIS_STATUS);
  });

  describe('POST /analysis/playlist/:id', () => {
    it('should start playlist analysis', async () => {
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'POST',
      });

      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'test-job-id',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'queued',
        progress: 0,
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status', 'queued');
    });

    it('writes queued status and enqueues the analysis job without running analysis inline', async () => {
      const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist');
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'POST',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toMatchObject({
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'queued',
        progress: 0,
      });
      await expect(statusStore.getStatus('test-user-id', 'playlist1')).resolves.toMatchObject({
        job_id: data.data.job_id,
        status: 'queued',
        progress: 0,
      });
      expect(mockEnv.ANALYSIS_QUEUE.send).toHaveBeenCalledWith(expect.objectContaining({
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        session_id: 'test-session-id',
        attempt: 0,
      }));
      expect(analyzeSpy).not.toHaveBeenCalled();
    });

    it('returns existing queued status without enqueuing a duplicate job', async () => {
      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'job-existing',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'queued',
        queued_at: '2026-06-19T00:00:00.000Z',
        progress: 0,
      });
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'POST',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toMatchObject({
        job_id: 'job-existing',
        status: 'queued',
      });
      expect(mockEnv.ANALYSIS_QUEUE.send).not.toHaveBeenCalled();
    });

    it('re-enqueues a fresh job when completed status has no matching results (stale)', async () => {
      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'job-old',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        progress: 100,
      });
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(null);
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'POST',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data.status).toBe('queued');
      expect(data.data.job_id).not.toBe('job-old');
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith('analysis:playlist1:test-user-id:results');
      expect(mockEnv.ANALYSIS_QUEUE.send).toHaveBeenCalled();
    });

    it('re-enqueues a fresh job when completed results are missing schema_version (stale)', async () => {
      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'job-old',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        progress: 100,
      });
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
          job_id: 'job-old',
          playlist_id: 'playlist1',
          user_id: 'test-user-id',
          status: 'completed',
          computed_at: '2026-01-01T00:00:00.000Z',
          completed_at: '2026-01-01T00:00:01.000Z',
          overview: { total_tracks: 0, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
          artists: { unique_artists: 0, top_artists: [], diversity: 0 },
          genre_distribution: {},
          insights: [],
          errors: [],
        }));
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'POST',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data.status).toBe('queued');
      expect(mockEnv.ANALYSIS_QUEUE.send).toHaveBeenCalled();
    });

    it('re-enqueues when completed results have incomplete enrichment coverage', async () => {
      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'job-old',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        progress: 100,
      });
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'job-old',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        computed_at: '2026-01-01T00:00:00.000Z',
        completed_at: '2026-01-01T00:00:01.000Z',
        overview: { total_tracks: 2, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
        artists: { unique_artists: 0, top_artists: [], diversity: 0 },
        genre_distribution: {},
        insights: [],
        errors: [],
        schema_version: '1.1',
        unique_track_count: 2,
        audio_features_resolved_count: 1,
        track_metadata_resolved_count: 2,
        enrichment_resolved_track_count: 1,
      }));
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'POST',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data.status).toBe('queued');
      expect(data.data.job_id).not.toBe('job-old');
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith('analysis:playlist1:test-user-id:results');
      expect(mockEnv.ANALYSIS_QUEUE.send).toHaveBeenCalled();
    });

    it('returns existing completed status when enrichment coverage is complete', async () => {
      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'job-complete',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        progress: 100,
      });
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'job-complete',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        computed_at: '2026-01-01T00:00:00.000Z',
        completed_at: '2026-01-01T00:00:01.000Z',
        overview: { total_tracks: 2, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
        artists: { unique_artists: 0, top_artists: [], diversity: 0 },
        genre_distribution: {},
        insights: [],
        errors: [],
        schema_version: '1.1',
        unique_track_count: 2,
        audio_features_resolved_count: 2,
        track_metadata_resolved_count: 2,
        enrichment_resolved_track_count: 2,
      }));
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'POST',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toMatchObject({ job_id: 'job-complete', status: 'completed' });
      expect(mockEnv.ANALYSIS_QUEUE.send).not.toHaveBeenCalled();
    });

    it('force_enrichment bypasses completed status and enqueues with flag', async () => {
      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'job-complete',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        progress: 100,
      });
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'job-complete',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        computed_at: '2026-01-01T00:00:00.000Z',
        completed_at: '2026-01-01T00:00:01.000Z',
        overview: { total_tracks: 2, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
        artists: { unique_artists: 0, top_artists: [], diversity: 0 },
        genre_distribution: {},
        insights: [],
        errors: [],
        schema_version: '1.1',
        unique_track_count: 2,
        audio_features_resolved_count: 2,
        track_metadata_resolved_count: 2,
        enrichment_resolved_track_count: 2,
      }));
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'POST',
        body: JSON.stringify({ force_enrichment: true }),
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data.status).toBe('queued');
      expect(data.data.job_id).not.toBe('job-complete');
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith('analysis:playlist1:test-user-id:results');
      expect(mockEnv.ANALYSIS_QUEUE.send).toHaveBeenCalledWith(
        expect.objectContaining({ force_enrichment: true }),
      );
    });

    it('force_enrichment bypasses queued status without duplicate short-circuit', async () => {
      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'job-existing',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'queued',
        queued_at: '2026-06-19T00:00:00.000Z',
        progress: 0,
      });
      const request = buildAuthenticatedRequest(
        '/analysis/playlist/playlist1?force_enrichment=true',
        { method: 'POST' },
      );

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data.status).toBe('queued');
      expect(data.data.job_id).not.toBe('job-existing');
      expect(mockEnv.ANALYSIS_QUEUE.send).toHaveBeenCalledWith(
        expect.objectContaining({ force_enrichment: true }),
      );
    });

    it('should return 400 for invalid playlist ID', async () => {
      const request = buildAuthenticatedRequest('/analysis/playlist/', {
        method: 'POST',
      });

      const response = await app.request(request, undefined, mockEnv);
      expect(response.status).toBe(404);
    });
  });

  describe('GET /analysis/playlist/:id/status', () => {
    it('should return analysis status', async () => {
      await statusStore.writeStatus('test-user-id', 'playlist1', {
        job_id: 'test-job-id',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        progress: 100,
      });

      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1/status', {
        method: 'GET',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status', 'completed');
      expect(data.data).toHaveProperty('progress');
    });

    it('should return 404 for non-existent analysis job', async () => {
      const request = buildAuthenticatedRequest('/analysis/playlist/nonexistent/status', {
        method: 'GET',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'ANALYSIS_NOT_FOUND');
    });
  });

  describe('GET /analysis/playlist/:id/results', () => {
    it('should return analysis results', async () => {
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1/results', {
        method: 'GET',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'ANALYSIS_RESULTS_NOT_FOUND');
    });

    it('should return results when cached', async () => {
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'test-job-id',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        computed_at: '2026-06-19T00:00:00.000Z',
        completed_at: '2026-06-19T00:00:01.000Z',
        overview: {
          total_tracks: 2,
          total_duration_ms: 360000,
          average_duration_ms: 180000,
          formatted_duration: '6m 0s',
        },
        artists: {
          unique_artists: 2,
          diversity: 1,
          top_artists: [{ artist: 'Artist 1', count: 1 }],
        },
        genre_distribution: {},
        audio_features: {
          track_count: 2,
          averages: {
            acousticness: 0.3,
            danceability: 0.6,
            energy: 0.4,
            instrumentalness: 0.1,
            liveness: 0.2,
            loudness: -6,
            speechiness: 0.05,
            tempo: 110,
            valence: 0.6,
          },
        },
        insights: [],
        unique_track_count: 2,
        audio_features_resolved_count: 2,
        track_metadata_resolved_count: 2,
        enrichment_resolved_track_count: 2,
        errors: [],
        schema_version: '1.1',
      }));

      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1/results', {
        method: 'GET',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('status', 'completed');
      expect(data.data).toHaveProperty('overview.formatted_duration', '6m 0s');
      expect(data.data).toHaveProperty('artists.unique_artists', 2);
      expect(data.data).toHaveProperty('genre_distribution');
      expect(data.data).toHaveProperty('audio_features.averages.energy', 0.4);
      expect(data.data).not.toHaveProperty('results');
    });

    it('deletes both KV keys and returns 404 when cached results are missing schema_version (stale)', async () => {
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'test-job-id',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        computed_at: '2026-01-01T00:00:00.000Z',
        completed_at: '2026-01-01T00:00:01.000Z',
        overview: { total_tracks: 0, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
        artists: { unique_artists: 0, top_artists: [], diversity: 0 },
        genre_distribution: {},
        insights: [],
        errors: [],
      }));

      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1/results', {
        method: 'GET',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'ANALYSIS_RESULTS_NOT_FOUND');
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith('analysis:playlist1:test-user-id:results');
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith('analysis:playlist1:test-user-id:status');
    });

    it('deletes both KV keys and returns 404 when cached results use schema_version 1.0 (stale after 1.1 bump)', async () => {
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'test-job-id',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'completed',
        computed_at: '2026-01-01T00:00:00.000Z',
        completed_at: '2026-01-01T00:00:01.000Z',
        overview: { total_tracks: 0, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
        artists: { unique_artists: 0, top_artists: [], diversity: 0 },
        genre_distribution: {},
        insights: [],
        errors: [],
        schema_version: '1.0',
      }));

      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1/results', {
        method: 'GET',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'ANALYSIS_RESULTS_NOT_FOUND');
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith('analysis:playlist1:test-user-id:results');
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith('analysis:playlist1:test-user-id:status');
    });
  });

  describe('DELETE /analysis/playlist/:id', () => {
    it('deletes user analysis results and legacy raw-enrichment key, not global per-track keys', async () => {
      const request = buildAuthenticatedRequest('/analysis/playlist/playlist1', {
        method: 'DELETE',
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toEqual({ message: 'Analysis deleted successfully' });
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith(
        'analysis:playlist1:test-user-id:results',
      );
      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith(
        'analysis:playlist:playlist1:raw-enrichment',
      );
    });
  });
});

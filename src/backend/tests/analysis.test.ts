import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { Hono } from 'hono';
import { analysisRoutes } from '../routes/analysis';
import { AnalysisService } from '../services/analysis';
import { SpotifyService } from '../services/spotify';
import type { Env } from '../types/env';
import type { SpotifyTrack } from '../types/spotify';
import { createTestEnv } from './helpers/env';

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

const spotifyTrack = (
  id: string,
  artistId: string,
  artistName: string,
  durationMs: number
): SpotifyTrack => ({
  id,
  name: `Track ${id}`,
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
});

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
          track: spotifyTrack('track1', 'artist1', 'Artist 1', 180000),
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

  it('continues paginating by raw Spotify page count when normalized items are filtered out', async () => {
    const getPlaylistTracksSpy = vi
      .spyOn(SpotifyService.prototype, 'getPlaylistTracks')
      .mockResolvedValueOnce({
        total: 150,
        rawCount: 100,
        items: [
          {
            added_by: null,
            track: spotifyTrack('track1', 'artist1', 'Artist 1', 120000),
          },
        ],
      })
      .mockResolvedValueOnce({
        total: 150,
        rawCount: 50,
        items: [
          {
            added_by: null,
            track: spotifyTrack('track2', 'artist2', 'Artist 2', 240000),
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
      expect(url.pathname).toBe('/v1/audio-features');
      expect(url.searchParams.getAll('ids')).toEqual(['track1', 'track2']);

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
        { added_by: null, track: spotifyTrack('track1', 'artist1', 'Artist 1', 120000) },
        { added_by: null, track: spotifyTrack('track2', 'artist2', 'Artist 2', 240000) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(fetchMock).toHaveBeenCalledTimes(1);
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
        { added_by: null, track: spotifyTrack('track1', 'artist1', 'Artist 1', 180000) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(result.status).toBe('completed');
    expect(result.overview?.total_tracks).toBe(1);
    expect(result.artists?.unique_artists).toBe(1);
    expect((result as any).audio_features).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledWith(
      'Failed to fetch ReccoBeats audio features; continuing with Spotify-only analysis',
      expect.objectContaining({
        playlistId: 'playlist1',
        trackCount: 1,
        error: 'ReccoBeats API error: HTTP 503: Service Unavailable',
      })
    );
  });

  it('chunks track IDs into batches of 50 and aggregates correct averages across batches', async () => {
    const tracksList = Array.from({ length: 60 }, (_, i) => ({
      added_by: null,
      track: spotifyTrack(`track${i + 1}`, `artist${i + 1}`, `Artist ${i + 1}`, 120000),
    }));

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      expect(url.origin).toBe('https://api.reccobeats.com');
      expect(url.pathname).toBe('/v1/audio-features');
      const ids = url.searchParams.getAll('ids');
      expect(ids.length).toBeLessThanOrEqual(50);

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
      total: 60,
      rawCount: 60,
      items: tracksList,
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const service = new AnalysisService('access-token');
    const result = await service.analyzePlaylist('playlist1', 'user1', 'job1');

    expect(fetchMock).toHaveBeenCalledTimes(2);

    const firstBatchCallUrl = new URL(String(fetchMock.mock.calls[0][0]));
    expect(firstBatchCallUrl.searchParams.getAll('ids').length).toBe(50);

    const secondBatchCallUrl = new URL(String(fetchMock.mock.calls[1][0]));
    expect(secondBatchCallUrl.searchParams.getAll('ids').length).toBe(10);

    expect((result as any).audio_features).toEqual({
      track_count: 60,
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
});

describe('Analysis Routes', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;

  beforeEach(() => {
    app = new Hono<{ Bindings: Env }>();
    app.route('/analysis', analysisRoutes);

    mockEnv = {
      ...createTestEnv(),
      SESSIONS_KV: {
        get: vi.fn().mockResolvedValue(JSON.stringify({
          user_id: 'test-user-id',
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token',
          expires_at: Date.now() + 3600000,
        })),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined)
      } as any,
    };
  });

  describe('POST /analysis/playlist/:id', () => {
    it('should start playlist analysis', async () => {
      const request = new Request('http://localhost/analysis/playlist/playlist1', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'test-job-id',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'queued',
        progress: 0
      }));

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status', 'queued');
    });

    it('writes queued status and enqueues the analysis job without running analysis inline', async () => {
      const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist');
      const request = new Request('http://localhost/analysis/playlist/playlist1', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json',
        },
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
      expect(mockEnv.CACHE_KV.put).toHaveBeenCalledWith(
        'analysis:playlist1:test-user-id:status',
        expect.stringContaining('"status":"queued"'),
        { expirationTtl: 3600 }
      );
      expect(mockEnv.ANALYSIS_QUEUE.send).toHaveBeenCalledWith(expect.objectContaining({
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        session_id: 'test-session-id',
        attempt: 0,
      }));
      expect(analyzeSpy).not.toHaveBeenCalled();
    });

    it('returns existing queued status without enqueuing a duplicate job', async () => {
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'job-existing',
        playlist_id: 'playlist1',
        user_id: 'test-user-id',
        status: 'queued',
        queued_at: '2026-06-19T00:00:00.000Z',
        progress: 0,
      }));
      const request = new Request('http://localhost/analysis/playlist/playlist1', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json',
        },
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

    it('should return 400 for invalid playlist ID', async () => {
      const request = new Request('http://localhost/analysis/playlist/', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      expect(response.status).toBe(404);
    });
  });

  describe('GET /analysis/playlist/:id/status', () => {
    it('should return analysis status', async () => {
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        job_id: 'test-job-id',
        status: 'completed',
        progress: 100
      }));

      const request = new Request('http://localhost/analysis/playlist/playlist1/status', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status', 'completed');
      expect(data.data).toHaveProperty('progress');
    });

    it('should return 404 for non-existent analysis job', async () => {
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(null);

      const request = new Request('http://localhost/analysis/playlist/nonexistent/status', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'ANALYSIS_NOT_FOUND');
    });
  });

  describe('GET /analysis/playlist/:id/results', () => {
    it('should return analysis results', async () => {
      const request = new Request('http://localhost/analysis/playlist/playlist1/results', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
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
      }));

      const request = new Request('http://localhost/analysis/playlist/playlist1/results', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
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
  });
});

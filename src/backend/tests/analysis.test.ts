import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { Hono } from 'hono';
import { analysisRoutes } from '../routes/analysis';
import { AnalysisService } from '../services/analysis';
import { SpotifyService } from '../services/spotify';
import type { Env } from '../types/env';
import type { SpotifyTrack } from '../types/spotify';

vi.mock('../middleware/auth', () => ({
  authMiddleware: vi.fn().mockImplementation((c, next) => {
    // Mock authenticated user
    c.set('user', {
      id: 'test-user-id',
      email: 'test@example.com',
      name: 'Test User'
    });
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
  afterEach(() => {
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
});

describe('Analysis Routes', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;

  beforeEach(() => {
    app = new Hono<{ Bindings: Env }>();
    app.route('/analysis', analysisRoutes);

    mockEnv = {
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'test-client-id',
      SPOTIFY_CLIENT_SECRET: 'test-client-secret',
      JWT_SECRET: 'test-jwt-secret',
      RECOCOBEATS_API_KEY: 'test-reccobeats-key',
      CACHE_KV: {
        get: vi.fn().mockResolvedValue(null),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined)
      } as any,
      SESSIONS_KV: {
        get: vi.fn().mockResolvedValue(JSON.stringify({
          user_id: 'test-user-id',
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token',
          expires_at: Date.now() + 3600000,
          spotify_data: {}
        })),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined)
      } as any
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
        status: 'processing',
        progress: 100
      }));

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status', 'processing');
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
        status: 'processing',
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
      expect(data.data).toHaveProperty('status');
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
        status: 'processing',
        results: null,
        created_at: new Date().toISOString()
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
      expect(data.data).toHaveProperty('status', 'processing');
    });
  });
});

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { spotifyRoutes } from '../routes/spotify';
import type { Env } from '../types/env';
import { createTestEnv } from './helpers/env';

// Mock the services
vi.mock('../services/spotify', () => ({
  SpotifyService: vi.fn().mockImplementation(function () {
    return {
    getUserPlaylists: vi.fn().mockResolvedValue([
      {
        id: 'playlist1',
        name: 'Test Playlist',
        description: 'A test playlist',
        tracks: 10,
        images: ['http://example.com/image.jpg'],
        owner: 'Test User',
        public: true
      }
    ]),
    getPlaylist: vi.fn().mockResolvedValue({
      id: 'playlist1',
      name: 'Test Playlist',
      description: 'A test playlist',
      tracks: 10,
      images: ['http://example.com/image.jpg'],
      owner: 'Test User',
      public: true
    }),
    getPlaylistTracks: vi.fn().mockResolvedValue({
      total: 1,
      items: [
        {
          track: {
            id: 'track1',
            name: 'Test Song',
            artists: [{ name: 'Test Artist' }],
            album: { name: 'Test Album' },
            duration_ms: 180000
          }
        }
      ]
    }),
    getTrack: vi.fn().mockResolvedValue({
      id: 'track1',
      name: 'Test Song',
      artists: ['Test Artist'],
      album: 'Test Album',
      duration_ms: 180000
    })
    };
  })
}));

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

describe('Spotify Routes', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;

  beforeEach(() => {
    app = new Hono<{ Bindings: Env }>();
    app.route('/spotify', spotifyRoutes);

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

  describe('GET /spotify/playlists', () => {
    it('should return user playlists', async () => {
      const request = new Request('http://localhost/spotify/playlists', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(Array.isArray(data.data)).toBe(true);
      expect(data.data[0]).toHaveProperty('id');
      expect(data.data[0]).toHaveProperty('name');
    });

    it('should aggregate multiple playlist pages', async () => {
      const { SpotifyService } = await import('../services/spotify');
      const mockGetUserPlaylists = vi
        .fn()
        .mockResolvedValueOnce(
          Array.from({ length: 50 }, (_, i) => ({
            id: `playlist-${i}`,
            name: `Playlist ${i}`,
            description: null,
            tracks: { total: 1 },
            images: [],
            owner: { id: 'test-user-id' },
            public: true,
          }))
        )
        .mockResolvedValueOnce([
          {
            id: 'playlist-50',
            name: 'Playlist 50',
            description: null,
            tracks: { total: 1 },
            images: [],
            owner: { id: 'test-user-id' },
            public: true,
          },
        ]);

      vi.mocked(SpotifyService).mockImplementationOnce(
        function () {
          return {
            getUserPlaylists: mockGetUserPlaylists,
            getPlaylist: vi.fn(),
            getPlaylistTracks: vi.fn(),
            getTrack: vi.fn(),
          } as any;
        } as any
      );

      const request = new Request('http://localhost/spotify/playlists', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json',
        },
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(Array.isArray(data.data)).toBe(true);
      expect(data.data.length).toBe(51);
      expect(mockGetUserPlaylists).toHaveBeenCalledTimes(2);
      expect(mockGetUserPlaylists).toHaveBeenNthCalledWith(1, 50, 0);
      expect(mockGetUserPlaylists).toHaveBeenNthCalledWith(2, 50, 50);
    });
  });

  describe('GET /spotify/playlists/:id', () => {
    it('should return playlist details', async () => {
      const request = new Request('http://localhost/spotify/playlists/playlist1', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('id', 'playlist1');
      expect(data.data).toHaveProperty('name');
    });

    it('should return playlist details for requested id', async () => {
      const request = new Request('http://localhost/spotify/playlists/nonexistent', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('id', 'playlist1');
    });

    it('bypasses backend KV when force_refresh=true', async () => {
      const kvGet = mockEnv.CACHE_KV.get as ReturnType<typeof vi.fn>;
      kvGet.mockClear();

      const request = new Request(
        'http://localhost/spotify/playlists/playlist1?force_refresh=true',
        {
          method: 'GET',
          headers: {
            Authorization: 'Bearer test-jwt-token',
            'Content-Type': 'application/json',
          },
        },
      );

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(kvGet).not.toHaveBeenCalled();
      expect(data.meta.cached).toBe(false);
    });
  });

  describe('GET /spotify/playlists/:id/tracks', () => {
    it('should return playlist tracks', async () => {
      const request = new Request('http://localhost/spotify/playlists/playlist1/tracks', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('items');
      expect(Array.isArray(data.data.items)).toBe(true);
      expect(data.data.items[0]).toHaveProperty('track');
      expect(data.data.items[0].track).toHaveProperty('id');
    });

    it('bypasses backend KV and refetches Spotify when force_refresh=true', async () => {
      const kvGet = mockEnv.CACHE_KV.get as ReturnType<typeof vi.fn>;
      kvGet.mockClear();

      const warmRequest = new Request('http://localhost/spotify/playlists/playlist1/tracks', {
        method: 'GET',
        headers: {
          Authorization: 'Bearer test-jwt-token',
          'Content-Type': 'application/json',
        },
      });
      await app.request(warmRequest, undefined, mockEnv);
      expect(kvGet).toHaveBeenCalled();

      kvGet.mockClear();
      const request = new Request(
        'http://localhost/spotify/playlists/playlist1/tracks?force_refresh=true',
        {
          method: 'GET',
          headers: {
            Authorization: 'Bearer test-jwt-token',
            'Content-Type': 'application/json',
          },
        },
      );

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(kvGet).not.toHaveBeenCalled();
      expect(data.meta.cached).toBe(false);
    });
  });

  describe('GET /spotify/tracks/:id', () => {
    it('should return track details', async () => {
      const request = new Request('http://localhost/spotify/tracks/track1', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('id', 'track1');
      expect(data.data).toHaveProperty('name');
    });
  });
});

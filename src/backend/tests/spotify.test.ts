import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { spotifyRoutes } from '../routes/spotify';
import type { Env } from '../types/env';

// Mock the services
vi.mock('../services/spotify-api', () => ({
  SpotifyAPIService: vi.fn().mockImplementation(() => ({
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
    getPlaylistDetails: vi.fn().mockResolvedValue({
      id: 'playlist1',
      name: 'Test Playlist',
      description: 'A test playlist',
      tracks: 10,
      images: ['http://example.com/image.jpg'],
      owner: 'Test User',
      public: true
    }),
    getPlaylistTracks: vi.fn().mockResolvedValue([
      {
        id: 'track1',
        name: 'Test Song',
        artists: ['Test Artist'],
        album: 'Test Album',
        duration_ms: 180000,
        audio_features: {
          danceability: 0.8,
          energy: 0.7,
          valence: 0.6
        }
      }
    ]),
    getTrackDetails: vi.fn().mockResolvedValue({
      id: 'track1',
      name: 'Test Song',
      artists: ['Test Artist'],
      album: 'Test Album',
      duration_ms: 180000
    }),
    getTrackAudioFeatures: vi.fn().mockResolvedValue({
      danceability: 0.8,
      energy: 0.7,
      valence: 0.6,
      tempo: 120,
      acousticness: 0.1
    })
  }))
}));

vi.mock('../middleware/auth', () => ({
  authMiddleware: vi.fn().mockImplementation((c, next) => {
    // Mock authenticated user
    c.set('user', { 
      sub: 'test-user-id',
      email: 'test@example.com',
      name: 'Test User'
    });
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

  describe('GET /spotify/playlists', () => {
    it('should return user playlists', async () => {
      const request = new Request('http://localhost/spotify/playlists', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('playlists');
      expect(Array.isArray(data.data.playlists)).toBe(true);
      expect(data.data.playlists[0]).toHaveProperty('id');
      expect(data.data.playlists[0]).toHaveProperty('name');
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

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('playlist');
      expect(data.data.playlist).toHaveProperty('id', 'playlist1');
      expect(data.data.playlist).toHaveProperty('name');
    });

    it('should return 404 for non-existent playlist', async () => {
      // Mock the service to return null for non-existent playlist
      const { SpotifyAPIService } = require('../services/spotify-api');
      SpotifyAPIService.mockImplementation(() => ({
        getPlaylistDetails: vi.fn().mockResolvedValue(null)
      }));

      const request = new Request('http://localhost/spotify/playlists/nonexistent', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'PLAYLIST_NOT_FOUND');
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

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('tracks');
      expect(Array.isArray(data.data.tracks)).toBe(true);
      expect(data.data.tracks[0]).toHaveProperty('id');
      expect(data.data.tracks[0]).toHaveProperty('name');
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

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('track');
      expect(data.data.track).toHaveProperty('id', 'track1');
      expect(data.data.track).toHaveProperty('name');
    });
  });

  describe('GET /spotify/tracks/:id/audio-features', () => {
    it('should return track audio features', async () => {
      const request = new Request('http://localhost/spotify/tracks/track1/audio-features', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('audio_features');
      expect(data.data.audio_features).toHaveProperty('danceability');
      expect(data.data.audio_features).toHaveProperty('energy');
    });
  });
});

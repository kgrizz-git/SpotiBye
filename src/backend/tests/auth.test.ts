import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { authRoutes } from '../routes/auth';
import type { Env } from '../types/env';

// Mock the services
vi.mock('../services/spotify-auth', () => ({
  SpotifyAuthService: vi.fn().mockImplementation(() => ({
    getAuthUrl: vi.fn().mockReturnValue('https://accounts.spotify.com/authorize?test'),
    generateState: vi.fn().mockReturnValue('test-state'),
    exchangeCodeForTokens: vi.fn().mockResolvedValue({
      access_token: 'test-access-token',
      refresh_token: 'test-refresh-token',
      expires_in: 3600,
      token_type: 'Bearer',
      scope: 'playlist-read-private'
    }),
    refreshAccessToken: vi.fn().mockResolvedValue({
      access_token: 'new-access-token',
      expires_in: 3600,
      token_type: 'Bearer',
      scope: 'playlist-read-private'
    })
  }))
}));

vi.mock('../services/jwt', () => ({
  JWTService: vi.fn().mockImplementation(() => ({
    createToken: vi.fn().mockReturnValue('test-jwt-token'),
    verifyToken: vi.fn().mockReturnValue({
      sub: 'test-user-id',
      email: 'test@example.com',
      name: 'Test User',
      iat: Date.now() / 1000,
      exp: (Date.now() / 1000) + 3600
    })
  }))
}));

describe('Auth Routes', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;

  beforeEach(() => {
    app = new Hono<{ Bindings: Env }>();
    app.route('/auth', authRoutes);
    
    mockEnv = {
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'test-client-id',
      SPOTIFY_CLIENT_SECRET: 'test-client-secret',
      JWT_SECRET: 'test-jwt-secret',
      RECOCOBEATS_API_KEY: 'test-reccobeats-key',
      CACHE_KV: {} as KVNamespace,
      SESSIONS_KV: {} as KVNamespace
    };
  });

  describe('POST /auth/spotify/login', () => {
    it('should return auth URL and state when redirect_uri is provided', async () => {
      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ redirect_uri: 'http://localhost:3000/callback' })
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('auth_url');
      expect(data.data).toHaveProperty('state');
      expect(data.data.auth_url).toContain('accounts.spotify.com');
    });

    it('should return 400 when redirect_uri is missing', async () => {
      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'MISSING_REDIRECT_URI');
    });
  });

  describe('GET /auth/spotify/callback', () => {
    it('should handle successful OAuth callback', async () => {
      const request = new Request('http://localhost/auth/spotify/callback?code=test-code&state=test-state', {
        method: 'GET'
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('tokens');
      expect(data.data).toHaveProperty('jwt_token');
    });

    it('should handle OAuth error', async () => {
      const request = new Request('http://localhost/auth/spotify/callback?error=access_denied', {
        method: 'GET'
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'OAUTH_ERROR');
    });

    it('should return 400 when code or state is missing', async () => {
      const request = new Request('http://localhost/auth/spotify/callback?code=test-code', {
        method: 'GET'
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'INVALID_CALLBACK');
    });
  });

  describe('POST /auth/spotify/refresh', () => {
    it('should refresh access token successfully', async () => {
      const request = new Request('http://localhost/auth/spotify/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: 'test-refresh-token' })
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('access_token');
    });

    it('should return 400 when refresh_token is missing', async () => {
      const request = new Request('http://localhost/auth/spotify/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'MISSING_REFRESH_TOKEN');
    });
  });
});

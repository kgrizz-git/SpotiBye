import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { authRoutes } from '../routes/auth';
import type { Env } from '../types/env';

vi.mock('../services/spotify-auth', () => ({
  SpotifyAuthService: vi.fn().mockImplementation(function () {
    return {
      getAuthUrl: vi.fn().mockReturnValue('https://accounts.spotify.com/authorize?test'),
      generateState: vi.fn().mockReturnValue('test-state'),
      generateCodeVerifier: vi.fn().mockReturnValue('test-code-verifier'),
      computeCodeChallenge: vi.fn().mockResolvedValue('test-code-challenge'),
      exchangeCodeForTokens: vi.fn().mockResolvedValue({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        expires_in: 3600,
        token_type: 'Bearer',
        scope: 'playlist-read-private'
      }),
      getUserProfile: vi.fn().mockResolvedValue({
        id: 'test-user-id',
        email: 'test@example.com',
        display_name: 'Test User'
      }),
      refreshAccessToken: vi.fn().mockResolvedValue({
        access_token: 'new-access-token',
        expires_in: 3600,
        token_type: 'Bearer',
        scope: 'playlist-read-private'
      })
    };
  })
}));

vi.mock('../services/jwt', () => ({
  JWTService: vi.fn().mockImplementation(function () {
    return {
      generateToken: vi.fn().mockResolvedValue('test-jwt-token'),
      verifyToken: vi.fn().mockResolvedValue({
        sub: 'test-user-id',
        email: 'test@example.com',
        name: 'Test User',
        session_id: 'test-session-id',
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600,
      })
    };
  })
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
      CACHE_KV: {
        get: vi.fn().mockResolvedValue(null),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      } as unknown as KVNamespace,
      SESSIONS_KV: {
        get: vi.fn().mockResolvedValue(null),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      } as unknown as KVNamespace,
    };
  });

  describe('POST /auth/spotify/login', () => {
    it('returns auth URL and state when redirect_uri is provided', async () => {
      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ redirect_uri: 'http://localhost:3000/callback' })
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json() as any;

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('data.auth_url');
      expect(data).toHaveProperty('data.state');
      expect(data.data.auth_url).toContain('accounts.spotify.com');

      // PKCE verifier is persisted alongside redirect_uri for the callback.
      const putCall = (mockEnv.CACHE_KV.put as any).mock.calls.find(
        ([key]: [string]) => key.startsWith('oauth_state:')
      );
      expect(putCall).toBeDefined();
      const stored = JSON.parse(putCall[1]);
      expect(stored).toHaveProperty('redirect_uri', 'http://localhost:3000/callback');
      expect(stored).toHaveProperty('code_verifier', 'test-code-verifier');
    });

    it('returns 400 when redirect_uri is missing', async () => {
      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json() as any;

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'MISSING_REDIRECT_URI');
    });
  });

  describe('GET /auth/spotify/callback', () => {
    it('handles successful OAuth callback', async () => {
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce('http://localhost:3000/callback');

      const request = new Request('http://localhost/auth/spotify/callback?code=test-code&state=test-state', {
        method: 'GET'
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json() as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('token');
      expect(data.data).toHaveProperty('user');
      expect(data.data).toHaveProperty('expires_in');
      expect((mockEnv.SESSIONS_KV.put as any)).toHaveBeenCalled();
    });

    it('handles OAuth error', async () => {
      const request = new Request('http://localhost/auth/spotify/callback?error=access_denied', {
        method: 'GET'
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json() as any;

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'OAUTH_ERROR');
    });

    it('returns 400 when code or state is missing', async () => {
      const request = new Request('http://localhost/auth/spotify/callback?code=test-code', {
        method: 'GET'
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json() as any;

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'INVALID_CALLBACK');
    });
  });

  describe('POST /auth/spotify/refresh', () => {
    it('refreshes access token successfully', async () => {
      const sessionJson = JSON.stringify({
        refresh_token: 'test-refresh-token',
        access_token: 'test-access-token',
        expires_at: Date.now() + 3600000,
      });
      (mockEnv.SESSIONS_KV.get as any)
        .mockResolvedValueOnce(sessionJson)
        .mockResolvedValueOnce(sessionJson);

      const request = new Request('http://localhost/auth/spotify/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-jwt-token',
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json() as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('token', 'test-jwt-token');
      expect(data.data).toHaveProperty('access_token', 'test-jwt-token');
      expect(data.data).toHaveProperty('spotify_access_expires_in', 3600);
    });

    it('returns 404 when session is missing', async () => {
      const sessionJson = JSON.stringify({
        refresh_token: 'test-refresh-token',
        access_token: 'test-access-token',
        expires_at: Date.now() + 3600000,
      });
      (mockEnv.SESSIONS_KV.get as any)
        .mockResolvedValueOnce(sessionJson)
        .mockResolvedValueOnce(null);

      const request = new Request('http://localhost/auth/spotify/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-jwt-token',
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json() as any;

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'SESSION_NOT_FOUND');
    });
  });
});

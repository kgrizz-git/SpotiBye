import { describe, it, expect, vi } from 'vitest';
import app from '../index';
import type { Env } from '../types/env';
import { createTestEnv } from './helpers/env';

// Mock JWT service
vi.mock('../services/jwt', () => ({
  JWTService: class {
    constructor(_secret: string) {
      // Mock constructor
    }
    verifyToken() {
      return {
        sub: 'test-user-id',
        email: 'test@example.com',
        name: 'Test User',
        session_id: 'test-session-id'
      };
    }
  }
}));

// Mock environment variables
const mockEnv: Env = {
  ...createTestEnv(),
  SESSIONS_KV: {
    get: vi.fn().mockResolvedValue(JSON.stringify({
      user_id: 'test-user-id',
      access_token: 'test-access-token',
      refresh_token: 'test-refresh-token',
      expires_at: Date.now() + 3600000,
    })),
    getWithMetadata: vi.fn().mockResolvedValue({ value: null, metadata: null }),
    put: vi.fn().mockResolvedValue(undefined),
    delete: vi.fn().mockResolvedValue(undefined),
    list: vi.fn().mockResolvedValue({ keys: [] })
  } as any,
};

describe('API Coverage Tests', () => {
  describe('All API Endpoints', () => {
    it('should have all authentication endpoints available', async () => {
      const endpoints = [
        { method: 'POST', path: '/auth/spotify/login', auth: false },
        { method: 'GET', path: '/auth/spotify/callback', auth: false },
        { method: 'POST', path: '/auth/spotify/refresh', auth: true }
      ];

      for (const endpoint of endpoints) {
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (endpoint.auth) {
          headers['Authorization'] = 'Bearer mock-token';
        }

        const request = new Request(`http://localhost${endpoint.path}`, {
          method: endpoint.method,
          headers,
          body: endpoint.method === 'POST' ? JSON.stringify({}) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        // Should not return 404 (endpoint exists)
        expect(response.status).not.toBe(404);
        expect([200, 400, 401, 500]).toContain(response.status);
      }
    });

    it('should have all Spotify data endpoints available', async () => {
      const endpoints = [
        { method: 'GET', path: '/spotify/playlists' },
        { method: 'GET', path: '/spotify/playlists/test-playlist-id' },
        { method: 'GET', path: '/spotify/playlists/test-playlist-id/tracks' },
        { method: 'GET', path: '/spotify/tracks/test-track-id' },
        { method: 'GET', path: '/spotify/tracks/test-track-id/audio-features' }
      ];

      for (const endpoint of endpoints) {
        const request = new Request(`http://localhost${endpoint.path}`, {
          method: endpoint.method,
          headers: { 'Content-Type': 'application/json' }
        });

        const response = await app.fetch(request, mockEnv);

        // Should not return 404 (endpoint exists)
        expect(response.status).not.toBe(404);
        expect([200, 400, 401, 404, 500]).toContain(response.status);
      }
    });

    it('should have all analysis endpoints available', async () => {
      const endpoints = [
        { method: 'POST', path: '/analysis/playlist/test-playlist-id' },
        { method: 'GET', path: '/analysis/playlist/test-playlist-id/status' },
        { method: 'GET', path: '/analysis/playlist/test-playlist-id/results' }
      ];

      for (const endpoint of endpoints) {
        const request = new Request(`http://localhost${endpoint.path}`, {
          method: endpoint.method,
          headers: { 'Content-Type': 'application/json' },
          body: endpoint.method === 'POST' ? JSON.stringify({}) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        // Should not return 404 (endpoint exists)
        expect(response.status).not.toBe(404);
        expect([200, 400, 401, 404, 500]).toContain(response.status);
      }
    });

    it('should have all export endpoints available', async () => {
      const endpoints = [
        { method: 'POST', path: '/export/playlist/test-playlist-id' },
        { method: 'GET', path: '/export/playlist/test-export-id/download' }
      ];

      for (const endpoint of endpoints) {
        const request = new Request(`http://localhost${endpoint.path}`, {
          method: endpoint.method,
          headers: { 'Content-Type': 'application/json' },
          body: endpoint.method === 'POST' ? JSON.stringify({}) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        // Should not return 404 (endpoint exists)
        expect(response.status).not.toBe(404);
        expect([200, 400, 401, 404, 500]).toContain(response.status);
      }
    });

    it('should have system endpoints available', async () => {
      const endpoints = [
        { method: 'GET', path: '/health' }
      ];

      for (const endpoint of endpoints) {
        const request = new Request(`http://localhost${endpoint.path}`, {
          method: endpoint.method,
          headers: { 'Content-Type': 'application/json' }
        });

        const response = await app.fetch(request, mockEnv);

        // Health endpoint should work
        expect(response.status).toBe(200);
      }
    });
  });

  describe('API Response Formats', () => {
    it('should return consistent error response format', async () => {
      // Test various error scenarios
      const errorRequests = [
        { method: 'POST', path: '/auth/spotify/login', body: {} }, // Missing redirect_uri
        { method: 'GET', path: '/non-existent' }, // 404
        { method: 'GET', path: '/spotify/playlists' } // Unauthorized
      ];

      for (const req of errorRequests) {
        const request = new Request(`http://localhost${req.path}`, {
          method: req.method,
          headers: { 'Content-Type': 'application/json' },
          body: req.body ? JSON.stringify(req.body) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        if (response.status >= 400) {
          const data = await response.json() as any;

          // Error responses should have consistent structure
          if (response.status === 404) {
            expect(data).toHaveProperty('error');
            expect(data.error).toHaveProperty('code', 'NOT_FOUND');
            expect(data.error).toHaveProperty('message', 'Not Found');
            expect(data.error).toHaveProperty('request_id');
          } else if (response.status >= 400 && response.status < 500) {
            // Client errors should have error object with code and message
            expect(data).toHaveProperty('error');
            if (typeof data.error === 'object' && data.error !== null) {
              expect(data.error).toHaveProperty('code');
              expect(data.error).toHaveProperty('message');
            }
          }
        }
      }
    });

    it('should return consistent success response format', async () => {
      // Test successful responses
      const successRequests = [
        { method: 'GET', path: '/health' },
        { method: 'POST', path: '/auth/spotify/login', body: { redirect_uri: 'http://localhost:3000/callback' } }
      ];

      for (const req of successRequests) {
        const request = new Request(`http://localhost${req.path}`, {
          method: req.method,
          headers: { 'Content-Type': 'application/json' },
          body: req.body ? JSON.stringify(req.body) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        if (response.status === 200) {
          const data = await response.json();

          // Success responses should have consistent structure
          if (req.path === '/health') {
            expect(data).toHaveProperty('data');
            expect(data.data).toHaveProperty('status', 'healthy');
            expect(data.data).toHaveProperty('service', 'spotibye-backend');
          } else {
            // API endpoints should wrap data in 'data' property
            expect(data).toHaveProperty('data');
          }
        }
      }
    });
  });

  describe('API Security', () => {
    it('should require authentication for protected endpoints', async () => {
      const protectedEndpoints = [
        '/spotify/playlists',
        '/spotify/playlists/test-id',
        '/spotify/playlists/test-id/tracks',
        '/spotify/tracks/test-id',
        '/spotify/tracks/test-id/audio-features',
        '/analysis/playlist/test-id',
        '/analysis/playlist/test-id/status',
        '/analysis/playlist/test-id/results',
        '/export/playlist/test-id'
      ];

      for (const endpoint of protectedEndpoints) {
        const request = new Request(`http://localhost${endpoint}`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' }
        });

        const response = await app.fetch(request, mockEnv);

        // Protected endpoints should require authentication
        expect([401, 500]).toContain(response.status);
      }
    });

    it('should allow public endpoints without authentication', async () => {
      const publicEndpoints = [
        '/health',
        '/auth/spotify/login',
        '/auth/spotify/callback'
      ];

      for (const endpoint of publicEndpoints) {
        const request = new Request(`http://localhost${endpoint}`, {
          method: endpoint.includes('callback') ? 'GET' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: endpoint.includes('login') ? JSON.stringify({ redirect_uri: 'http://localhost:3000' }) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        // Public endpoints should not require authentication
        expect(response.status).not.toBe(401);
      }
    });
  });

  describe('CORS Headers', () => {
    it('should include CORS headers on all endpoints', async () => {
      const endpoints = [
        '/health',
        '/auth/spotify/login',
        '/spotify/playlists',
        '/analysis/playlist/test-id',
        '/export/playlist/test-id'
      ];

      for (const endpoint of endpoints) {
        const request = new Request(`http://localhost${endpoint}`, {
          method: 'GET',
          headers: { 'Origin': 'http://localhost:3000' }
        });

        const response = await app.fetch(request, mockEnv);

        // Should include CORS headers
        expect(response.headers.get('access-control-allow-origin')).toBeTruthy();
      }
    });
  });

  describe('Content-Type Headers', () => {
    it('should return appropriate content-type for responses', async () => {
      const request = new Request('http://localhost/health', {
        method: 'GET'
      });

      const response = await app.fetch(request, mockEnv);

      // Should return JSON content type
      expect(response.headers.get('content-type')).toContain('application/json');
    });
  });
});

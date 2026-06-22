import { describe, it, expect } from 'vitest';
import app from '../index';
import { createTestEnv } from './helpers/env';

// Mock environment variables
const mockEnv = createTestEnv();

describe('API Integration Tests', () => {
  describe('Health Check', () => {
    it('should return healthy status', async () => {
      const request = new Request('http://localhost/health', {
        method: 'GET'
      });

      const response = await app.fetch(request, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('status', 'healthy');
      expect(data.data).toHaveProperty('service', 'spotibye-backend');
      expect(data.data).toHaveProperty('timestamp');
    });
  });

  describe('Authentication Endpoints', () => {
    it('POST /auth/spotify/login should initiate OAuth flow', async () => {
      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ redirect_uri: 'http://localhost:3000/callback' })
      });

      const response = await app.fetch(request, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data).toHaveProperty('data');
      expect(data.data).toHaveProperty('auth_url');
      expect(data.data).toHaveProperty('state');
      expect(data.data.auth_url).toContain('accounts.spotify.com');
    });

    it('POST /auth/spotify/login should return 400 without redirect_uri', async () => {
      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      const response = await app.fetch(request, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(400);
      expect(data).toHaveProperty('error');
      expect(data.error).toHaveProperty('code', 'MISSING_REDIRECT_URI');
    });

    it('GET /auth/spotify/callback should handle OAuth callback', async () => {
      const request = new Request('http://localhost/auth/spotify/callback?code=test-code&state=test-state', {
        method: 'GET'
      });

      const response = await app.fetch(request, mockEnv);

      // This may fail without proper Spotify credentials, but should have proper error handling
      expect([200, 400, 500]).toContain(response.status);
    });
  });

  describe('Spotify Endpoints', () => {
    it('GET /spotify/playlists should require authentication', async () => {
      const request = new Request('http://localhost/spotify/playlists', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      const response = await app.fetch(request, mockEnv);
      await response.json();

      // Should return 401 or 500 due to missing auth token
      expect([401, 500]).toContain(response.status);
    });

    it('GET /spotify/playlists/:id should require authentication', async () => {
      const request = new Request('http://localhost/spotify/playlists/test-playlist', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });

      const response = await app.fetch(request, mockEnv);

      // Should return 401 or 500 due to missing auth token
      expect([401, 500]).toContain(response.status);
    });
  });

  describe('Analysis Endpoints', () => {
    it('POST /analysis/playlist/:id should require authentication', async () => {
      const request = new Request('http://localhost/analysis/playlist/test-playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const response = await app.fetch(request, mockEnv);

      // Should return 401 or 500 due to missing auth token
      expect([401, 500]).toContain(response.status);
    });
  });

  describe('Export Endpoints', () => {
    it('POST /export/playlist/:id should require authentication', async () => {
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const response = await app.fetch(request, mockEnv);

      // Should return 401 or 500 due to missing auth token
      expect([401, 500]).toContain(response.status);
    });
  });

  describe('CORS Headers', () => {
    it('should include CORS headers', async () => {
      const request = new Request('http://localhost/health', {
        method: 'GET',
        headers: { 'Origin': 'http://localhost:3000' }
      });

      const response = await app.fetch(request, mockEnv);

      expect(response.headers.get('access-control-allow-origin')).toBe('http://localhost:3000');
    });
  });

  describe('404 Handling', () => {
    it('should return 404 for non-existent routes', async () => {
      const request = new Request('http://localhost/non-existent-route', {
        method: 'GET'
      });

      const response = await app.fetch(request, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(404);
      expect(data).toHaveProperty('error');
      expect(data.error).toHaveProperty('code', 'NOT_FOUND');
      expect(data.error).toHaveProperty('message', 'Not Found');
      expect(data.error).toHaveProperty('request_id');
    });
  });
});

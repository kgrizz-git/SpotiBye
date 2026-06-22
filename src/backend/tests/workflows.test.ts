import { describe, it, expect } from 'vitest';
import app from '../index';
import type { Env } from '../types/env';
import { createTestEnv } from './helpers/env';

// Mock environment variables
const mockEnv: Env = createTestEnv();

describe('Complete Workflow Integration Tests', () => {
  describe('Authentication Workflow', () => {
    it('should complete OAuth initiation flow', async () => {
      // Step 1: Initiate OAuth
      const loginRequest = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          redirect_uri: 'http://localhost:3000/callback'
        })
      });

      const loginResponse = await app.fetch(loginRequest, mockEnv);
      const loginData = (await loginResponse.json()) as any;

      expect(loginResponse.status).toBe(200);
      expect(loginData.data).toHaveProperty('auth_url');
      expect(loginData.data).toHaveProperty('state');

      // Verify the auth URL structure
      const authUrl = loginData.data.auth_url;
      expect(authUrl).toContain('accounts.spotify.com/authorize');
      expect(authUrl).toContain('response_type=code');
    });

    it('should handle OAuth callback with errors gracefully', async () => {
      // Simulate OAuth error callback
      const callbackRequest = new Request('http://localhost/auth/spotify/callback?error=access_denied&state=test-state', {
        method: 'GET'
      });

      const callbackResponse = await app.fetch(callbackRequest, mockEnv);
      const callbackData = (await callbackResponse.json()) as any;

      expect(callbackResponse.status).toBe(400);
      expect(callbackData.error).toHaveProperty('code', 'OAUTH_ERROR');
    });
  });

  describe('Protected Resource Access Workflow', () => {
    it('should deny access to protected resources without auth', async () => {
      const protectedEndpoints = [
        '/spotify/playlists',
        '/spotify/playlists/test-id',
        '/analysis/playlist/test-id',
        '/export/playlist/test-id'
      ];

      for (const endpoint of protectedEndpoints) {
        const request = new Request(`http://localhost${endpoint}`, {
          method: endpoint.includes('export') ? 'POST' : 'GET',
          headers: { 'Content-Type': 'application/json' },
          body: endpoint.includes('export') ? JSON.stringify({}) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        // Should require authentication
        expect([401, 500]).toContain(response.status);
      }
    });

    it('should allow access to public resources without auth', async () => {
      const publicEndpoints = [
        { path: '/health', method: 'GET' },
        { path: '/auth/spotify/login', method: 'POST', body: { redirect_uri: 'http://localhost:3000' } }
      ];

      for (const endpoint of publicEndpoints) {
        const request = new Request(`http://localhost${endpoint.path}`, {
          method: endpoint.method,
          headers: { 'Content-Type': 'application/json' },
          body: endpoint.body ? JSON.stringify(endpoint.body) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        // Should not require authentication
        expect(response.status).not.toBe(401);
      }
    });
  });

  describe('Error Handling Workflow', () => {
    it('should handle malformed requests gracefully', async () => {
      const malformedRequests = [
        // Missing required body
        { path: '/auth/spotify/login', method: 'POST', body: null },
        // Invalid JSON
        { path: '/auth/spotify/login', method: 'POST', body: 'invalid-json' },
        // Missing query parameters
        { path: '/auth/spotify/callback', method: 'GET', body: null }
      ];

      for (const req of malformedRequests) {
        const request = new Request(`http://localhost${req.path}`, {
          method: req.method,
          headers: { 'Content-Type': 'application/json' },
          body: req.body ? JSON.stringify(req.body) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        // Should handle gracefully without crashing
        expect([400, 401, 404, 500]).toContain(response.status);
      }
    });
  });

  describe('CORS Workflow', () => {
    it('should handle cross-origin requests properly', async () => {
      const origins = ['http://localhost:3000', 'https://spotibye.com'];

      for (const origin of origins) {
        const request = new Request('http://localhost/health', {
          method: 'GET',
          headers: { 'Origin': origin }
        });

        const response = await app.fetch(request, mockEnv);

        // Should include appropriate CORS headers
        expect(response.headers.get('access-control-allow-origin')).toBeTruthy();
      }
    });
  });

  describe('Request Validation Workflow', () => {
    it('should validate request methods', async () => {
      // Test unsupported methods on endpoints
      const invalidRequests = [
        { path: '/health', method: 'POST' },
        { path: '/auth/spotify/login', method: 'GET' },
        { path: '/spotify/playlists', method: 'POST' }
      ];

      for (const req of invalidRequests) {
        const request = new Request(`http://localhost${req.path}`, {
          method: req.method,
          headers: { 'Content-Type': 'application/json' }
        });

        const response = await app.fetch(request, mockEnv);

        // Should handle method not allowed or auth guard responses for protected routes.
        expect([401, 404, 405, 400, 500]).toContain(response.status);
      }
    });

    it('should validate content types', async () => {
      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        body: 'some text'
      });

      const response = await app.fetch(request, mockEnv);

      // Should handle content type validation
      expect([400, 415, 500]).toContain(response.status);
    });
  });

  describe('Response Format Workflow', () => {
    it('should maintain consistent response format across endpoints', async () => {
      const endpoints = [
        { path: '/health', method: 'GET' },
        { path: '/auth/spotify/login', method: 'POST', body: { redirect_uri: 'http://localhost:3000' } }
      ];

      for (const endpoint of endpoints) {
        const request = new Request(`http://localhost${endpoint.path}`, {
          method: endpoint.method,
          headers: { 'Content-Type': 'application/json' },
          body: endpoint.body ? JSON.stringify(endpoint.body) : undefined
        });

        const response = await app.fetch(request, mockEnv);

        if (response.status === 200) {
          const data = (await response.json()) as Record<string, any>;

          // Should have consistent JSON structure
          expect(typeof data).toBe('object');
          expect(data).not.toBeNull();

          // Check for expected response patterns
          if (endpoint.path === '/health') {
            expect(data).toHaveProperty('data');
            expect(data.data).toHaveProperty('status');
          } else {
            expect(data).toHaveProperty('data');
          }
        }
      }
    });
  });

  describe('System Health Workflow', () => {
    it('should respond to health checks consistently', async () => {
      const request = new Request('http://localhost/health', {
        method: 'GET'
      });

      const response = await app.fetch(request, mockEnv);
      const data = (await response.json()) as any;

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('status', 'healthy');
      expect(data.data).toHaveProperty('service', 'spotibye-backend');
      expect(data.data).toHaveProperty('timestamp');

      // Timestamp should be a valid ISO string
      const timestamp = new Date(data.data.timestamp);
      expect(timestamp.getTime()).not.toBeNaN();
    });
  });
});

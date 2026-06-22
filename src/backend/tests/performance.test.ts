import { describe, it, expect } from 'vitest';
import app from '../index';
import type { Env } from '../types/env';
import { createTestEnv } from './helpers/env';

// Mock environment variables
const mockEnv: Env = createTestEnv();

describe('API Performance Tests', () => {
  describe('Response Time Benchmarks', () => {
    it('should handle health check with stable CI latency', async () => {
      const iterations = 5;
      const durations: number[] = [];

      // Warm-up request to avoid first-run transform/setup overhead skewing results.
      await app.fetch(new Request('http://localhost/health', { method: 'GET' }), mockEnv);

      for (let i = 0; i < iterations; i += 1) {
        const request = new Request('http://localhost/health', {
          method: 'GET'
        });

        const startTime = Date.now();
        const response = await app.fetch(request, mockEnv);
        const endTime = Date.now();

        expect(response.status).toBe(200);
        durations.push(endTime - startTime);
      }

      const averageDuration = durations.reduce((sum, value) => sum + value, 0) / durations.length;
      expect(averageDuration).toBeLessThan(100);
    });

    it('should handle authentication endpoints within 200ms', async () => {
      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ redirect_uri: 'http://localhost:3000' })
      });

      const startTime = Date.now();
      const response = await app.fetch(request, mockEnv);
      const endTime = Date.now();
      const duration = endTime - startTime;

      expect([200, 400]).toContain(response.status);
      expect(duration).toBeLessThan(200); // Auth should be fast
    });

    it('should handle public endpoints within 100ms', async () => {
      const endpoints = [
        '/health',
        '/auth/spotify/login'
      ];

      for (const endpoint of endpoints) {
        const request = new Request(`http://localhost${endpoint}`, {
          method: endpoint.includes('login') ? 'POST' : 'GET',
          headers: { 'Content-Type': 'application/json' },
          body: endpoint.includes('login') ? JSON.stringify({ redirect_uri: 'http://localhost:3000' }) : undefined
        });

        const startTime = Date.now();
        const response = await app.fetch(request, mockEnv);
        const endTime = Date.now();
        const duration = endTime - startTime;

        expect(response.status).not.toBe(500);
        expect(duration).toBeLessThan(100); // Public endpoints should be fast
      }
    });
  });

  describe('Concurrent Request Handling', () => {
    it('should handle 10 concurrent health checks', async () => {
      const requests = Array(10).fill(null).map(() =>
        new Request('http://localhost/health', { method: 'GET' })
      );

      const startTime = Date.now();
      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );
      const endTime = Date.now();
      const totalDuration = endTime - startTime;

      // All requests should succeed
      responses.forEach(response => {
        expect(response.status).toBe(200);
      });

      // Concurrent requests should be faster than sequential
      expect(totalDuration).toBeLessThan(500); // Much less than 10 * 50ms
    });

    it('should handle 5 concurrent authentication requests', async () => {
      const requests = Array(5).fill(null).map(() =>
        new Request('http://localhost/auth/spotify/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ redirect_uri: 'http://localhost:3000' })
        })
      );

      const startTime = Date.now();
      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );
      const endTime = Date.now();
      const totalDuration = endTime - startTime;

      // All requests should handle gracefully
      responses.forEach(response => {
        expect([200, 400]).toContain(response.status);
      });

      // Should handle concurrent requests efficiently
      expect(totalDuration).toBeLessThan(800);
    });

    it('should handle mixed concurrent requests', async () => {
      const requests = [
        new Request('http://localhost/health', { method: 'GET' }),
        new Request('http://localhost/auth/spotify/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ redirect_uri: 'http://localhost:3000' })
        }),
        new Request('http://localhost/nonexistent', { method: 'GET' })
      ];

      const startTime = Date.now();
      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );
      const endTime = Date.now();
      const totalDuration = endTime - startTime;

      // Should handle mixed request types
      expect(responses[0].status).toBe(200); // health
      expect([200, 400]).toContain(responses[1].status); // auth
      expect(responses[2].status).toBe(404); // not found

      expect(totalDuration).toBeLessThan(300);
    });
  });

  describe('Memory and Resource Usage', () => {
    it('should handle large request payloads efficiently', async () => {
      const largePayload = {
        data: 'x'.repeat(10000), // 10KB of data
        nested: {
          array: Array(100).fill('large data item'),
          object: Object.fromEntries(
            Array(50).fill(null).map((_, i) => [`key${i}`, `value${i}`.repeat(100)])
          )
        }
      };

      const request = new Request('http://localhost/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(largePayload)
      });

      const startTime = Date.now();
      const response = await app.fetch(request, mockEnv);
      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should handle large payloads without memory issues
      expect([200, 400, 413]).toContain(response.status);
      expect(duration).toBeLessThan(500);
    });

    it('should handle many small requests efficiently', async () => {
      const requests = Array(20).fill(null).map((_, i) =>
        new Request(`http://localhost/health?test=${i}`, { method: 'GET' })
      );

      const startTime = Date.now();
      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );
      const endTime = Date.now();
      const totalDuration = endTime - startTime;

      // All requests should succeed
      responses.forEach(response => {
        expect(response.status).toBe(200);
      });

      // Should handle many small requests efficiently
      expect(totalDuration).toBeLessThan(1000);
    });
  });

  describe('Error Handling Performance', () => {
    it('should handle invalid requests quickly', async () => {
      const invalidRequests = [
        new Request('http://localhost/health', { method: 'POST' }), // Wrong method
        new Request('http://localhost/nonexistent', { method: 'GET' }), // Not found
        new Request('http://localhost/auth/spotify/login', { // Missing body
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
      ];

      for (const request of invalidRequests) {
        const startTime = Date.now();
        const response = await app.fetch(request, mockEnv);
        const endTime = Date.now();
        const duration = endTime - startTime;

        // Should handle errors quickly
        expect([400, 404, 405, 500]).toContain(response.status);
        expect(duration).toBeLessThan(100);
      }
    });

    it('should handle malformed requests efficiently', async () => {
      const malformedRequests = [
        new Request('http://localhost/auth/spotify/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: 'invalid json'
        }),
        new Request('http://localhost/auth/spotify/login', {
          method: 'POST',
          headers: { 'Content-Type': 'text/plain' },
          body: 'plain text'
        })
      ];

      for (const request of malformedRequests) {
        const startTime = Date.now();
        const response = await app.fetch(request, mockEnv);
        const endTime = Date.now();
        const duration = endTime - startTime;

        // Should handle malformed requests quickly
        expect([400, 415, 500]).toContain(response.status);
        expect(duration).toBeLessThan(100);
      }
    });
  });

  describe('Caching Performance', () => {
    it('should demonstrate cache hit performance', async () => {
      // Mock cache hit
      (mockEnv.CACHE_KV.get as any).mockResolvedValue('{"cached": true}');

      const request = new Request('http://localhost/health', { method: 'GET' });

      const startTime = Date.now();
      const response = await app.fetch(request, mockEnv);
      const endTime = Date.now();
      const duration = endTime - startTime;

      expect(response.status).toBe(200);
      expect(duration).toBeLessThan(50); // Cache hits should be very fast
    });

    it('should demonstrate cache miss performance', async () => {
      // Mock cache miss
      (mockEnv.CACHE_KV.get as any).mockResolvedValue(null);

      const request = new Request('http://localhost/health', { method: 'GET' });

      const startTime = Date.now();
      const response = await app.fetch(request, mockEnv);
      const endTime = Date.now();
      const duration = endTime - startTime;

      expect(response.status).toBe(200);
      expect(duration).toBeLessThan(100); // Cache misses should still be fast
    });
  });

  describe('Rate Limiting Performance', () => {
    it('should handle rate limiting efficiently', async () => {
      const requests = Array(15).fill(null).map(() =>
        new Request('http://localhost/health', { method: 'GET' })
      );

      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );

      // Should handle rate limiting without performance degradation
      responses.forEach(response => {
        expect([200, 429]).toContain(response.status);
      });
    });
  });

  describe('Stress Testing', () => {
    it('should handle sustained load without memory leaks', async () => {
      const batches = 5;
      const requestsPerBatch = 10;

      for (let batch = 0; batch < batches; batch++) {
        const requests = Array(requestsPerBatch).fill(null).map((_, i) =>
          new Request(`http://localhost/health?batch=${batch}&req=${i}`, { method: 'GET' })
        );

        const startTime = Date.now();
        const responses = await Promise.all(
          requests.map(req => app.fetch(req, mockEnv))
        );
        const endTime = Date.now();
        const batchDuration = endTime - startTime;

        // Each batch should complete efficiently
        responses.forEach(response => {
          expect(response.status).toBe(200);
        });
        expect(batchDuration).toBeLessThan(500);
      }
    });
  });
});

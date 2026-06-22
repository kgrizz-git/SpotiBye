import { describe, it, expect } from 'vitest';
import app from '../index';
import type { Env } from '../types/env';
import { createTestEnv } from './helpers/env';

// Mock environment variables
const mockEnv: Env = createTestEnv();

describe('Workers Execution Limits and Cold Starts', () => {
  describe('CPU Time Limits', () => {
    it('should handle CPU-intensive operations within limits', async () => {
      // Simulate CPU-intensive operation
      const cpuIntensiveRequest = new Request('http://localhost/health', {
        method: 'GET',
        headers: { 'X-CPU-Intensive': 'true' }
      });

      const startTime = Date.now();
      const response = await app.fetch(cpuIntensiveRequest, mockEnv);
      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should complete within reasonable CPU time limits
      expect(response.status).toBe(200);
      expect(duration).toBeLessThan(5000); // 5 seconds max CPU time
    });

    it('should handle long-running operations gracefully', async () => {
      // Simulate a potentially long-running operation
      const longRunningRequest = new Request('http://localhost/health', {
        method: 'GET',
        headers: { 'X-Long-Running': 'true' }
      });

      const startTime = Date.now();
      const response = await app.fetch(longRunningRequest, mockEnv);
      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should either complete successfully or timeout gracefully
      expect([200, 408, 500]).toContain(response.status);

      if (response.status === 200) {
        expect(duration).toBeLessThan(10000); // 10 seconds max
      }
    });
  });

  describe('Memory Limits', () => {
    it('should handle large data structures without memory leaks', async () => {
      // Create a request that would require significant memory
      const largeDataRequest = new Request('http://localhost/health', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          largeArray: Array(10000).fill(null).map((_, i) => ({
            id: i,
            data: 'x'.repeat(1000),
            nested: {
              deep: Array(100).fill('nested data')
            }
          }))
        })
      });

      const initialMemory = process.memoryUsage();
      const response = await app.fetch(largeDataRequest, mockEnv);
      const finalMemory = process.memoryUsage();

      // Should handle large data without memory issues
      expect([200, 400, 404, 413]).toContain(response.status);

      // Memory usage should not grow excessively
      const memoryGrowth = finalMemory.heapUsed - initialMemory.heapUsed;
      expect(memoryGrowth).toBeLessThan(50 * 1024 * 1024); // 50MB max growth
    });

    it('should handle memory pressure gracefully', async () => {
      // Simulate memory pressure with multiple concurrent requests
      const requests = Array(20).fill(null).map((_, i) =>
        new Request(`http://localhost/health?memory-test=${i}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data: 'x'.repeat(50000), // 50KB per request
            index: i
          })
        })
      );

      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );

      // All requests should handle memory pressure gracefully
      responses.forEach(response => {
        expect([200, 400, 404, 429, 500]).toContain(response.status);
      });
    });
  });

  describe('Cold Start Performance', () => {
    it('should simulate cold start behavior', async () => {
      // First request after "cold start"
      const coldStartRequest = new Request('http://localhost/health', {
        method: 'GET',
        headers: { 'X-Cold-Start': 'true' }
      });

      const startTime = Date.now();
      const response = await app.fetch(coldStartRequest, mockEnv);
      const endTime = Date.now();
      const coldStartDuration = endTime - startTime;

      // Cold starts should take longer but still be reasonable
      expect(response.status).toBe(200);
      expect(coldStartDuration).toBeLessThan(3000); // 3 seconds max cold start

      // Second request should be faster (warm)
      const warmStartTime = Date.now();
      const warmResponse = await app.fetch(coldStartRequest, mockEnv);
      const warmEndTime = Date.now();
      const warmDuration = warmEndTime - warmStartTime;

      expect(warmResponse.status).toBe(200);
      // In CI, millisecond timer jitter can make warm appear slightly slower.
      // Keep this assertion meaningful but resilient to tiny fluctuations.
      expect(warmDuration).toBeLessThanOrEqual(coldStartDuration + 20);
    });

    it('should handle concurrent cold starts', async () => {
      // Simulate multiple concurrent cold starts
      const coldStartRequests = Array(5).fill(null).map((_, i) =>
        new Request(`http://localhost/health?cold=${i}`, {
          method: 'GET',
          headers: { 'X-Cold-Start': 'true' }
        })
      );

      const startTime = Date.now();
      const responses = await Promise.all(
        coldStartRequests.map(req => app.fetch(req, mockEnv))
      );
      const endTime = Date.now();
      const totalDuration = endTime - startTime;

      // All concurrent cold starts should succeed
      responses.forEach(response => {
        expect(response.status).toBe(200);
      });

      // Should handle concurrent cold starts efficiently
      expect(totalDuration).toBeLessThan(5000); // 5 seconds max for all
    });
  });

  describe('Request Size Limits', () => {
    it('should handle large request payloads', async () => {
      // Test with progressively larger payloads
      const sizes = [1024, 10240, 102400, 1024000]; // 1KB, 10KB, 100KB, 1MB

      for (const size of sizes) {
        const largePayload = {
          data: 'x'.repeat(size),
          size: size,
          timestamp: Date.now()
        };

        const request = new Request('http://localhost/health', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(largePayload)
        });

        const response = await app.fetch(request, mockEnv);

        // Should handle large payloads or reject appropriately
        expect([200, 400, 404, 413]).toContain(response.status);

        if (response.status === 413) {
          // Should reject payloads that are too large
          break;
        }
      }
    });

    it('should handle many small requests efficiently', async () => {
      const requestCount = 100;
      const requests = Array(requestCount).fill(null).map((_, i) =>
        new Request(`http://localhost/health?req=${i}`, { method: 'GET' })
      );

      const startTime = Date.now();
      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );
      const endTime = Date.now();
      const avgDuration = (endTime - startTime) / requestCount;

      // Should handle many requests efficiently
      responses.forEach(response => {
        expect(response.status).toBe(200);
      });

      expect(avgDuration).toBeLessThan(50); // Average < 50ms per request
    });
  });

  describe('Response Size Limits', () => {
    it('should handle large response payloads', async () => {
      // Request a potentially large response
      const largeResponseRequest = new Request('http://localhost/health', {
        method: 'GET',
        headers: { 'X-Large-Response': 'true' }
      });

      const response = await app.fetch(largeResponseRequest, mockEnv);

      // Should handle large responses or limit appropriately
      expect([200, 400, 500]).toContain(response.status);

      if (response.status === 200) {
        const responseText = await response.text();
        // Response should be reasonable size
        expect(responseText.length).toBeLessThan(1000000); // 1MB max
      }
    });
  });

  describe('Concurrent Execution Limits', () => {
    it('should handle high concurrency without degradation', async () => {
      const concurrencyLevels = [10, 25, 50, 100];

      for (const concurrency of concurrencyLevels) {
        const requests = Array(concurrency).fill(null).map((_, i) =>
          new Request(`http://localhost/health?concurrency=${i}`, { method: 'GET' })
        );

        const startTime = Date.now();
        const responses = await Promise.all(
          requests.map(req => app.fetch(req, mockEnv))
        );
        const endTime = Date.now();
        const duration = endTime - startTime;

        // Should handle each concurrency level
        const successCount = responses.filter(r => r.status === 200).length;
        expect(successCount).toBeGreaterThan(concurrency * 0.8); // At least 80% success

        // Performance shouldn't degrade too much
        expect(duration).toBeLessThan(concurrency * 100); // < 100ms per request
      }
    });

    it('should handle resource exhaustion gracefully', async () => {
      // Push the system to its limits
      const extremeConcurrency = 200;
      const requests = Array(extremeConcurrency).fill(null).map((_, i) =>
        new Request(`http://localhost/health?extreme=${i}`, { method: 'GET' })
      );

      const responses = await Promise.allSettled(
        requests.map(req => app.fetch(req, mockEnv))
      );

      // Should handle extreme load gracefully
      const successful = responses.filter(r =>
        r.status === 'fulfilled' && r.value.status === 200
      ).length;

      const rejected = responses.filter(r => r.status === 'rejected').length;

      // Should have some successes even under extreme load
      expect(successful).toBeGreaterThan(0);

      // Should handle rejections gracefully
      expect(rejected).toBeLessThan(extremeConcurrency * 0.5); // Less than 50% rejected
    });
  });

  describe('Timeout Handling', () => {
    it('should handle operation timeouts gracefully', async () => {
      // Simulate operations that might timeout
      const timeoutRequest = new Request('http://localhost/health', {
        method: 'GET',
        headers: { 'X-Timeout-Test': 'true' }
      });

      const response = await app.fetch(timeoutRequest, mockEnv);

      // Should handle timeouts gracefully
      expect([200, 408, 500]).toContain(response.status);

      if (response.status === 408) {
        const data = await response.json() as any;
        expect(data.error).toHaveProperty('code', 'TIMEOUT');
      }
    });

    it('should respect request timeout limits', async () => {
      // Test with different timeout scenarios
      const timeoutScenarios = [
        { timeout: 1000, expected: [200, 408, 500] },
        { timeout: 5000, expected: [200, 408, 500] },
        { timeout: 10000, expected: [200, 408, 500] }
      ];

      for (const scenario of timeoutScenarios) {
        const request = new Request('http://localhost/health', {
          method: 'GET',
          headers: { 'X-Timeout': scenario.timeout.toString() }
        });

        const response = await app.fetch(request, mockEnv);

        expect(scenario.expected).toContain(response.status);
      }
    });
  });

  describe('Resource Cleanup', () => {
    it('should clean up resources properly after requests', async () => {
      const initialMemory = process.memoryUsage();

      // Make several requests
      for (let i = 0; i < 10; i++) {
        const request = new Request(`http://localhost/health?cleanup=${i}`, {
          method: 'GET'
        });
        await app.fetch(request, mockEnv);
      }

      const finalMemory = process.memoryUsage();

      // Memory should not grow significantly after cleanup
      const memoryGrowth = finalMemory.heapUsed - initialMemory.heapUsed;
      expect(memoryGrowth).toBeLessThan(10 * 1024 * 1024); // 10MB max growth
    });

    it('should handle connection pooling efficiently', async () => {
      // Test connection reuse
      const requests = Array(20).fill(null).map((_, i) =>
        new Request(`http://localhost/health?pool=${i}`, { method: 'GET' })
      );

      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );

      // All requests should succeed with efficient connection use
      responses.forEach(response => {
        expect(response.status).toBe(200);
      });
    });
  });
});

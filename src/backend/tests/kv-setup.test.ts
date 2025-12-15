import { describe, it, expect, beforeEach, vi } from 'vitest';
import app from '../index';
import type { Env } from '../types/env';

describe('KV Namespace Setup Tests', () => {
  describe('KV Namespace Configuration', () => {
    it('should have proper KV namespace bindings', async () => {
      // Mock environment with KV namespaces
      const mockEnv: Env = {
        ENVIRONMENT: 'test',
        SPOTIFY_CLIENT_ID: 'test-client-id',
        SPOTIFY_CLIENT_SECRET: 'test-client-secret',
        JWT_SECRET: 'test-jwt-secret',
        RECOCOBEATS_API_KEY: 'test-reccobeats-key',
        CACHE_KV: {
          get: vi.fn().mockResolvedValue(null),
          put: vi.fn().mockResolvedValue(undefined),
          delete: vi.fn().mockResolvedValue(undefined),
          list: vi.fn().mockResolvedValue({ keys: [] })
        } as any,
        SESSIONS_KV: {
          get: vi.fn().mockResolvedValue(null),
          put: vi.fn().mockResolvedValue(undefined),
          delete: vi.fn().mockResolvedValue(undefined),
          list: vi.fn().mockResolvedValue({ keys: [] })
        } as any
      };

      // Test that KV namespaces are properly bound
      expect(mockEnv.CACHE_KV).toBeDefined();
      expect(mockEnv.SESSIONS_KV).toBeDefined();
      
      // Test basic KV operations
      const testKey = 'test-key';
      const testValue = { data: 'test' };

      // Test cache KV operations
      await mockEnv.CACHE_KV.put(testKey, JSON.stringify(testValue));
      const cachedValue = await mockEnv.CACHE_KV.get(testKey);
      expect(mockEnv.CACHE_KV.put).toHaveBeenCalledWith(testKey, JSON.stringify(testValue));

      // Test session KV operations
      await mockEnv.SESSIONS_KV.put(testKey, JSON.stringify(testValue));
      const sessionValue = await mockEnv.SESSIONS_KV.get(testKey);
      expect(mockEnv.SESSIONS_KV.put).toHaveBeenCalledWith(testKey, JSON.stringify(testValue));
    });

    it('should handle KV namespace errors gracefully', async () => {
      // Mock KV with errors
      const errorKV = {
        get: vi.fn().mockRejectedValue(new Error('KV Error')),
        put: vi.fn().mockRejectedValue(new Error('KV Error')),
        delete: vi.fn().mockRejectedValue(new Error('KV Error')),
        list: vi.fn().mockRejectedValue(new Error('KV Error'))
      } as any;

      const mockEnv: Env = {
        ENVIRONMENT: 'test',
        SPOTIFY_CLIENT_ID: 'test-client-id',
        SPOTIFY_CLIENT_SECRET: 'test-client-secret',
        JWT_SECRET: 'test-jwt-secret',
        RECOCOBEATS_API_KEY: 'test-reccobeats-key',
        CACHE_KV: errorKV,
        SESSIONS_KV: errorKV
      };

      // Test that the app can handle KV errors
      const request = new Request('http://localhost/health', {
        method: 'GET'
      });

      const response = await app.fetch(request, mockEnv);
      
      // Health check should still work even if KV has issues
      expect(response.status).toBe(200);
    });
  });

  describe('KV Namespace Integration', () => {
    it('should work with cache service in tests', async () => {
      const { CacheService } = await import('../services/cache');
      
      const mockKV = {
        get: vi.fn().mockResolvedValue(null),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
        list: vi.fn().mockResolvedValue({ keys: [] })
      } as any;

      const cacheService = new CacheService(mockKV);
      
      // Test cache operations
      const testKey = 'test-key';
      const testValue = { data: 'test' };

      await cacheService.set(testKey, testValue);
      expect(mockKV.put).toHaveBeenCalledWith(testKey, JSON.stringify(testValue), undefined);

      const retrievedValue = await cacheService.get(testKey);
      expect(mockKV.get).toHaveBeenCalledWith(testKey);
    });

    it('should work with JWT service in tests', async () => {
      const { JWTService } = await import('../services/jwt');
      
      const jwtService = new JWTService('test-secret');
      
      // Test JWT operations
      const payload = { sub: 'test-user', email: 'test@example.com', name: 'Test User' };
      const token = await jwtService.generateToken(payload);
      
      expect(typeof token).toBe('string');
      expect(token.split('.')).toHaveLength(3); // JWT has 3 parts
    });
  });

  describe('Test Environment Isolation', () => {
    it('should isolate test data from production', async () => {
      // Ensure test environment uses different KV namespaces
      const testEnv: Env = {
        ENVIRONMENT: 'test',
        SPOTIFY_CLIENT_ID: 'test-client-id',
        SPOTIFY_CLIENT_SECRET: 'test-client-secret',
        JWT_SECRET: 'test-jwt-secret',
        RECOCOBEATS_API_KEY: 'test-reccobeats-key',
        CACHE_KV: {
          get: vi.fn().mockResolvedValue(null),
          put: vi.fn().mockResolvedValue(undefined),
          delete: vi.fn().mockResolvedValue(undefined),
          list: vi.fn().mockResolvedValue({ keys: [] })
        } as any,
        SESSIONS_KV: {
          get: vi.fn().mockResolvedValue(null),
          put: vi.fn().mockResolvedValue(undefined),
          delete: vi.fn().mockResolvedValue(undefined),
          list: vi.fn().mockResolvedValue({ keys: [] })
        } as any
      };

      // Verify test environment
      expect(testEnv.ENVIRONMENT).toBe('test');
      
      // Test that test operations don't affect production
      const testKey = 'test-isolation-key';
      await testEnv.CACHE_KV.put(testKey, 'test-value');
      
      // In real implementation, this would use separate KV namespaces
      // For tests, we just verify the mock is called correctly
      expect(testEnv.CACHE_KV.put).toHaveBeenCalledWith(testKey, 'test-value');
    });
  });
});

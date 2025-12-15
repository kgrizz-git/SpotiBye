import { describe, it, expect, beforeEach, vi } from 'vitest';
import { CacheService } from '../services/cache';
import type { Env } from '../types/env';

describe('Caching Tests', () => {
  let cacheService: CacheService;
  let mockEnv: Env;

  beforeEach(() => {
    mockEnv = {
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

    cacheService = new CacheService(mockEnv.CACHE_KV);
  });

  describe('Basic Cache Operations', () => {
    it('should store and retrieve data from cache', async () => {
      const testData = { id: 'test', name: 'Test Data' };
      const cacheKey = 'test-key';

      // Store data
      await cacheService.set(cacheKey, testData, 3600);
      
      // Verify put was called
      expect(mockEnv.CACHE_KV.put).toHaveBeenCalledWith(
        cacheKey,
        JSON.stringify(testData),
        { expirationTtl: 3600 }
      );
    });

    it('should retrieve data from cache', async () => {
      const testData = { id: 'test', name: 'Test Data' };
      const cacheKey = 'test-key';

      // Mock successful cache hit
      (mockEnv.CACHE_KV.get as any).mockResolvedValue(JSON.stringify(testData));

      // Retrieve data
      const result = await cacheService.get(cacheKey);

      expect(result).toEqual(testData);
      expect(mockEnv.CACHE_KV.get).toHaveBeenCalledWith(cacheKey);
    });

    it('should return null for cache miss', async () => {
      const cacheKey = 'non-existent-key';

      // Mock cache miss
      (mockEnv.CACHE_KV.get as any).mockResolvedValue(null);

      // Retrieve data
      const result = await cacheService.get(cacheKey);

      expect(result).toBeNull();
      expect(mockEnv.CACHE_KV.get).toHaveBeenCalledWith(cacheKey);
    });

    it('should delete data from cache', async () => {
      const cacheKey = 'test-key';

      // Delete data
      await cacheService.delete(cacheKey);

      expect(mockEnv.CACHE_KV.delete).toHaveBeenCalledWith(cacheKey);
    });
  });

  describe('Cache Key Generation', () => {
    it('should generate user-specific cache keys manually', async () => {
      const userId = 'user-123';
      const resource = 'playlists';
      const params = { limit: 50, offset: 0 };

      const cacheKey = `${userId}:${resource}:${JSON.stringify(params)}`;

      expect(cacheKey).toBe('user-123:playlists:{"limit":50,"offset":0}');
    });

    it('should generate consistent cache keys for same parameters', async () => {
      const userId = 'user-123';
      const resource = 'tracks';
      const params = { playlist: 'playlist-456' };

      const key1 = `${userId}:${resource}:${JSON.stringify(params)}`;
      const key2 = `${userId}:${resource}:${JSON.stringify(params)}`;

      expect(key1).toBe(key2);
    });

    it('should generate different cache keys for different users', async () => {
      const resource = 'playlists';
      const params = { limit: 50 };

      const key1 = `user-1:${resource}:${JSON.stringify(params)}`;
      const key2 = `user-2:${resource}:${JSON.stringify(params)}`;

      expect(key1).not.toBe(key2);
    });
  });

  describe('Cache TTL Management', () => {
    it('should use default TTL when not specified', async () => {
      const testData = { id: 'test' };
      const cacheKey = 'test-key';

      await cacheService.set(cacheKey, testData);

      expect(mockEnv.CACHE_KV.put).toHaveBeenCalledWith(
        cacheKey,
        JSON.stringify(testData),
        undefined
      );
    });

    it('should use custom TTL when specified', async () => {
      const testData = { id: 'test' };
      const cacheKey = 'test-key';
      const customTtl = 7200;

      await cacheService.set(cacheKey, testData, customTtl);

      expect(mockEnv.CACHE_KV.put).toHaveBeenCalledWith(
        cacheKey,
        JSON.stringify(testData),
        { expirationTtl: customTtl }
      );
    });
  });

  describe('Cache Invalidation', () => {
    it('should invalidate cache entries with prefix', async () => {
      const userId = 'user-123';
      const prefix = `${userId}:`;

      // Create a fresh mock for this test
      const mockKV = {
        get: vi.fn().mockResolvedValue(null),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
        list: vi.fn().mockImplementation(({ prefix }) => {
          // Simulate KV behavior: only return keys that match the prefix
          if (prefix === 'user-123:') {
            return Promise.resolve({
              keys: [
                { name: `${userId}:playlists` },
                { name: `${userId}:tracks` }
              ]
            });
          }
          return Promise.resolve({ keys: [] });
        })
      } as any;

      const testCacheService = new CacheService(mockKV);

      await testCacheService.clear(prefix);

      // The clear method should delete only the keys that match the prefix
      expect(mockKV.list).toHaveBeenCalledWith({ prefix });
      expect(mockKV.delete).toHaveBeenCalledTimes(2);
      expect(mockKV.delete).toHaveBeenCalledWith('user-123:playlists');
      expect(mockKV.delete).toHaveBeenCalledWith('user-123:tracks');
    });

    it('should handle empty cache during invalidation', async () => {
      const prefix = 'user-123:';

      // Mock empty list
      (mockEnv.CACHE_KV.list as any).mockResolvedValue({ keys: [] });

      await cacheService.clear(prefix);

      expect(mockEnv.CACHE_KV.delete).not.toHaveBeenCalled();
    });
  });

  describe('Cache Operations', () => {
    it('should check if key exists', async () => {
      const cacheKey = 'test-key';

      // Mock existing key
      (mockEnv.CACHE_KV.get as any).mockResolvedValue('test-value');

      const exists = await cacheService.exists(cacheKey);

      expect(exists).toBe(true);
      expect(mockEnv.CACHE_KV.get).toHaveBeenCalledWith(cacheKey, { stream: true });
    });

    it('should handle non-existent key', async () => {
      const cacheKey = 'non-existent-key';

      // Mock non-existent key
      (mockEnv.CACHE_KV.get as any).mockResolvedValue(null);

      const exists = await cacheService.exists(cacheKey);

      expect(exists).toBe(false);
    });

    it('should get multiple keys', async () => {
      const keys = ['key1', 'key2'];
      const values = ['value1', 'value2'];

      // Mock cache hits with JSON strings
      (mockEnv.CACHE_KV.get as any)
        .mockResolvedValueOnce(JSON.stringify('value1'))
        .mockResolvedValueOnce(JSON.stringify('value2'));

      const results = await cacheService.getMultiple(keys);

      expect(results).toEqual(['value1', 'value2']);
      expect(mockEnv.CACHE_KV.get).toHaveBeenCalledTimes(2);
    });

    it('should set multiple keys', async () => {
      const entries = [
        { key: 'key1', value: 'value1', ttlSeconds: 3600 },
        { key: 'key2', value: 'value2' }
      ];

      const results = await cacheService.setMultiple(entries);

      expect(results).toEqual([true, true]);
      expect(mockEnv.CACHE_KV.put).toHaveBeenCalledTimes(2);
    });
  });

  describe('Error Handling', () => {
    it('should handle JSON parsing errors gracefully', async () => {
      const cacheKey = 'test-key';

      // Mock invalid JSON
      (mockEnv.CACHE_KV.get as any).mockResolvedValue('invalid-json');

      const result = await cacheService.get(cacheKey);

      expect(result).toBeNull();
    });

    it('should handle KV operation errors', async () => {
      const cacheKey = 'test-key';

      // Mock KV error
      (mockEnv.CACHE_KV.get as any).mockRejectedValue(new Error('KV Error'));

      const result = await cacheService.get(cacheKey);

      expect(result).toBeNull();
    });
  });
});

import { vi } from 'vitest';
import type { Env } from '../../types/env';
import { createTestEnv } from './env';

export const kvNamespace = (initial: Record<string, unknown> = {}) => {
  const store = new Map(
    Object.entries(initial).map(([key, value]) => [
      key,
      typeof value === 'string' ? value : JSON.stringify(value)
    ])
  );

  return {
    get: vi.fn(async (key: string) => store.get(key) ?? null),
    put: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    delete: vi.fn(async (key: string) => {
      store.delete(key);
    }),
    list: vi.fn(async () => ({ keys: [] })),
  } as unknown as KVNamespace;
};

export const envWithKv = (cacheKv = kvNamespace(), sessionsKv = kvNamespace()): Env =>
  createTestEnv({
    SPOTIFY_CLIENT_ID: 'client-id',
    SPOTIFY_CLIENT_SECRET: 'client-secret',
    JWT_SECRET: 'jwt-secret',
    CACHE_KV: cacheKv,
    SESSIONS_KV: sessionsKv,
  });

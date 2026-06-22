/**
 * Shared test environment factory for the backend.
 *
 * Centralizes the inline `mockEnv: Env` boilerplate that was previously
 * copy-pasted across 14+ test files. Adding a new field to `Env` (such as
 * `ALLOWED_REDIRECT_URIS`) should require updating only this helper rather
 * than every test mock.
 *
 * Usage:
 *   import { createTestEnv } from './helpers/env';
 *   const env = createTestEnv(); // uses defaults
 *   const env = createTestEnv({ ALLOWED_REDIRECT_URIS: '' }); // fail-closed
 */
import { vi } from 'vitest';
import type { Env } from '../../types/env';

export const TEST_ALLOWED_REDIRECT_URIS =
  'http://localhost:3000,http://localhost:3000/callback,http://localhost:8080';

export const createTestEnv = (overrides: Partial<Env> = {}): Env => {
  const baseEnv = {
    ENVIRONMENT: 'test',
    SPOTIFY_CLIENT_ID: 'test-client-id',
    SPOTIFY_CLIENT_SECRET: 'test-client-secret',
    JWT_SECRET: 'test-jwt-secret',
    ALLOWED_REDIRECT_URIS: TEST_ALLOWED_REDIRECT_URIS,
    CACHE_KV: {
      get: vi.fn(async () => null),
      getWithMetadata: vi.fn(async () => ({ value: null, metadata: null })),
      put: vi.fn(async () => undefined),
      delete: vi.fn(async () => undefined),
      list: vi.fn(async () => ({ keys: [] })),
    } as unknown as KVNamespace,
    SESSIONS_KV: {
      get: vi.fn(async () => null),
      getWithMetadata: vi.fn(async () => ({ value: null, metadata: null })),
      put: vi.fn(async () => undefined),
      delete: vi.fn(async () => undefined),
      list: vi.fn(async () => ({ keys: [] })),
    } as unknown as KVNamespace,
    ANALYSIS_QUEUE: {
      send: vi.fn(async () => undefined),
    } as unknown as Queue,
  };

  return { ...baseEnv, ...overrides } as Env;
};

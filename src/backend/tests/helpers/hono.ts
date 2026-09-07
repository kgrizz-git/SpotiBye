/**
 * Shared Hono route-test setup for backend tests.
 *
 * Centralizes the `app = new Hono(); app.route(…)` + `SESSIONS_KV` stub +
 * `Bearer test-jwt-token` request boilerplate copy-pasted across the route
 * test files (`analysis.test.ts`, `spotify.test.ts`, `export*.test.ts`).
 *
 * NOTE on `vi.mock('../middleware/auth', …)`: those blocks intentionally stay
 * inline in each test file. `vi.mock` factories are hoisted above imports, so
 * a shared wrapper (e.g. `mockAuthMiddleware()`) would either throw a
 * temporal-dead-zone error or silently run before helpers are initialized.
 * Only plain runtime code (route setup, request building) is shared here.
 */
import { Hono } from 'hono';
import type { Env as HonoEnv, Schema } from 'hono/types';
import { vi } from 'vitest';
import type { Env } from '../../types/env';
import { createTestEnv } from './env';

/** JWT convention used by every route test (`Authorization: Bearer …`). */
export const TEST_JWT_TOKEN = 'test-jwt-token';

export const buildAuthenticatedRequest = (path: string, init: RequestInit = {}): Request => {
  const headers = new Headers(init.headers);
  if (!headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${TEST_JWT_TOKEN}`);
  }
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return new Request(`http://localhost${path}`, { ...init, headers });
};

export interface RouteTestContext {
  app: Hono<{ Bindings: Env }>;
  env: Env;
}

/**
 * Fresh Hono app with `routes` mounted plus an env whose `SESSIONS_KV`
 * returns a canned session for `test-user-id`. Callers that need more
 * (e.g. an `AnalysisStatusStore`) build it from the returned `env`.
 */
export const setupRouteContext = <
  SubEnv extends HonoEnv,
  SubSchema extends Schema,
  SubBasePath extends string,
>(
  mountPath: string,
  routes: Hono<SubEnv, SubSchema, SubBasePath>,
): RouteTestContext => {
  const app = new Hono<{ Bindings: Env }>();
  app.route(mountPath, routes);
  const env: Env = {
    ...createTestEnv(),
    SESSIONS_KV: {
      get: vi.fn().mockResolvedValue(
        JSON.stringify({
          user_id: 'test-user-id',
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token',
          expires_at: Date.now() + 3600000,
        }),
      ),
      put: vi.fn().mockResolvedValue(undefined),
      delete: vi.fn().mockResolvedValue(undefined),
    } as unknown as KVNamespace,
  };
  return { app, env };
};

import { describe, it, expect, vi, afterEach } from 'vitest';
import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';
import { errorHandler } from '../middleware/error';
import { JWTService } from '../services/jwt';
import { kvNamespace, envWithKv } from './helpers/kv';
import type { Env } from '../types/env';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('authMiddleware concurrent token refresh deduplication', () => {
  it('deduplicates concurrent refresh calls and calls fetch only once', async () => {
    const app = new Hono<{ Bindings: Env }>();
    app.use('*', authMiddleware);
    app.get('/test', (c) => c.text('ok'));

    const sessionsKv = kvNamespace({
      'session-1': {
        user_id: 'user-1',
        access_token: 'old-access-token',
        refresh_token: 'refresh-token-1',
        expires_at: Date.now() - 1000,
      },
    });

    const env = envWithKv(kvNamespace(), sessionsKv);

    const jwtService = new JWTService(env.JWT_SECRET);
    const token = await jwtService.generateToken({
      sub: 'user-1',
      email: 'user1@example.com',
      name: 'User One',
      session_id: 'session-1',
    });

    let resolveFetch: (v: any) => void;
    const fetchPromise = new Promise<any>((r) => {
      resolveFetch = r;
    });

    const fetchMock = vi.fn().mockImplementation(() => fetchPromise);
    vi.stubGlobal('fetch', fetchMock);

    const reqPromise1 = app.request('/test', {
      headers: { Authorization: `Bearer ${token}` }
    }, env);

    const reqPromise2 = app.request('/test', {
      headers: { Authorization: `Bearer ${token}` }
    }, env);

    await new Promise((r) => queueMicrotask(r));

    resolveFetch!({
      ok: true,
      json: async () => ({
        access_token: 'refreshed-access-token',
        token_type: 'Bearer',
        expires_in: 3600,
        scope: 'user-read-private',
      }),
    });

    const [res1, res2] = await Promise.all([reqPromise1, reqPromise2]);

    expect(res1.status).toBe(200);
    expect(res2.status).toBe(200);
    expect(await res1.text()).toBe('ok');
    expect(await res2.text()).toBe('ok');

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const fetchMock2 = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: 'refreshed-access-token-2',
        token_type: 'Bearer',
        expires_in: 3600,
        scope: 'user-read-private',
      }),
    });
    vi.stubGlobal('fetch', fetchMock2);

    const sessionData = await sessionsKv.get('session-1');
    if (sessionData) {
      const session = JSON.parse(sessionData);
      session.expires_at = Date.now() - 1000;
      await sessionsKv.put('session-1', JSON.stringify(session));
    }

    const res3 = await app.request('/test', {
      headers: { Authorization: `Bearer ${token}` }
    }, env);

    expect(res3.status).toBe(200);
    expect(fetchMock2).toHaveBeenCalledTimes(1);
  });

  it('deduplicates concurrent refresh calls when Spotify returns invalid_grant', async () => {
    const app = new Hono<{ Bindings: Env }>();
    app.onError(errorHandler);
    app.use('*', authMiddleware);
    app.get('/test', (c) => c.text('ok'));

    const sessionsKv = kvNamespace({
      'session-1': {
        user_id: 'user-1',
        access_token: 'old-access-token',
        refresh_token: 'refresh-token-1',
        expires_at: Date.now() - 1000,
      },
    });
    const env = envWithKv(kvNamespace(), sessionsKv);

    const jwtService = new JWTService(env.JWT_SECRET);
    const token = await jwtService.generateToken({
      sub: 'user-1',
      email: 'user1@example.com',
      name: 'User One',
      session_id: 'session-1',
    });

    let resolveFetch: (v: unknown) => void;
    const fetchPromise = new Promise<unknown>((r) => {
      resolveFetch = r;
    });

    const fetchMock = vi.fn().mockImplementation(() => fetchPromise);
    vi.stubGlobal('fetch', fetchMock);

    const reqPromise1 = app.request('/test', {
      headers: { Authorization: `Bearer ${token}` },
    }, env);
    const reqPromise2 = app.request('/test', {
      headers: { Authorization: `Bearer ${token}` },
    }, env);

    await new Promise((r) => queueMicrotask(r));

    resolveFetch!({
      ok: false,
      text: async () => JSON.stringify({ error: 'invalid_grant' }),
    });

    const [res1, res2] = await Promise.all([reqPromise1, reqPromise2]);

    expect(res1.status).toBe(401);
    expect(res2.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(await sessionsKv.get('session-1')).toBeNull();
  });
});

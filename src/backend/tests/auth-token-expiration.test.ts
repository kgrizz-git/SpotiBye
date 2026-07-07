import { afterEach, describe, expect, it, vi } from 'vitest';
import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';
import { errorHandler } from '../middleware/error';
import { JWTService } from '../services/jwt';
import { SpotifyAuthService } from '../services/spotify-auth';
import { AuthRequiredException } from '../types/errors';
import { AnalysisJobService } from '../services/analysis-job';
import worker from '../index';
import { kvNamespace, envWithKv } from './helpers/kv';
import { createTestEnv } from './helpers/env';
import type { Env } from '../types/env';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const expiredSession = {
  user_id: 'user-1',
  access_token: 'old-access-token',
  refresh_token: 'refresh-token-1',
  expires_at: Date.now() - 1000,
};

async function bearerToken(env: Env, sessionId = 'session-1') {
  const jwtService = new JWTService(env.JWT_SECRET);
  return jwtService.generateToken({
    sub: 'user-1',
    email: 'user1@example.com',
    name: 'User One',
    session_id: sessionId,
  });
}

describe('Spotify token expiration — SpotifyAuthService', () => {
  it('throws AuthRequiredException when Spotify returns invalid_grant', async () => {
    const auth = new SpotifyAuthService('client-id', 'client-secret');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => JSON.stringify({ error: 'invalid_grant' }),
      }),
    );

    await expect(auth.refreshAccessToken('stale-refresh-token')).rejects.toBeInstanceOf(
      AuthRequiredException,
    );
  });
});

describe('Spotify token expiration — errorHandler', () => {
  it('preserves AUTH_REQUIRED code instead of mapping to UNAUTHORIZED', async () => {
    const app = new Hono<{ Bindings: Env }>();
    app.onError(errorHandler);
    app.get('/test', () => {
      throw new AuthRequiredException();
    });

    const res = await app.request('/test', undefined, createTestEnv());
    const body = (await res.json()) as { error: { code: string } };

    expect(res.status).toBe(401);
    expect(body.error.code).toBe('AUTH_REQUIRED');
  });
});

describe('Spotify token expiration — authMiddleware', () => {
  it('deletes KV session and returns AUTH_REQUIRED on invalid_grant', async () => {
    const app = new Hono<{ Bindings: Env }>();
    app.onError(errorHandler);
    app.use('*', authMiddleware);
    app.get('/test', (c) => c.text('ok'));

    const sessionsKv = kvNamespace({ 'session-1': expiredSession });
    const env = envWithKv(kvNamespace(), sessionsKv);
    const token = await bearerToken(env);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        text: async () => JSON.stringify({ error: 'invalid_grant' }),
      }),
    );

    const res = await app.request(
      '/test',
      { headers: { Authorization: `Bearer ${token}` } },
      env,
    );
    const body = (await res.json()) as { error: { code: string } };

    expect(res.status).toBe(401);
    expect(body.error.code).toBe('AUTH_REQUIRED');
    expect(await sessionsKv.get('session-1')).toBeNull();
    expect(sessionsKv.put).toHaveBeenCalledWith('REFRESH_FAILED:session-1', '1', {
      expirationTtl: 60,
    });
  });

  it('rejects immediately when REFRESH_FAILED negative cache is set (before fetch)', async () => {
    const app = new Hono<{ Bindings: Env }>();
    app.onError(errorHandler);
    app.use('*', authMiddleware);
    app.get('/test', (c) => c.text('ok'));

    const sessionsKv = kvNamespace({
      'session-1': expiredSession,
      'REFRESH_FAILED:session-1': '1',
    });
    const env = envWithKv(kvNamespace(), sessionsKv);
    const token = await bearerToken(env);

    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const res = await app.request(
      '/test',
      { headers: { Authorization: `Bearer ${token}` } },
      env,
    );
    const body = (await res.json()) as { error: { code: string } };

    expect(res.status).toBe(401);
    expect(body.error.code).toBe('AUTH_REQUIRED');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('deletes REFRESH_FAILED key after a successful refresh', async () => {
    const app = new Hono<{ Bindings: Env }>();
    app.onError(errorHandler);
    app.use('*', authMiddleware);
    app.get('/test', (c) => c.text('ok'));

    const sessionsKv = kvNamespace({
      'session-1': expiredSession,
    });
    const env = envWithKv(kvNamespace(), sessionsKv);
    const token = await bearerToken(env);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          access_token: 'refreshed-access-token',
          token_type: 'Bearer',
          expires_in: 3600,
          scope: 'user-read-private',
        }),
      }),
    );

    const res = await app.request(
      '/test',
      { headers: { Authorization: `Bearer ${token}` } },
      env,
    );

    expect(res.status).toBe(200);
    expect(sessionsKv.delete).toHaveBeenCalledWith('REFRESH_FAILED:session-1');
    expect(await sessionsKv.get('session-1')).toContain('refreshed-access-token');
  });

  it('returns 401 (not 500) when session JSON is malformed', async () => {
    const app = new Hono<{ Bindings: Env }>();
    app.onError(errorHandler);
    app.use('*', authMiddleware);
    app.get('/test', (c) => c.text('ok'));

    const sessionsKv = kvNamespace({ 'session-1': 'not-json' });
    const env = envWithKv(kvNamespace(), sessionsKv);
    const token = await bearerToken(env);

    const res = await app.request(
      '/test',
      { headers: { Authorization: `Bearer ${token}` } },
      env,
    );

    expect(res.status).toBe(401);
  });
});

describe('Spotify token expiration — analysis queue', () => {
  const analysisMessage = {
    job_id: 'job-1',
    playlist_id: 'playlist-1',
    user_id: 'user-1',
    session_id: 'session-1',
    enqueued_at: new Date().toISOString(),
    attempt: 1,
  };

  it('AnalysisJobService fails permanently when session is missing', async () => {
    const cacheKv = kvNamespace({
      'analysis:playlist-1:user-1:status': {
        job_id: 'job-1',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'queued',
        progress: 0,
      },
    });
    const service = new AnalysisJobService(envWithKv(cacheKv, kvNamespace()));

    await expect(service.process(analysisMessage)).rejects.toMatchObject({
      name: 'NonRetryableError',
      code: 'NON_RETRYABLE',
    });
  });

  it('queue consumer acks immediately on NonRetryableError without retrying', async () => {
    vi.spyOn(AnalysisJobService.prototype, 'process').mockRejectedValue(
      new (await import('../types/errors')).NonRetryableError(),
    );
    const markFailedSpy = vi
      .spyOn(AnalysisJobService.prototype, 'markFailed')
      .mockResolvedValue(undefined);

    const message = {
      id: 'message-1',
      timestamp: new Date(),
      body: analysisMessage,
      attempts: 1,
      ack: vi.fn(),
      retry: vi.fn(),
    };
    const batch = {
      queue: 'spotibye-analysis-dev',
      messages: [message],
      retryAll: vi.fn(),
      ackAll: vi.fn(),
    } as unknown as MessageBatch<typeof analysisMessage>;

    await worker.queue(batch, envWithKv(), {} as ExecutionContext);

    expect(markFailedSpy).toHaveBeenCalledTimes(1);
    expect(message.ack).toHaveBeenCalledTimes(1);
    expect(message.retry).not.toHaveBeenCalled();
  });
});

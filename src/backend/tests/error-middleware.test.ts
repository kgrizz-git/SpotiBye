import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { HTTPException } from 'hono/http-exception';
import { errorHandler } from '../middleware/error';
import { AuthRequiredException } from '../types/errors';
import type { Env } from '../types/env';
import { createTestEnv } from './helpers/env';

const setupErrorApp = (): { app: Hono<{ Bindings: Env }>; env: Env } => {
  const app = new Hono<{ Bindings: Env }>();
  app.onError(errorHandler);
  return { app, env: createTestEnv() };
};

const runErrorRequest = async (app: Hono<{ Bindings: Env }>, env: Env) => {
  const res = await app.request(new Request('http://localhost/test'), undefined, env);
  return {
    status: res.status,
    body: (await res.json()) as { error: { code: string; message: string } },
  };
};

describe('errorHandler discriminator strengthening (BL-6)', () => {
  let app: Hono<{ Bindings: Env }>;
  let env: Env;

  beforeEach(() => {
    vi.restoreAllMocks();
    ({ app, env } = setupErrorApp());
  });

  const runRequest = () => runErrorRequest(app, env);

  it('does not map a 3rd-party ValidationError to 400 (no code discriminator)', async () => {
    app.get('/test', () => {
      // 3rd-party style: name is ValidationError but no code field
      const err = new Error('something failed');
      err.name = 'ValidationError';
      throw err;
    });

    const { status, body } = await runRequest();
    expect(status).toBe(500);
    expect(body.error.code).toBe('INTERNAL_ERROR');
  });

  it('maps ValidationError with code=SCHEMA_VALIDATION to 400 (regex discriminator)', async () => {
    app.get('/test', () => {
      const err = new Error('schema validation failed') as Error & { code: string };
      err.name = 'ValidationError';
      err.code = 'SCHEMA_VALIDATION';
      throw err;
    });

    const { status, body } = await runRequest();
    expect(status).toBe(400);
    expect(body.error.code).toBe('VALIDATION_ERROR');
  });

  it('does not map a 3rd-party UnauthorizedError without a code to 401', async () => {
    app.get('/test', () => {
      const err = new Error('auth failed');
      err.name = 'UnauthorizedError';
      throw err;
    });

    const { status, body } = await runRequest();
    expect(status).toBe(500);
    expect(body.error.code).toBe('INTERNAL_ERROR');
  });

  it('maps UnauthorizedError with code=UNAUTHORIZED to 401', async () => {
    app.get('/test', () => {
      const err = new Error('unauthorized') as Error & { code: string };
      err.name = 'UnauthorizedError';
      err.code = 'UNAUTHORIZED';
      throw err;
    });

    const { status, body } = await runRequest();
    expect(status).toBe(401);
    expect(body.error.code).toBe('UNAUTHORIZED');
  });

  it('does not map a 3rd-party ForbiddenError without a code to 403', async () => {
    app.get('/test', () => {
      const err = new Error('forbidden');
      err.name = 'ForbiddenError';
      throw err;
    });

    const { status } = await runRequest();
    expect(status).toBe(500);
  });

  it('maps ForbiddenError with code=FORBIDDEN to 403', async () => {
    app.get('/test', () => {
      const err = new Error('forbidden') as Error & { code: string };
      err.name = 'ForbiddenError';
      err.code = 'FORBIDDEN';
      throw err;
    });

    const { status, body } = await runRequest();
    expect(status).toBe(403);
    expect(body.error.code).toBe('FORBIDDEN');
  });

  it('does not map a 3rd-party NotFoundError without a code to 404', async () => {
    app.get('/test', () => {
      const err = new Error('not found');
      err.name = 'NotFoundError';
      throw err;
    });

    const { status } = await runRequest();
    expect(status).toBe(500);
  });

  it('maps NotFoundError with code=NOT_FOUND to 404', async () => {
    app.get('/test', () => {
      const err = new Error('not found') as Error & { code: string };
      err.name = 'NotFoundError';
      err.code = 'NOT_FOUND';
      throw err;
    });

    const { status, body } = await runRequest();
    expect(status).toBe(404);
    expect(body.error.code).toBe('NOT_FOUND');
  });

  it('falls back to 500 for plain Error (no name match)', async () => {
    app.get('/test', () => {
      throw new Error('plain error');
    });

    const { status, body } = await runRequest();
    expect(status).toBe(500);
    expect(body.error.code).toBe('INTERNAL_ERROR');
  });
});

describe('errorHandler HTTPException branch (status code lookup table)', () => {
  let app: Hono<{ Bindings: Env }>;
  let env: Env;

  beforeEach(() => {
    vi.restoreAllMocks();
    ({ app, env } = setupErrorApp());
  });

  const runRequest = () => runErrorRequest(app, env);

  it.each([
    { status: 401, code: 'UNAUTHORIZED', message: 'bad token' },
    { status: 403, code: 'FORBIDDEN' },
    { status: 404, code: 'NOT_FOUND' },
  ])('maps HTTPException($status) to $code', async ({ status, code, message }) => {
    app.get('/test', () => {
      throw message
        ? new HTTPException(status as 401 | 403 | 404, { message })
        : new HTTPException(status as 401 | 403 | 404);
    });
    const { status: resStatus, body } = await runRequest();
    expect(resStatus).toBe(status);
    expect(body.error.code).toBe(code);
    if (message) {
      expect(body.error.message).toBe(message);
    }
  });

  it('maps HTTPException with unmapped status to HTTP_ERROR', async () => {
    app.get('/test', () => { throw new HTTPException(422); });
    const { status, body } = await runRequest();
    expect(status).toBe(422);
    expect(body.error.code).toBe('HTTP_ERROR');
  });

  it('maps AuthRequiredException (extends HTTPException 401) to AUTH_REQUIRED', async () => {
    app.get('/test', () => { throw new AuthRequiredException(); });
    const { status, body } = await runRequest();
    expect(status).toBe(401);
    expect(body.error.code).toBe('AUTH_REQUIRED');
  });
});

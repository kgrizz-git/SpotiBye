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

/** Registers `/test` to throw a named error (the mapping depends on name + code, never message). */
const throwNamedError = (
  app: Hono<{ Bindings: Env }>,
  name: string,
  message: string,
  code?: string,
): void => {
  app.get('/test', () => {
    const err = new Error(message) as Error & { code?: string };
    err.name = name;
    if (code !== undefined) {
      err.code = code;
    }
    throw err;
  });
};

describe('errorHandler discriminator strengthening (BL-6)', () => {
  let app: Hono<{ Bindings: Env }>;
  let env: Env;

  beforeEach(() => {
    vi.restoreAllMocks();
    ({ app, env } = setupErrorApp());
  });

  const runRequest = () => runErrorRequest(app, env);

  it.each([
    {
      title: 'does not map a 3rd-party ValidationError to 400 (no code discriminator)',
      name: 'ValidationError',
      message: 'something failed',
      code: undefined as string | undefined,
      status: 500,
      errorCode: 'INTERNAL_ERROR',
    },
    {
      title: 'maps ValidationError with code=SCHEMA_VALIDATION to 400 (regex discriminator)',
      name: 'ValidationError',
      message: 'schema validation failed',
      code: 'SCHEMA_VALIDATION' as string | undefined,
      status: 400,
      errorCode: 'VALIDATION_ERROR',
    },
    {
      title: 'does not map a 3rd-party UnauthorizedError without a code to 401',
      name: 'UnauthorizedError',
      message: 'auth failed',
      code: undefined as string | undefined,
      status: 500,
      errorCode: 'INTERNAL_ERROR',
    },
    {
      title: 'maps UnauthorizedError with code=UNAUTHORIZED to 401',
      name: 'UnauthorizedError',
      message: 'unauthorized',
      code: 'UNAUTHORIZED' as string | undefined,
      status: 401,
      errorCode: 'UNAUTHORIZED',
    },
    {
      title: 'does not map a 3rd-party ForbiddenError without a code to 403',
      name: 'ForbiddenError',
      message: 'forbidden',
      code: undefined as string | undefined,
      status: 500,
      errorCode: 'INTERNAL_ERROR',
    },
    {
      title: 'maps ForbiddenError with code=FORBIDDEN to 403',
      name: 'ForbiddenError',
      message: 'forbidden',
      code: 'FORBIDDEN' as string | undefined,
      status: 403,
      errorCode: 'FORBIDDEN',
    },
    {
      title: 'does not map a 3rd-party NotFoundError without a code to 404',
      name: 'NotFoundError',
      message: 'not found',
      code: undefined as string | undefined,
      status: 500,
      errorCode: 'INTERNAL_ERROR',
    },
    {
      title: 'maps NotFoundError with code=NOT_FOUND to 404',
      name: 'NotFoundError',
      message: 'not found',
      code: 'NOT_FOUND' as string | undefined,
      status: 404,
      errorCode: 'NOT_FOUND',
    },
    {
      title: 'falls back to 500 for plain Error (no name match)',
      name: 'Error',
      message: 'plain error',
      code: undefined as string | undefined,
      status: 500,
      errorCode: 'INTERNAL_ERROR',
    },
  ])('$title', async ({ name, message, code, status, errorCode }) => {
    throwNamedError(app, name, message, code);

    const { status: resStatus, body } = await runRequest();
    expect(resStatus).toBe(status);
    expect(body.error.code).toBe(errorCode);
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

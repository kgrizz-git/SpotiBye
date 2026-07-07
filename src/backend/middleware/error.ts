import type { ErrorHandler } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { HTTPException } from 'hono/http-exception';
import type { ErrorResponse } from '../types/api';
import { AuthRequiredException } from '../types/errors';

/**
 * Discriminator check for 3rd-party errors whose `err.name` string might
 * collide with our HTTP status code classes. SpotiBye does not throw any
 * of the names below directly; the discriminator field (`code` or
 * `statusCode`) must be present to avoid silently mapping 3rd-party
 * errors (e.g. pg/mongoose ValidationError, jsonwebtoken errors) to
 * the wrong HTTP status.
 */
function matchesStatus(err: Error, expected: string): boolean {
  const ext = err as { code?: unknown; statusCode?: unknown };
  return ext.code === expected || ext.statusCode === expected;
}

function isValidationCode(value: unknown): boolean {
  return typeof value === 'string' && /^[A-Z_]+_VALIDATION/i.test(value);
}

export const errorHandler: ErrorHandler = (err, c) => {
  console.error(JSON.stringify({
    event: 'ERROR_OCCURRED',
    error: err.message,
    name: err.name,
    path: c.req.path,
    method: c.req.method,
    timestamp: new Date().toISOString(),
  }));
  const requestId = crypto.randomUUID();

  // Default error response
  let status = 500;
  let message = 'Internal Server Error';
  let code = 'INTERNAL_ERROR';

  // Preserve explicit HTTP statuses thrown by middleware/routes (e.g. auth 401).
  if (err instanceof HTTPException) {
    status = err.status;
    message = err.message || message;
    code = err instanceof AuthRequiredException
      ? 'AUTH_REQUIRED'
      : status === 401
        ? 'UNAUTHORIZED'
        : status === 403
          ? 'FORBIDDEN'
          : status === 404
            ? 'NOT_FOUND'
            : 'HTTP_ERROR';
  } else if (
    err.name === 'ValidationError' &&
    isValidationCode((err as { code?: unknown }).code)
  ) {
    status = 400;
    message = err.message;
    code = 'VALIDATION_ERROR';
  } else if (err.name === 'UnauthorizedError' && matchesStatus(err, 'UNAUTHORIZED')) {
    status = 401;
    message = 'Unauthorized';
    code = 'UNAUTHORIZED';
  } else if (err.name === 'ForbiddenError' && matchesStatus(err, 'FORBIDDEN')) {
    status = 403;
    message = 'Forbidden';
    code = 'FORBIDDEN';
  } else if (err.name === 'NotFoundError' && matchesStatus(err, 'NOT_FOUND')) {
    status = 404;
    message = 'Not Found';
    code = 'NOT_FOUND';
  }

  const errorResponse: ErrorResponse = {
    error: {
      code,
      message,
      timestamp: new Date().toISOString(),
      request_id: requestId,
      details: {
        path: c.req.path,
        method: c.req.method,
      },
    },
  };

  return c.json(errorResponse, { status: status as ContentfulStatusCode });
};

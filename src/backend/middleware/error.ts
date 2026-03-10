import type { ErrorHandler } from 'hono';
import { HTTPException } from 'hono/http-exception';
import type { ErrorResponse } from '../types/api';

export const errorHandler: ErrorHandler = (err, c) => {
  console.error('Error occurred:', err);
  
  // Default error response
  let status = 500;
  let message = 'Internal Server Error';
  let code = 'INTERNAL_ERROR';
  
  // Preserve explicit HTTP statuses thrown by middleware/routes (e.g. auth 401).
  if (err instanceof HTTPException) {
    status = err.status;
    message = err.message || message;
    code = status === 401
      ? 'UNAUTHORIZED'
      : status === 403
        ? 'FORBIDDEN'
        : status === 404
          ? 'NOT_FOUND'
          : 'HTTP_ERROR';
  } else if (err.name === 'ValidationError') {
    status = 400;
    message = err.message;
    code = 'VALIDATION_ERROR';
  } else if (err.name === 'UnauthorizedError') {
    status = 401;
    message = 'Unauthorized';
    code = 'UNAUTHORIZED';
  } else if (err.name === 'ForbiddenError') {
    status = 403;
    message = 'Forbidden';
    code = 'FORBIDDEN';
  } else if (err.name === 'NotFoundError') {
    status = 404;
    message = 'Not Found';
    code = 'NOT_FOUND';
  }
  
  const errorResponse: ErrorResponse = {
    error: {
      code,
      message,
      timestamp: new Date().toISOString(),
    },
  };
  
  return c.json(errorResponse, status);
};

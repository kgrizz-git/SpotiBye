import { HTTPException } from 'hono/http-exception';

export class AuthRequiredException extends HTTPException {
  readonly code: string = 'AUTH_REQUIRED';
  constructor(message = 'Refresh token expired or revoked') {
    super(401, { message });
  }
}

export class NonRetryableError extends Error {
  readonly code = 'NON_RETRYABLE';
  constructor(message = 'Spotify session expired or revoked. Please sign in again.') {
    super(message);
    this.name = 'NonRetryableError';
  }
}

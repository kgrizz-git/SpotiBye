/**
 * Shared @hono/zod-validator wrapper that maps Zod failures to the app's
 * uniform `{ error: { code, message } }` envelope (see middleware/error.ts).
 */
import { zValidator as baseZValidator } from '@hono/zod-validator';
import type { ValidationTargets } from 'hono';
import type { ZodSchema } from 'zod';

function formatZodMessage(error: { issues: Array<{ path: Array<string | number>; message: string }> }): string {
  if (error.issues.length === 0) {
    return 'Request validation failed';
  }
  return error.issues
    .map((issue) => {
      const path = issue.path.length > 0 ? issue.path.join('.') : 'request';
      return `${path}: ${issue.message}`;
    })
    .join('; ');
}

/**
 * Wrap @hono/zod-validator so failures use the app's uniform error envelope.
 *
 * `code` defaults to the generic `VALIDATION_ERROR` but accepts a route-specific
 * code (e.g. `MISSING_REDIRECT_URI`, `INVALID_PLAYLISTS`) so existing API error
 * contracts are preserved when a route previously returned a specific code.
 */
export function zValidator<T extends ZodSchema>(
  target: keyof ValidationTargets,
  schema: T,
  code = 'VALIDATION_ERROR',
) {
  return baseZValidator(target, schema, (result, c) => {
    if (!result.success) {
      return c.json(
        {
          error: {
            code,
            message: formatZodMessage(result.error),
          },
        },
        400,
      );
    }
  });
}

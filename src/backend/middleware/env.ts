import type { MiddlewareHandler } from 'hono';
import type { Env } from '../types/env';
import { validateEnvBindings } from '../validation/schemas/env';

let envValidated = false;

/**
 * Fail fast when required Worker string bindings are missing or empty.
 * Runs once per isolate (Workers reuse isolates across requests).
 */
export const envValidationMiddleware: MiddlewareHandler<{ Bindings: Env }> = async (_c, next) => {
  if (!envValidated) {
    validateEnvBindings(_c.env);
    envValidated = true;
  }
  await next();
};

/** Reset validation flag for unit tests that swap env bindings between cases. */
export function resetEnvValidationForTests(): void {
  envValidated = false;
}

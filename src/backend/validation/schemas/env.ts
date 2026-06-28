import { z } from 'zod';
import type { Env } from '../../types/env';

/**
 * Validates string Worker bindings at the HTTP boundary. KV/Queue bindings are
 * runtime objects and are not schema-checked here.
 */
export const EnvBindingsSchema = z.object({
  ENVIRONMENT: z.string().min(1),
  RELEASE_SHA: z.string().optional(),
  RELEASE_VERSION: z.string().optional(),
  DEPLOYED_AT: z.string().optional(),
  SPOTIFY_CLIENT_ID: z.string().min(1),
  SPOTIFY_CLIENT_SECRET: z.string().min(1),
  JWT_SECRET: z.string().min(1),
  ALLOWED_REDIRECT_URIS: z.string(),
});

export function validateEnvBindings(env: Env): void {
  const result = EnvBindingsSchema.safeParse(env);
  if (!result.success) {
    const message = result.error.issues
      .map((issue) => `${issue.path.join('.')}: ${issue.message}`)
      .join('; ');
    throw new Error(`Invalid Worker environment bindings: ${message}`);
  }
}

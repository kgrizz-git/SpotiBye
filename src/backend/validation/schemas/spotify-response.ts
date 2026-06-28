import { z } from 'zod';

export function spotifyResponseShapeSchema(expectedKeys: string[]) {
  const shape = Object.fromEntries(
    expectedKeys.map((key) => [key, z.unknown()]),
  ) as Record<string, z.ZodUnknown>;
  return z.object(shape).passthrough();
}

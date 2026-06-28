import { z } from 'zod';

export const SessionDataSchema = z.object({
  user_id: z.string().min(1),
  access_token: z.string().min(1),
  refresh_token: z.string().optional(),
  expires_at: z.number(),
});

export type ParsedSessionData = z.infer<typeof SessionDataSchema>;

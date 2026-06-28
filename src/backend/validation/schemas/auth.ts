import { z } from 'zod';

export const SpotifyLoginBodySchema = z.object({
  redirect_uri: z.string().trim().min(1, 'redirect_uri is required'),
});

import { z } from 'zod';

/** Raw queue payload before `attempt` is overridden from `message.attempts`. */
export const AnalysisQueueMessagePayloadSchema = z.object({
  job_id: z.string().min(1),
  playlist_id: z.string().min(1),
  user_id: z.string().min(1),
  session_id: z.string().min(1),
  enqueued_at: z.string().min(1),
  attempt: z.number().int().nonnegative().optional(),
  force_enrichment: z.boolean().optional(),
});

export const AnalysisQueueMessageSchema = AnalysisQueueMessagePayloadSchema.extend({
  attempt: z.number().int().nonnegative(),
});

export type AnalysisQueueMessagePayload = z.infer<typeof AnalysisQueueMessagePayloadSchema>;

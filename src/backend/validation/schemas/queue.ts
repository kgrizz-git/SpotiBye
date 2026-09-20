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

/** Fan-out chunk payload: extends the base shape with chunk coordinates. */
export const AnalysisChunkMessagePayloadSchema = AnalysisQueueMessagePayloadSchema.extend({
  chunk_id: z.string().min(1),
  chunk_index: z.number().int().nonnegative(),
  chunk_count: z.number().int().positive(),
  track_ids: z.array(z.string().min(1)).min(1),
  artist_ids: z.array(z.string().min(1)),
  force_resolve: z.boolean().optional(),
});

export type AnalysisChunkMessagePayload = z.infer<typeof AnalysisChunkMessagePayloadSchema>;

/**
 * Parse a raw queue body, routing on `chunk_id` presence BEFORE validation:
 * the base schema strips unknown keys, so parsing base-first would silently
 * drop chunk coordinates. Returns the parsed payload tagged by shape.
 */
export function parseQueuePayload(
  body: unknown,
): { kind: 'chunk'; payload: AnalysisChunkMessagePayload } | { kind: 'single'; payload: AnalysisQueueMessagePayload } | { kind: 'invalid'; errors: unknown } {
  if (typeof body === 'object' && body !== null && 'chunk_id' in body) {
    const chunk = AnalysisChunkMessagePayloadSchema.safeParse(body);
    if (chunk.success) return { kind: 'chunk', payload: chunk.data };
    return { kind: 'invalid', errors: chunk.error.flatten() };
  }
  const single = AnalysisQueueMessagePayloadSchema.safeParse(body);
  if (single.success) return { kind: 'single', payload: single.data };
  return { kind: 'invalid', errors: single.error.flatten() };
}

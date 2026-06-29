import { z } from 'zod';

/**
 * Body schemas intentionally enforce ONLY the rules the routes enforced before
 * Zod was introduced — i.e. `playlist_ids` must be a non-empty array of
 * non-empty strings. For `ExportJobBodySchema` and `ExportBatchBodySchema`,
 * other fields (`format`, `include_audio_features`, etc.) are left permissive
 * and normalized downstream (`resolveRequestedFormat`, `resolveStepSize`,
 * clamping) exactly as before. `ExportBatchChunkBodySchema` is the exception:
 * it explicitly declares `cursor` / `chunk_size` / `job_id` as `z.any().optional()`
 * because the chunk route reads them directly (see the per-schema comment).
 */

const PlaylistIdsSchema = z
  .array(z.string().trim().min(1))
  .min(1, 'playlist_ids must contain at least one playlist id');

export const ExportJobBodySchema = z
  .object({ playlist_ids: PlaylistIdsSchema })
  .passthrough();

export const ExportBatchBodySchema = z
  .object({ playlist_ids: PlaylistIdsSchema })
  .passthrough();

// Explicitly declare passthrough fields accessed directly in handlers as z.any().optional().
// In Zod v4, `.passthrough()` types extra fields as `unknown` (rather than `any`), which
// prevents direct property access/comparison without explicit schema declaration.
export const ExportBatchChunkBodySchema = z
  .object({
    playlist_ids: PlaylistIdsSchema,
    cursor: z.any().optional(),
    chunk_size: z.any().optional(),
    job_id: z.any().optional(),
  })
  .passthrough();

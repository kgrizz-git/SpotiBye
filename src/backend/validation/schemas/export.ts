import { z } from 'zod';

/**
 * Body schemas intentionally enforce ONLY the rules the routes enforced before
 * Zod was introduced — i.e. `playlist_ids` must be a non-empty array of
 * non-empty strings. Other fields (`format`, `include_audio_features`,
 * `chunk_size`, etc.) are left permissive and normalized downstream
 * (`resolveRequestedFormat`, `resolveStepSize`, clamping) exactly as before, so
 * previously-accepted payloads (e.g. an unknown `format`) keep working.
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

export const ExportBatchChunkBodySchema = z
  .object({ playlist_ids: PlaylistIdsSchema })
  .passthrough();

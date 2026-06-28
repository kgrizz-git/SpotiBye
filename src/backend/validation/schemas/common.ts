import { z } from 'zod';

/** Non-empty path identifier (playlist id, track id, etc.). */
export const PathIdSchema = z.string().trim().min(1).max(256);

export const JobIdParamSchema = z.object({
  jobId: z.string().trim().min(1).max(256),
});

export const IdParamSchema = z.object({
  id: PathIdSchema,
});

export const PaginationQuerySchema = z.object({
  limit: z.coerce.number().int().min(1).max(50).optional().default(50),
  offset: z.coerce.number().int().min(0).optional().default(0),
});

export const ExportFormatSchema = z.enum(['csv', 'json', 'xlsx']);

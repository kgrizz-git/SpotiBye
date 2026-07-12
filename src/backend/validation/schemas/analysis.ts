import { z } from 'zod';

/** Optional JSON body for POST /analysis/playlist/:id */
export const AnalysisRequestSchema = z.object({
  force_enrichment: z.boolean().optional().default(false),
});

/** Query-string alternative for force_enrichment (matches force_refresh pattern). */
export const ForceEnrichmentQuerySchema = z.object({
  force_enrichment: z
    .string()
    .optional()
    .default('false')
    .transform((value) => value === 'true' || value === '1'),
});

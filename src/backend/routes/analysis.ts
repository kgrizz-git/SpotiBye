import { Hono } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { authMiddleware } from '../middleware/auth';
import { CacheService } from '../services/cache';
import { AnalysisStatusStore } from '../services/analysis-status-object';
import { ANALYSIS_SCHEMA_VERSION } from '../utils/constants';
import { compareVersions } from '../utils/version';
import type { AnalysisStatusRecord } from '../types/analysis-queue';
import type { AnalysisResult } from '../types/analysis';
import type { Env } from '../types/env';
import type { Variables } from '../types/variables';
import { zValidator } from '../validation/z-validator';
import { IdParamSchema } from '../validation/schemas/common';
import {
  AnalysisRequestSchema,
  ForceEnrichmentQuerySchema,
} from '../validation/schemas/analysis';

function isStaleAnalysisResult(results: AnalysisResult | null): boolean {
  return (
    !results ||
    typeof results.schema_version !== 'string' ||
    compareVersions(results.schema_version, ANALYSIS_SCHEMA_VERSION) < 0
  );
}

async function resolveForceEnrichment(
  c: { req: { valid: (target: 'query' | 'json') => { force_enrichment: boolean }; json: () => Promise<unknown> } },
  queryForce: boolean,
): Promise<boolean> {
  if (queryForce) {
    return true;
  }
  try {
    const raw = await c.req.json();
    const parsed = AnalysisRequestSchema.safeParse(raw);
    if (parsed.success) {
      return parsed.data.force_enrichment;
    }
  } catch {
    // Empty or non-JSON body — treat as default (no force).
  }
  return false;
}

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// POST /analysis/playlist/:id - Analyze playlist
// Optional `force_enrichment` (JSON body or query) bypasses idempotent
// completed/queued short-circuit and clears user status/results before enqueue.
app.post(
  '/playlist/:id',
  zValidator('param', IdParamSchema),
  zValidator('query', ForceEnrichmentQuerySchema),
  async (c) => {
  try {
    const { id: playlistId } = c.req.valid('param');
    const queryForce = c.req.valid('query').force_enrichment;
    const forceEnrichment = await resolveForceEnrichment(c, queryForce);
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const statusStore = new AnalysisStatusStore(c.env.ANALYSIS_STATUS);

    const resultsKey = `analysis:${playlistId}:${userId}:results`;
    const existingStatus = await statusStore.getStatus(userId, playlistId);

    if (existingStatus && !forceEnrichment) {
      const isQueued = existingStatus.status === 'queued';
      const isCompleted = existingStatus.status === 'completed';
      const isActivelyProcessing =
        (existingStatus.status === 'processing' || existingStatus.status === 'retrying') &&
        (!existingStatus.started_at ||
          Date.now() - new Date(existingStatus.started_at).getTime() < 300_000);

      if (isCompleted) {
        const results = await cacheService.get<AnalysisResult>(resultsKey);
        // Serve whatever is cached: completed fresh-schema results are
        // returned even when enrichment is partial (upstream gaps may never
        // fill — re-running the whole job every open can never complete
        // them). Gap-filling is the frontend miss-fill's job; only stale
        // results trigger a fresh job here.
        if (!isStaleAnalysisResult(results) && results) {
          return c.json({
            data: existingStatus,
            meta: { timestamp: new Date().toISOString() }
          });
        }
        await Promise.all([
          statusStore.deleteStatus(userId, playlistId),
          cacheService.delete(resultsKey),
        ]);
      } else if (isQueued || isActivelyProcessing) {
        return c.json({
          data: existingStatus,
          meta: { timestamp: new Date().toISOString() }
        });
      }
    } else if (existingStatus && forceEnrichment) {
      await Promise.all([
        statusStore.deleteStatus(userId, playlistId),
        cacheService.delete(resultsKey),
      ]);
    }

    const jobId = crypto.randomUUID();
    const now = new Date().toISOString();
    const status: AnalysisStatusRecord = {
      job_id: jobId,
      playlist_id: playlistId,
      user_id: userId,
      status: 'queued',
      queued_at: now,
      progress: 0,
    };

    await statusStore.writeStatus(userId, playlistId, status);

    const queuePayload: {
      job_id: string;
      playlist_id: string;
      user_id: string;
      session_id: string;
      enqueued_at: string;
      attempt: number;
      force_enrichment?: boolean;
    } = {
      job_id: jobId,
      playlist_id: playlistId,
      user_id: userId,
      session_id: c.get('session_id'),
      enqueued_at: now,
      attempt: 0,
    };
    if (forceEnrichment) {
      queuePayload.force_enrichment = true;
    }

    await c.env.ANALYSIS_QUEUE.send(queuePayload);

    return c.json({
      data: status,
      meta: { timestamp: new Date().toISOString() }
    });
  } catch (error) {
    console.error('Failed to start analysis:', error);
    return c.json({ error: { code: 'ANALYSIS_START_FAILED', message: 'Failed to start analysis' } }, { status: 500 as ContentfulStatusCode });
  }
},
);

// GET /analysis/playlist/:id/status - Get analysis status
app.get('/playlist/:id/status', zValidator('param', IdParamSchema), async (c) => {
  try {
    const { id: playlistId } = c.req.valid('param');
    const userId = c.get('user').id;
    const statusStore = new AnalysisStatusStore(c.env.ANALYSIS_STATUS);
    const status = await statusStore.getStatus(userId, playlistId);

    if (!status) {
      return c.json({ error: { code: 'ANALYSIS_NOT_FOUND', message: 'Analysis not found' } }, { status: 404 as ContentfulStatusCode });
    }

    return c.json({ data: status, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get analysis status:', error);
    return c.json({ error: { code: 'ANALYSIS_STATUS_FAILED', message: 'Failed to get analysis status' } }, { status: 500 as ContentfulStatusCode });
  }
});

// GET /analysis/playlist/:id/results - Get analysis results
app.get('/playlist/:id/results', zValidator('param', IdParamSchema), async (c) => {
  try {
    const { id: playlistId } = c.req.valid('param');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const resultsKey = `analysis:${playlistId}:${userId}:results`;
    const results = await cacheService.get<AnalysisResult>(resultsKey);

    if (!results) {
      return c.json({ error: { code: 'ANALYSIS_RESULTS_NOT_FOUND', message: 'Analysis results not found' } }, { status: 404 as ContentfulStatusCode });
    }

    if (isStaleAnalysisResult(results)) {
      const statusKey = `analysis:${playlistId}:${userId}:status`;
      const statusStore = new AnalysisStatusStore(c.env.ANALYSIS_STATUS);
      await Promise.all([
        cacheService.delete(resultsKey),
        cacheService.delete(statusKey),
        statusStore.deleteStatus(userId, playlistId),
      ]);
      return c.json({ error: { code: 'ANALYSIS_RESULTS_NOT_FOUND', message: 'Analysis results not found' } }, { status: 404 as ContentfulStatusCode });
    }

    return c.json({ data: results, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get analysis results:', error);
    return c.json({ error: { code: 'ANALYSIS_RESULTS_FAILED', message: 'Failed to get analysis results' } }, { status: 500 as ContentfulStatusCode });
  }
});

// DELETE /analysis/playlist/:id - Delete analysis
app.delete('/playlist/:id', zValidator('param', IdParamSchema), async (c) => {
  try {
    const { id: playlistId } = c.req.valid('param');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const statusStore = new AnalysisStatusStore(c.env.ANALYSIS_STATUS);

    const resultsKey = `analysis:${playlistId}:${userId}:results`;
    // Stopgap: clears legacy playlist-scoped raw-enrichment blob if present.
    // Global per-track keys (`global:reccobeats:*`) are intentionally NOT cleared.
    const rawEnrichmentKey = `analysis:playlist:${playlistId}:raw-enrichment`;

    await Promise.all([
      statusStore.deleteStatus(userId, playlistId),
      cacheService.delete(resultsKey),
      cacheService.delete(rawEnrichmentKey),
    ]);

    return c.json({ data: { message: 'Analysis deleted successfully' } });
  } catch (error) {
    console.error('Failed to delete analysis:', error);
    return c.json({ error: { code: 'ANALYSIS_DELETE_FAILED', message: 'Failed to delete analysis' } }, { status: 500 as ContentfulStatusCode });
  }
});

export { app as analysisRoutes };

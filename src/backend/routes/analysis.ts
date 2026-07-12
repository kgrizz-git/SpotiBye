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

function isStaleAnalysisResult(results: AnalysisResult | null): boolean {
  return (
    !results ||
    typeof results.schema_version !== 'string' ||
    compareVersions(results.schema_version, ANALYSIS_SCHEMA_VERSION) < 0
  );
}

/** True when completed results still have unresolved ReccoBeats endpoint coverage. */
function isEnrichmentIncomplete(results: AnalysisResult): boolean {
  const unique = results.unique_track_count ?? 0;
  if (unique <= 0) {
    return false;
  }
  const audioResolved = results.audio_features_resolved_count ?? 0;
  const metadataResolved = results.track_metadata_resolved_count ?? 0;
  return audioResolved < unique || metadataResolved < unique;
}

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// POST /analysis/playlist/:id - Analyze playlist
// NOTE: the request body (see openapi.yaml AnalysisRequest) is intentionally
// ignored — analysis always runs with default settings. Never parsed here.
app.post('/playlist/:id', zValidator('param', IdParamSchema), async (c) => {
  try {
    const { id: playlistId } = c.req.valid('param');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const statusStore = new AnalysisStatusStore(c.env.ANALYSIS_STATUS);

    // Check if analysis is already in progress or completed
    const resultsKey = `analysis:${playlistId}:${userId}:results`;
    const existingStatus = await statusStore.getStatus(userId, playlistId);

    if (existingStatus) {
      // completed: return cached result, unless the results are stale (missing
      // or from an older schema_version), in which case fall through and
      // enqueue a fresh job instead of serving data the frontend can't render.
      // queued: return while waiting for the queue consumer
      // processing/retrying: return if started within last 5 minutes (still running)
      // failed/anything else: restart
      const isQueued = existingStatus.status === 'queued';
      const isCompleted = existingStatus.status === 'completed';
      const isActivelyProcessing =
        (existingStatus.status === 'processing' || existingStatus.status === 'retrying') &&
        (!existingStatus.started_at ||
          Date.now() - new Date(existingStatus.started_at).getTime() < 300_000);

      if (isCompleted) {
        const results = await cacheService.get<AnalysisResult>(resultsKey);
        if (!isStaleAnalysisResult(results) && results && !isEnrichmentIncomplete(results)) {
          return c.json({
            data: existingStatus,
            meta: { timestamp: new Date().toISOString() }
          });
        }
        await Promise.all([
          statusStore.deleteStatus(userId, playlistId),
          cacheService.delete(resultsKey),
        ]);
        // Falls through to enqueue a fresh job below.
      } else if (isQueued || isActivelyProcessing) {
        return c.json({
          data: existingStatus,
          meta: { timestamp: new Date().toISOString() }
        });
      }
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

    await c.env.ANALYSIS_QUEUE.send({
      job_id: jobId,
      playlist_id: playlistId,
      user_id: userId,
      session_id: c.get('session_id'),
      enqueued_at: now,
      attempt: 0,
    });

    return c.json({
      data: status,
      meta: { timestamp: new Date().toISOString() }
    });
  } catch (error) {
    console.error('Failed to start analysis:', error);
    return c.json({ error: { code: 'ANALYSIS_START_FAILED', message: 'Failed to start analysis' } }, { status: 500 as ContentfulStatusCode });
  }
});

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

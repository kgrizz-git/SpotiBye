import { Hono } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { authMiddleware } from '../middleware/auth';
import { AnalysisService } from '../services/analysis';
import { CacheService } from '../services/cache';
import type { Env } from '../types/env';
import type { Variables } from '../types/variables';

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// POST /analysis/playlist/:id - Analyze playlist
app.post('/playlist/:id', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');

    const analysisService = new AnalysisService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);

    // Check if analysis is already in progress or completed
    const statusKey = `analysis:${playlistId}:${userId}:status`;
    const existingStatus = await cacheService.get<Record<string, unknown>>(statusKey);

    if (existingStatus) {
      const s = existingStatus as Record<string, unknown>;
      // completed: always return cached result
      // processing: return if started within last 5 minutes (still running)
      // pending/failed/anything else: restart
      const isCompleted = s.status === 'completed';
      const isActivelyProcessing =
        s.status === 'processing' &&
        (typeof s.started_at !== 'string' ||
          Date.now() - new Date(s.started_at).getTime() < 300_000);

      if (isCompleted || isActivelyProcessing) {
        return c.json({
          data: existingStatus,
          meta: { timestamp: new Date().toISOString() }
        });
      }
    }

    // Start analysis
    const jobId = crypto.randomUUID();
    const status = {
      job_id: jobId,
      playlist_id: playlistId,
      user_id: userId,
      status: 'processing',
      started_at: new Date().toISOString(),
      progress: 0
    };

    await cacheService.set(statusKey, status, 3600);

    const resultsKey = `analysis:${playlistId}:${userId}:results`;

    const analysisPromise = analysisService.analyzePlaylist(playlistId, userId, jobId)
      .then(async (result) => {
        await cacheService.set(resultsKey, result, 86400);
        await cacheService.set(statusKey, {
          ...status,
          status: 'completed',
          completed_at: new Date().toISOString()
        }, 3600);
      })
      .catch(async (error) => {
        console.error('Analysis failed:', error);
        await cacheService.set(statusKey, {
          ...status,
          status: 'failed',
          error: error.message,
          completed_at: new Date().toISOString()
        }, 3600);
      });

    try {
      c.executionCtx.waitUntil(analysisPromise);
    } catch {
      // executionCtx unavailable outside Cloudflare Workers runtime — promise runs detached
    }

    return c.json({
      data: { ...status, status: 'processing' },
      meta: { timestamp: new Date().toISOString() }
    });
  } catch (error) {
    console.error('Failed to start analysis:', error);
    return c.json({ error: { code: 'ANALYSIS_START_FAILED', message: 'Failed to start analysis' } }, { status: 500 as ContentfulStatusCode });
  }
});

// GET /analysis/playlist/:id/status - Get analysis status
app.get('/playlist/:id/status', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const statusKey = `analysis:${playlistId}:${userId}:status`;
    const status = await cacheService.get(statusKey);

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
app.get('/playlist/:id/results', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const resultsKey = `analysis:${playlistId}:${userId}:results`;
    const results = await cacheService.get(resultsKey);

    if (!results) {
      return c.json({ error: { code: 'ANALYSIS_RESULTS_NOT_FOUND', message: 'Analysis results not found' } }, { status: 404 as ContentfulStatusCode });
    }

    return c.json({ data: results, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get analysis results:', error);
    return c.json({ error: { code: 'ANALYSIS_RESULTS_FAILED', message: 'Failed to get analysis results' } }, { status: 500 as ContentfulStatusCode });
  }
});

// DELETE /analysis/playlist/:id - Delete analysis
app.delete('/playlist/:id', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const statusKey = `analysis:${playlistId}:${userId}:status`;
    const resultsKey = `analysis:${playlistId}:${userId}:results`;

    await Promise.all([
      cacheService.delete(statusKey),
      cacheService.delete(resultsKey)
    ]);

    return c.json({ data: { message: 'Analysis deleted successfully' } });
  } catch (error) {
    console.error('Failed to delete analysis:', error);
    return c.json({ error: { code: 'ANALYSIS_DELETE_FAILED', message: 'Failed to delete analysis' } }, { status: 500 as ContentfulStatusCode });
  }
});

export { app as analysisRoutes };

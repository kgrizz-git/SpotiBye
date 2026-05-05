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

    if (existingStatus && (existingStatus as Record<string, unknown>)?.status !== 'failed') {
      return c.json({
        data: existingStatus,
        meta: { timestamp: new Date().toISOString() }
      });
    }

    // Start analysis
    const jobId = crypto.randomUUID();
    const status = {
      job_id: jobId,
      playlist_id: playlistId,
      user_id: userId,
      status: 'pending',
      started_at: new Date().toISOString(),
      progress: 0
    };

    await cacheService.set(statusKey, status, 3600); // 1 hour TTL

    // Start async analysis (in Workers, this would typically use a Durable Object or Queue)
    // For now, we'll start it synchronously but mark it as async
    analysisService.analyzePlaylist(playlistId, userId, jobId).catch(error => {
      console.error('Analysis failed:', error);
      // Update status to failed
      cacheService.set(statusKey, {
        ...status,
        status: 'failed',
        error: error.message,
        completed_at: new Date().toISOString()
      }, 3600);
    });

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

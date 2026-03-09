import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';
import { ExportService } from '../services/export';
import { CacheService } from '../services/cache';
import type { Env } from '../types/env';

const app = new Hono<{ Bindings: Env }>();

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// POST /export/playlist/:id - Generate Excel export
app.post('/playlist/:id', async (c) => {
  const requestId = crypto.randomUUID();
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    
    const exportService = new ExportService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);
    console.info('[export] start', { requestId, userId, playlistId });
    
    // Check if export already exists
    const exportKey = `export:${playlistId}:${userId}`;
    const existingExport = await cacheService.get(exportKey);
    
    if (existingExport && existingExport.status === 'completed') {
      console.info('[export] using cached completed export', { requestId, userId, playlistId, exportKey });
      return c.json({ 
        data: existingExport,
        meta: { timestamp: new Date().toISOString(), request_id: requestId }
      });
    }
    
    // Start export process
    const jobId = crypto.randomUUID();
    const status = {
      job_id: jobId,
      playlist_id: playlistId,
      user_id: userId,
      status: 'processing',
      started_at: new Date().toISOString(),
      progress: 0
    };
    
    await cacheService.set(exportKey, status, 3600); // 1 hour TTL
    
    try {
      // Generate the export
      const exportData = await exportService.generatePlaylistExport(playlistId);
      
      // Store the export data (in production, this would be stored in R2 or similar)
      const completedStatus = {
        ...status,
        status: 'completed',
        completed_at: new Date().toISOString(),
        progress: 100,
        file_url: `/export/playlist/${playlistId}/download`,
        file_size: exportData.length,
        track_count: exportData.tracks.length
      };
      
      await cacheService.set(exportKey, completedStatus, 3600);
      await cacheService.set(`${exportKey}:data`, exportData, 3600);

      console.info('[export] completed', {
        requestId,
        userId,
        playlistId,
        trackCount: exportData.tracks.length,
      });
      
      return c.json({ 
        data: completedStatus,
        meta: { timestamp: new Date().toISOString(), request_id: requestId }
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      const failedStatus = {
        ...status,
        status: 'failed',
        error: errorMessage,
        completed_at: new Date().toISOString()
      };

      console.error('[export] generation failed', {
        requestId,
        userId,
        playlistId,
        error: errorMessage,
      });
      
      await cacheService.set(exportKey, failedStatus, 3600);
      
      return c.json(
        {
          error: {
            code: 'EXPORT_FAILED',
            message: `Failed to generate export: ${errorMessage}`,
            request_id: requestId,
            details: {
              playlist_id: playlistId,
              user_id: userId,
            },
          },
        },
        500
      );
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('Failed to start export:', { requestId, error });
    return c.json(
      {
        error: {
          code: 'EXPORT_START_FAILED',
          message: `Failed to start export: ${errorMessage}`,
          request_id: requestId,
        },
      },
      500
    );
  }
});

// GET /export/playlist/:id/status - Get export status
app.get('/playlist/:id/status', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    
    const exportKey = `export:${playlistId}:${userId}`;
    const status = await cacheService.get(exportKey);
    
    if (!status) {
      return c.json({ error: { code: 'EXPORT_NOT_FOUND', message: 'Export not found' } }, 404);
    }
    
    return c.json({ data: status, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get export status:', error);
    return c.json({ error: { code: 'EXPORT_STATUS_FAILED', message: 'Failed to get export status' } }, 500);
  }
});

// GET /export/playlist/:id/download - Download generated file
app.get('/playlist/:id/download', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    
    const exportKey = `export:${playlistId}:${userId}`;
    const exportData = await cacheService.get(`${exportKey}:data`);
    
    if (!exportData) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Export data not found' } }, 404);
    }
    
    // Generate Excel file content
    const excelContent = await new ExportService(c.get('access_token')).generateExcelFile(exportData);
    
    // Set headers for file download
    const filename = `playlist_${playlistId}_export_${Date.now()}.xlsx`;
    c.header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    c.header('Content-Disposition', `attachment; filename="${filename}"`);
    
    return new Response(excelContent);
  } catch (error) {
    console.error('Failed to download export:', error);
    return c.json({ error: { code: 'EXPORT_DOWNLOAD_FAILED', message: 'Failed to download export' } }, 500);
  }
});

// DELETE /export/playlist/:id - Delete export
app.delete('/playlist/:id', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    
    const exportKey = `export:${playlistId}:${userId}`;
    
    await Promise.all([
      cacheService.delete(exportKey),
      cacheService.delete(`${exportKey}:data`)
    ]);
    
    return c.json({ data: { message: 'Export deleted successfully' } });
  } catch (error) {
    console.error('Failed to delete export:', error);
    return c.json({ error: { code: 'EXPORT_DELETE_FAILED', message: 'Failed to delete export' } }, 500);
  }
});

export { app as exportRoutes };

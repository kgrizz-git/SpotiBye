import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';
import { ExportService } from '../services/export';
import { CacheService } from '../services/cache';
import type { Env } from '../types/env';

const app = new Hono<{ Bindings: Env }>();

function resolveRequestedFormat(body: any): 'xlsx' | 'csv' {
  return body && body.format === 'csv' ? 'csv' : 'xlsx';
}

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// POST /export/playlist/:id - Generate playlist export
app.post('/playlist/:id', async (c) => {
  const requestId = crypto.randomUUID();
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const body = await c.req.json().catch(() => ({}));
    const requestedFormat = resolveRequestedFormat(body);
    
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
        file_format: requestedFormat,
        file_size: JSON.stringify(exportData).length,
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

// POST /export/playlists - Generate combined export for multiple playlists
app.post('/playlists', async (c) => {
  const requestId = crypto.randomUUID();
  try {
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const body = await c.req.json().catch(() => ({}));
    const playlistIds: string[] = Array.isArray(body?.playlist_ids)
      ? body.playlist_ids.filter((id: unknown) => typeof id === 'string' && id.trim().length > 0)
      : [];
    const requestedFormat = resolveRequestedFormat(body);

    if (playlistIds.length === 0) {
      return c.json({ error: { code: 'INVALID_PLAYLISTS', message: 'playlist_ids must contain at least one playlist id' } }, 400);
    }

    const exportService = new ExportService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);
    const jobId = crypto.randomUUID();
    const batchKey = `export:batch:${jobId}:${userId}`;

    console.info('[export-batch] start', {
      requestId,
      userId,
      playlistCount: playlistIds.length,
      jobId,
    });

    const exportDataList = [];
    for (const playlistId of playlistIds) {
      const exportData = await exportService.generatePlaylistExport(playlistId);
      exportDataList.push(exportData);
    }

    const totalTracks = exportDataList.reduce((sum, item) => sum + item.tracks.length, 0);
    const status = {
      job_id: jobId,
      user_id: userId,
      status: 'completed',
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      progress: 100,
      file_url: `/export/playlists/${jobId}/download`,
      file_format: requestedFormat,
      file_size: JSON.stringify(exportDataList).length,
      playlist_count: exportDataList.length,
      track_count: totalTracks,
      playlist_ids: playlistIds,
    };

    await cacheService.set(batchKey, status, 3600);
    await cacheService.set(`${batchKey}:data`, exportDataList, 3600);

    console.info('[export-batch] completed', {
      requestId,
      userId,
      playlistCount: exportDataList.length,
      totalTracks,
      jobId,
    });

    return c.json({
      data: status,
      meta: { timestamp: new Date().toISOString(), request_id: requestId }
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('[export-batch] failed', { requestId, error: errorMessage });
    return c.json(
      {
        error: {
          code: 'EXPORT_BATCH_FAILED',
          message: `Failed to generate combined export: ${errorMessage}`,
          request_id: requestId,
        },
      },
      500
    );
  }
});

// GET /export/playlists/:jobId/download - Download combined generated file
app.get('/playlists/:jobId/download', async (c) => {
  try {
    const jobId = c.req.param('jobId');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const batchKey = `export:batch:${jobId}:${userId}`;
    const exportStatus = await cacheService.get(batchKey);
    const exportDataList = await cacheService.get(`${batchKey}:data`);

    if (!exportStatus || !exportDataList || !Array.isArray(exportDataList) || exportDataList.length === 0) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Combined export data not found' } }, 404);
    }

    const exportService = new ExportService(c.get('access_token'));
    const fileFormat = exportStatus.file_format === 'csv' ? 'csv' : 'xlsx';

    if (fileFormat === 'csv') {
      const chunks: string[] = [];
      for (const item of exportDataList) {
        const csvBytes = await exportService.generateCsvFile(item);
        const csvText = new TextDecoder().decode(csvBytes);
        chunks.push(csvText);
      }
      const combined = chunks.join('\n\n');
      const filename = `playlists_export_${Date.now()}.csv`;
      return new Response(combined, {
        headers: {
          'Content-Type': 'text/csv; charset=utf-8',
          'Content-Disposition': `attachment; filename="${filename}"`,
        },
      });
    }

    const xlsxContent = await exportService.generateCombinedExcelFile(exportDataList);
    const filename = `playlists_export_${Date.now()}.xlsx`;
    return new Response(xlsxContent, {
      headers: {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });
  } catch (error) {
    console.error('Failed to download combined export:', error);
    return c.json({ error: { code: 'EXPORT_DOWNLOAD_FAILED', message: 'Failed to download combined export' } }, 500);
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
    const exportStatus = await cacheService.get(exportKey);
    
    if (!exportData) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Export data not found' } }, 404);
    }
    
    const exportService = new ExportService(c.get('access_token'));
    const fileFormat = exportStatus && exportStatus.file_format === 'csv' ? 'csv' : 'xlsx';

    if (fileFormat === 'csv') {
      const csvContent = await exportService.generateCsvFile(exportData);
      const filename = `playlist_${playlistId}_export_${Date.now()}.csv`;
      return new Response(csvContent, {
        headers: {
          'Content-Type': 'text/csv; charset=utf-8',
          'Content-Disposition': `attachment; filename="${filename}"`,
        },
      });
    }

    const xlsxContent = await exportService.generateExcelFile(exportData);
    const filename = `playlist_${playlistId}_export_${Date.now()}.xlsx`;
    return new Response(xlsxContent, {
      headers: {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });
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

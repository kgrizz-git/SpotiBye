import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';
import { ExportService } from '../services/export';
import { CacheService } from '../services/cache';
import type { Env } from '../types/env';

const app = new Hono<{ Bindings: Env }>();

type BatchExportStatus = {
  job_id: string;
  user_id: string;
  status: 'processing' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  progress: number;
  file_url?: string;
  file_format: 'xlsx' | 'csv';
  file_size?: number;
  playlist_count: number;
  processed_count: number;
  track_count: number;
  playlist_ids: string[];
  next_cursor: number;
  continuation_required: boolean;
  error?: string;
};

function resolveRequestedFormat(body: any): 'xlsx' | 'csv' {
  return body && body.format === 'csv' ? 'csv' : 'xlsx';
}

function resolveIncludeAudioFeatures(body: any): boolean {
  return body?.include_audio_features === true;
}

function resolveErrorStatus(code: string, message: string): number {
  if (/cpu time limit|exceeded cpu/i.test(message)) {
    return 503;
  }
  if (/HTTP\s+401/i.test(message)) {
    return 401;
  }
  if (/HTTP\s+429/i.test(message)) {
    return 429;
  }
  return code.includes('DOWNLOAD') ? 503 : 500;
}

function parseUpstreamStatus(errorMessage: string): number | undefined {
  const match = /HTTP\s+(\d{3})/i.exec(errorMessage);
  if (!match) {
    return undefined;
  }
  const parsed = Number.parseInt(match[1], 10);
  return Number.isNaN(parsed) ? undefined : parsed;
}

function buildExportErrorPayload(code: string, message: string, requestId: string, details: Record<string, unknown> = {}) {
  const upstreamStatus = parseUpstreamStatus(message);
  const upstream = upstreamStatus ? 'spotify' : undefined;
  const cpuLimited = /cpu time limit|exceeded cpu/i.test(message);
  return {
    error: {
      code,
      message,
      request_id: requestId,
      details: {
        ...details,
        upstream,
        upstream_status: upstreamStatus,
        cpu_limited: cpuLimited,
      },
    },
  };
}

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// POST /export/playlist/:id - Generate playlist export
app.post('/playlist/:id', async (c) => {
  const requestId = crypto.randomUUID();
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const body = await c.req.json().catch(() => ({}));
    const requestedFormat = resolveRequestedFormat(body);
    const includeAudioFeatures = resolveIncludeAudioFeatures(body);
    
    const exportService = new ExportService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);
    console.info('[export] start', { requestId, traceId, userId, playlistId });
    
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
      const exportData = await exportService.generatePlaylistExport(playlistId, { includeAudioFeatures });
      
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
        traceId,
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
        traceId,
        userId,
        playlistId,
        error: errorMessage,
      });
      
      await cacheService.set(exportKey, failedStatus, 3600);
      
      return c.json(
        buildExportErrorPayload(
          'EXPORT_FAILED',
          `Failed to generate export: ${errorMessage}`,
          requestId,
          {
            playlist_id: playlistId,
            user_id: userId,
            trace_id: traceId,
            include_audio_features: includeAudioFeatures,
          },
        ),
        resolveErrorStatus('EXPORT_FAILED', errorMessage)
      );
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('Failed to start export:', { requestId, error });
    return c.json(
      buildExportErrorPayload(
        'EXPORT_START_FAILED',
        `Failed to start export: ${errorMessage}`,
        requestId,
      ),
      resolveErrorStatus('EXPORT_START_FAILED', errorMessage)
    );
  }
});

// POST /export/playlists - Generate combined export for multiple playlists
app.post('/playlists', async (c) => {
  const requestId = crypto.randomUUID();
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const body = await c.req.json().catch(() => ({}));
    const playlistIds: string[] = Array.isArray(body?.playlist_ids)
      ? body.playlist_ids.filter((id: unknown) => typeof id === 'string' && id.trim().length > 0)
      : [];
    const requestedFormat = resolveRequestedFormat(body);
    const includeAudioFeatures = resolveIncludeAudioFeatures(body);

    if (playlistIds.length === 0) {
      return c.json({ error: { code: 'INVALID_PLAYLISTS', message: 'playlist_ids must contain at least one playlist id' } }, 400);
    }

    const exportService = new ExportService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);
    const jobId = crypto.randomUUID();
    const batchKey = `export:batch:${jobId}:${userId}`;

    console.info('[export-batch] start', {
      requestId,
      traceId,
      userId,
      playlistCount: playlistIds.length,
      jobId,
    });

    const exportDataList = [];
    for (const playlistId of playlistIds) {
      const exportData = await exportService.generatePlaylistExport(playlistId, { includeAudioFeatures });
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
      traceId,
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
      buildExportErrorPayload(
        'EXPORT_BATCH_FAILED',
        `Failed to generate combined export: ${errorMessage}`,
        requestId,
      ),
      resolveErrorStatus('EXPORT_BATCH_FAILED', errorMessage)
    );
  }
});

// POST /export/playlists/chunk - Generate combined export incrementally across invocations
app.post('/playlists/chunk', async (c) => {
  const requestId = crypto.randomUUID();
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const body = await c.req.json().catch(() => ({}));
    const playlistIds: string[] = Array.isArray(body?.playlist_ids)
      ? body.playlist_ids.filter((id: unknown) => typeof id === 'string' && id.trim().length > 0)
      : [];
    const requestedFormat = resolveRequestedFormat(body);
    const includeAudioFeatures = resolveIncludeAudioFeatures(body);
    const providedJobId = typeof body?.job_id === 'string' && body.job_id.trim().length > 0
      ? body.job_id.trim()
      : '';
    const startCursor = Number.isInteger(body?.cursor) && body.cursor >= 0 ? Number(body.cursor) : 0;
    const requestedChunkSize = Number.isInteger(body?.chunk_size) ? Number(body.chunk_size) : 1;
    const chunkSize = Math.min(Math.max(requestedChunkSize, 1), 3);

    if (playlistIds.length === 0) {
      return c.json({ error: { code: 'INVALID_PLAYLISTS', message: 'playlist_ids must contain at least one playlist id' } }, 400);
    }

    const exportService = new ExportService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);
    const jobId = providedJobId || crypto.randomUUID();
    const batchKey = `export:batch:${jobId}:${userId}`;
    const batchDataKey = `${batchKey}:data`;

    const cachedStatus = await cacheService.get<BatchExportStatus>(batchKey);
    const cachedData = await cacheService.get<any[]>(batchDataKey);

    const status: BatchExportStatus = cachedStatus && cachedStatus.user_id === userId
      ? {
          ...cachedStatus,
          file_format: requestedFormat,
          playlist_ids: playlistIds,
          playlist_count: playlistIds.length,
        }
      : {
          job_id: jobId,
          user_id: userId,
          status: 'processing',
          started_at: new Date().toISOString(),
          progress: 0,
          file_format: requestedFormat,
          playlist_count: playlistIds.length,
          processed_count: 0,
          track_count: 0,
          playlist_ids: playlistIds,
          next_cursor: startCursor,
          continuation_required: true,
        };

    // Keep already-generated playlist exports between chunk calls.
    const exportDataList: any[] = Array.isArray(cachedData) ? cachedData : [];
    const effectiveCursor = Math.max(startCursor, status.next_cursor || 0);
    const endCursor = Math.min(effectiveCursor + chunkSize, playlistIds.length);

    console.info('[export-batch-chunk] process', {
      requestId,
      traceId,
      userId,
      jobId,
      startCursor: effectiveCursor,
      endCursor,
      chunkSize,
      total: playlistIds.length,
    });

    for (let idx = effectiveCursor; idx < endCursor; idx += 1) {
      const playlistId = playlistIds[idx];
      const exportData = await exportService.generatePlaylistExport(playlistId, { includeAudioFeatures });
      exportDataList.push(exportData);
      status.processed_count = exportDataList.length;
      status.track_count = exportDataList.reduce((sum, item) => sum + item.tracks.length, 0);
      status.next_cursor = idx + 1;
      status.progress = Math.min(99, Math.floor((status.processed_count / playlistIds.length) * 100));
      status.continuation_required = status.next_cursor < playlistIds.length;
    }

    if (status.next_cursor >= playlistIds.length) {
      status.status = 'completed';
      status.progress = 100;
      status.completed_at = new Date().toISOString();
      status.file_url = `/export/playlists/${jobId}/download`;
      status.file_size = JSON.stringify(exportDataList).length;
      status.continuation_required = false;
      console.info('[export-batch-chunk] completed', {
        requestId,
        traceId,
        userId,
        jobId,
        playlistCount: exportDataList.length,
        totalTracks: status.track_count,
      });
    }

    await cacheService.set(batchKey, status, 3600);
    await cacheService.set(batchDataKey, exportDataList, 3600);

    return c.json({
      data: status,
      meta: { timestamp: new Date().toISOString(), request_id: requestId },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('[export-batch-chunk] failed', { requestId, error: errorMessage });
    return c.json(
      buildExportErrorPayload(
        'EXPORT_BATCH_CHUNK_FAILED',
        `Failed to process combined export chunk: ${errorMessage}`,
        requestId,
      ),
      resolveErrorStatus('EXPORT_BATCH_CHUNK_FAILED', errorMessage)
    );
  }
});

// GET /export/playlists/:jobId/status - Get combined export status
app.get('/playlists/:jobId/status', async (c) => {
  try {
    const jobId = c.req.param('jobId');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const batchKey = `export:batch:${jobId}:${userId}`;
    const status = await cacheService.get<BatchExportStatus>(batchKey);

    if (!status) {
      return c.json({ error: { code: 'EXPORT_NOT_FOUND', message: 'Combined export not found' } }, 404);
    }

    return c.json({ data: status, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get combined export status:', error);
    return c.json({ error: { code: 'EXPORT_STATUS_FAILED', message: 'Failed to get combined export status' } }, 500);
  }
});

// GET /export/playlists/:jobId/download - Download combined generated file
app.get('/playlists/:jobId/download', async (c) => {
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
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
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('Failed to download combined export:', { error: errorMessage, traceId });
    return c.json(
      buildExportErrorPayload(
        'EXPORT_DOWNLOAD_FAILED',
        `Failed to download combined export: ${errorMessage}`,
        crypto.randomUUID(),
        { trace_id: traceId },
      ),
      resolveErrorStatus('EXPORT_DOWNLOAD_FAILED', errorMessage)
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
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('Failed to download export:', error);
    return c.json(
      buildExportErrorPayload(
        'EXPORT_DOWNLOAD_FAILED',
        `Failed to download export: ${errorMessage}`,
        crypto.randomUUID(),
      ),
      resolveErrorStatus('EXPORT_DOWNLOAD_FAILED', errorMessage)
    );
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

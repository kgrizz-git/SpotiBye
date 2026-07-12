import { Hono } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { ExportService } from '../../services/export';
import { CacheService } from '../../services/cache';
import type { Env } from '../../types/env';
import type { Variables } from '../../types/variables';
import type { ExportData } from '../../services/export-types';
import type { BatchExportStatus } from './helpers/types';
import {
  buildBatchKey,
  buildBatchDataKey,
  buildBatchFileKey,
} from './helpers/cache-keys';
import {
  resolveRequestedFormat,
  resolveStoredFormat,
  formatHttpMeta,
  resolveIncludeAudioFeatures,
} from './helpers/format';
import {
  resolveErrorStatus,
  buildExportErrorPayload,
} from './helpers/errors';
import { generateFileBytes } from './helpers/file-bytes';
import { newRequestId } from './helpers/request-id';
import { zValidator } from '../../validation/z-validator';
import { JobIdParamSchema } from '../../validation/schemas/common';
import {
  ExportBatchBodySchema,
  ExportBatchChunkBodySchema,
} from '../../validation/schemas/export';

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

// POST /export/playlists - Generate combined export for multiple playlists
app.post('/', zValidator('json', ExportBatchBodySchema, 'INVALID_PLAYLISTS'), async (c) => {
  const requestId = newRequestId();
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const body = c.req.valid('json');
    const playlistIds = body.playlist_ids;
    const requestedFormat = resolveRequestedFormat(body);
    const includeAudioFeatures = resolveIncludeAudioFeatures(body);

    const cacheService = new CacheService(c.env.CACHE_KV);
    const exportService = new ExportService(accessToken, cacheService);
    const jobId = crypto.randomUUID();
    const batchKey = buildBatchKey(jobId, userId);

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
      status: 'completed' as const,
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
    await cacheService.set(buildBatchDataKey(jobId, userId), exportDataList, 3600);

    if (requestedFormat !== 'xlsx') {
      // csv and json prebuild cheaply; xlsx regenerates on demand.
      try {
        const fileBytes = await generateFileBytes(exportService, exportDataList, requestedFormat);
        await cacheService.setBuffer(buildBatchFileKey(jobId, userId), fileBytes, 3600);
      } catch (genErr) {
        console.warn('[export-batch] file pre-build failed; download will regenerate', {
          jobId,
          error: genErr instanceof Error ? genErr.message : String(genErr),
        });
      }
    }

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
      { status: resolveErrorStatus('EXPORT_BATCH_FAILED', errorMessage) }
    );
  }
});

// POST /export/playlists/chunk - Generate combined export incrementally across invocations
app.post('/chunk', zValidator('json', ExportBatchChunkBodySchema, 'INVALID_PLAYLISTS'), async (c) => {
  const requestId = newRequestId();
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const body = c.req.valid('json');
    const playlistIds = body.playlist_ids;
    const requestedFormat = resolveRequestedFormat(body);
    const includeAudioFeatures = resolveIncludeAudioFeatures(body);
    const providedJobId = typeof body.job_id === 'string' && body.job_id.trim().length > 0
      ? body.job_id.trim()
      : '';
    const startCursor = Number.isInteger(body.cursor) && body.cursor >= 0 ? Number(body.cursor) : 0;
    const requestedChunkSize = Number.isInteger(body.chunk_size) ? Number(body.chunk_size) : 1;
    const chunkSize = Math.min(Math.max(requestedChunkSize, 1), 3);

    const exportService = new ExportService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);
    const jobId = providedJobId || crypto.randomUUID();
    const batchKey = buildBatchKey(jobId, userId);

    const cachedStatus = await cacheService.get<BatchExportStatus>(batchKey);
    const cachedData = await cacheService.get<ExportData[]>(buildBatchDataKey(jobId, userId));

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
    const exportDataList: ExportData[] = Array.isArray(cachedData) ? (cachedData as ExportData[]) : [];
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
      if (requestedFormat !== 'xlsx') {
        try {
          const fileBytes = await generateFileBytes(exportService, exportDataList, requestedFormat);
          await cacheService.setBuffer(buildBatchFileKey(jobId, userId), fileBytes, 3600);
          console.info('[export-batch-chunk] file cached', { jobId, fileFormat: requestedFormat });
        } catch (genErr) {
          console.warn('[export-batch-chunk] file pre-build failed; download will regenerate', {
            jobId,
            error: genErr instanceof Error ? genErr.message : String(genErr),
          });
        }
      }
    }

    await cacheService.set(batchKey, status, 3600);
    await cacheService.set(buildBatchDataKey(jobId, userId), exportDataList, 3600);

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
      { status: resolveErrorStatus('EXPORT_BATCH_CHUNK_FAILED', errorMessage) }
    );
  }
});

// GET /export/playlists/:jobId/status - Get combined export status
app.get('/:jobId/status', zValidator('param', JobIdParamSchema), async (c) => {
  try {
    const { jobId } = c.req.valid('param');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const batchKey = buildBatchKey(jobId, userId);
    const status = await cacheService.get<BatchExportStatus>(batchKey);

    if (!status) {
      return c.json({ error: { code: 'EXPORT_NOT_FOUND', message: 'Combined export not found' } }, { status: 404 as ContentfulStatusCode });
    }

    return c.json({ data: status, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get combined export status:', error);
    return c.json({ error: { code: 'EXPORT_STATUS_FAILED', message: 'Failed to get combined export status' } }, { status: 500 as ContentfulStatusCode });
  }
});

// GET /export/playlists/:jobId/download - Download combined generated file
app.get('/:jobId/download', zValidator('param', JobIdParamSchema), async (c) => {
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const { jobId } = c.req.valid('param');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const batchKey = buildBatchKey(jobId, userId);
    const exportStatus = await cacheService.get<Record<string, unknown>>(batchKey);
    if (!exportStatus) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Combined export data not found' } }, { status: 404 as ContentfulStatusCode });
    }
    const batchFileFormat = resolveStoredFormat((exportStatus as Record<string, unknown>).file_format);
    const [bContentType, bExt] = formatHttpMeta(batchFileFormat);
    const bFilename = `playlists_export_${Date.now()}.${bExt}`;

    // Serve pre-built bytes when available.
    const prebuiltBytes = await cacheService.getBuffer(buildBatchFileKey(jobId, userId));
    if (prebuiltBytes) {
      return new Response(prebuiltBytes, {
        headers: { 'Content-Type': bContentType, 'Content-Disposition': `attachment; filename="${bFilename}"` },
      });
    }

    // Fallback: regenerate from cached track data.
    const exportDataList = await cacheService.get(buildBatchDataKey(jobId, userId));
    if (!exportDataList || !Array.isArray(exportDataList) || exportDataList.length === 0) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Combined export data not found' } }, { status: 404 as ContentfulStatusCode });
    }
    const exportService = new ExportService(c.get('access_token'), cacheService);
    const fallbackBytes = await generateFileBytes(exportService, exportDataList, batchFileFormat);
    await cacheService.setBuffer(buildBatchFileKey(jobId, userId), fallbackBytes, 3600);
    return new Response(fallbackBytes, {
      headers: { 'Content-Type': bContentType, 'Content-Disposition': `attachment; filename="${bFilename}"` },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('Failed to download combined export:', { error: errorMessage, traceId });
    return c.json(
      buildExportErrorPayload(
        'EXPORT_DOWNLOAD_FAILED',
        `Failed to download combined export: ${errorMessage}`,
        newRequestId(),
        { trace_id: traceId },
      ),
      { status: resolveErrorStatus('EXPORT_DOWNLOAD_FAILED', errorMessage) }
    );
  }
});

export { app as playlistsApp };

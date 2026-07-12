import { Hono } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { ExportService } from '../../services/export';
import { CacheService } from '../../services/cache';
import type { Env } from '../../types/env';
import type { Variables } from '../../types/variables';
import {
  buildSingleExportKey,
  buildSingleExportPrefix,
  buildSingleExportDataKey,
  buildSingleExportFileKey,
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
import { IdParamSchema } from '../../validation/schemas/common';

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

// POST /export/playlist/:id - Generate playlist export
app.post('/:id', zValidator('param', IdParamSchema), async (c) => {
  const requestId = newRequestId();
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const { id: playlistId } = c.req.valid('param');
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const body = await c.req.json().catch(() => ({}));
    const requestedFormat = resolveRequestedFormat(body);
    const includeAudioFeatures = resolveIncludeAudioFeatures(body);

    const exportService = new ExportService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);
    console.info('[export] start', { requestId, traceId, userId, playlistId });

    // Check if export already exists
    const exportKey = buildSingleExportKey(playlistId, userId);
    const existingExport = await cacheService.get<Record<string, unknown>>(exportKey);

    if (existingExport && (existingExport as Record<string, unknown>)?.status === 'completed') {
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
      await cacheService.set(buildSingleExportDataKey(playlistId, userId), exportData, 3600);

      // Pre-build file bytes so the download endpoint only needs a KV read (avoids ExcelJS CPU spike).
      const singleFormat = requestedFormat;
      try {
        const fileBytes = await generateFileBytes(exportService, [exportData], singleFormat);
        await cacheService.setBuffer(buildSingleExportFileKey(playlistId, userId), fileBytes, 3600);
      } catch (genErr) {
        console.warn('[export] file pre-build failed; download will regenerate', {
          playlistId,
          error: genErr instanceof Error ? genErr.message : String(genErr),
        });
      }

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
        { status: resolveErrorStatus('EXPORT_FAILED', errorMessage) }
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
      { status: resolveErrorStatus('EXPORT_START_FAILED', errorMessage) }
    );
  }
});

// GET /export/playlist/:id/status - Get export status
app.get('/:id/status', zValidator('param', IdParamSchema), async (c) => {
  try {
    const { id: playlistId } = c.req.valid('param');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const exportKey = buildSingleExportKey(playlistId, userId);
    const status = await cacheService.get(exportKey);

    if (!status) {
      return c.json({ error: { code: 'EXPORT_NOT_FOUND', message: 'Export not found' } }, { status: 404 as ContentfulStatusCode });
    }

    return c.json({ data: status, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get export status:', error);
    return c.json({ error: { code: 'EXPORT_STATUS_FAILED', message: 'Failed to get export status' } }, { status: 500 as ContentfulStatusCode });
  }
});

// GET /export/playlist/:id/download - Download generated file
app.get('/:id/download', zValidator('param', IdParamSchema), async (c) => {
  try {
    const { id: playlistId } = c.req.valid('param');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const exportKey = buildSingleExportKey(playlistId, userId);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- backward-compat read: shape varies across schema versions (old format stored ExportData directly)
    const exportStatus = await cacheService.get<any>(exportKey);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- backward-compat read: shape varies across schema versions
    let exportData = await cacheService.get<any>(buildSingleExportDataKey(playlistId, userId));
    // Backward compatibility: older payloads stored export data directly under exportKey.
    if (!exportData && exportStatus && exportStatus.playlist && Array.isArray(exportStatus.tracks)) {
      exportData = exportStatus;
    }
    if (!exportStatus && !exportData) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Export data not found' } }, { status: 404 as ContentfulStatusCode });
    }
    const singleFileFormat = resolveStoredFormat(exportStatus?.file_format);
    const [spContentType, spExt] = formatHttpMeta(singleFileFormat);
    const spFilename = `playlist_${playlistId}_export_${Date.now()}.${spExt}`;

    // Serve pre-built bytes (written during POST) — zero CPU re-generation.
    const prebuiltBytes = await cacheService.getBuffer(buildSingleExportFileKey(playlistId, userId));
    if (prebuiltBytes) {
      return new Response(prebuiltBytes, {
        headers: { 'Content-Type': spContentType, 'Content-Disposition': `attachment; filename="${spFilename}"` },
      });
    }

    // Fallback: regenerate from cached track data.
    if (!exportData) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Export data not found' } }, { status: 404 as ContentfulStatusCode });
    }
    const exportService = new ExportService(c.get('access_token'));
    const fallbackBytes = await generateFileBytes(exportService, [exportData], singleFileFormat);
    await cacheService.setBuffer(buildSingleExportFileKey(playlistId, userId), fallbackBytes, 3600);
    return new Response(fallbackBytes, {
      headers: { 'Content-Type': spContentType, 'Content-Disposition': `attachment; filename="${spFilename}"` },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('Failed to download export:', error);
    return c.json(
      buildExportErrorPayload(
        'EXPORT_DOWNLOAD_FAILED',
        `Failed to download export: ${errorMessage}`,
        newRequestId(),
      ),
      { status: resolveErrorStatus('EXPORT_DOWNLOAD_FAILED', errorMessage) }
    );
  }
});

// DELETE /export/playlist/:id - Delete cached single-export artifacts.
// Clears `export:{playlistId}:{userId}*` (base, :data, :file, format variants).
// In-flight resumable job/batch keys (`export:job:*`, `export:batch:*`) are
// intentionally NOT cleared — users must recreate in-flight exports after refresh.
app.delete('/:id', zValidator('param', IdParamSchema), async (c) => {
  try {
    const { id: playlistId } = c.req.valid('param');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    await cacheService.clearPrefixPaginated(
      buildSingleExportPrefix(playlistId, userId),
    );

    return c.json({ data: { message: 'Export deleted successfully' } });
  } catch (error) {
    console.error('Failed to delete export:', error);
    return c.json({ error: { code: 'EXPORT_DELETE_FAILED', message: 'Failed to delete export' } }, { status: 500 as ContentfulStatusCode });
  }
});

export { app as playlistApp };

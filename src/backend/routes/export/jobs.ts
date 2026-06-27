import { Hono } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import {
  ExportService,
  ResumableExportConflictError,
} from '../../services/export';
import { CacheService } from '../../services/cache';
import type { Env } from '../../types/env';
import type { Variables } from '../../types/variables';
import type { ExportData, ResumableExportAssemblyState, ResumableExportJobState, XlsxRenderMode } from '../../services/export-types';
import {
  buildExportJobKey,
  buildExportJobDataKey,
  buildExportJobAssemblyKey,
  buildExportFileKey,
  buildXlsxVariantKey,
  buildPrebuiltFormatKey,
} from './helpers/cache-keys';
import {
  parseXlsxRenderMode,
  resolveRequestedFormat,
  resolveStoredFormat,
  formatHttpMeta,
  resolveIncludeAudioFeatures,
  resolveStepSize,
} from './helpers/format';
import {
  resolveErrorStatus,
  buildExportErrorPayload,
} from './helpers/errors';
import {
  generateFileBytes,
  generateFileBytesFromAssembly,
  precacheJobFiles,
} from './helpers/file-bytes';
import { newRequestId } from './helpers/request-id';

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

// POST /export/jobs - Create resumable export job
app.post('/', async (c) => {
  const requestId = newRequestId();
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const userId = c.get('user').id;
    const body = await c.req.json().catch(() => ({}));
    const playlistIds: string[] = Array.isArray(body?.playlist_ids)
      ? body.playlist_ids.filter((id: unknown) => typeof id === 'string' && id.trim().length > 0)
      : [];
    const requestedFormat = resolveRequestedFormat(body);
    const includeAudioFeatures = resolveIncludeAudioFeatures(body);

    if (playlistIds.length === 0) {
      return c.json({ error: { code: 'INVALID_PLAYLISTS', message: 'playlist_ids must contain at least one playlist id' } }, { status: 400 });
    }

    const cacheService = new CacheService(c.env.CACHE_KV);
    const jobId = crypto.randomUUID();
    const state = ExportService.createJobState({
      jobId,
      userId,
      playlistIds,
      fileFormat: requestedFormat,
      includeAudioFeatures,
      traceId,
    });

    await cacheService.set(buildExportJobKey(jobId, userId), state, 3600);
    await cacheService.set(buildExportJobDataKey(jobId, userId), [], 3600);
    await cacheService.set(buildExportJobAssemblyKey(jobId, userId), ExportService.createAssemblyState(), 3600);

    return c.json({
      data: state,
      meta: { timestamp: new Date().toISOString(), request_id: requestId },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return c.json(
      buildExportErrorPayload('EXPORT_JOB_CREATE_FAILED', `Failed to create export job: ${errorMessage}`, requestId, {
        trace_id: traceId,
      }),
      { status: resolveErrorStatus('EXPORT_JOB_CREATE_FAILED', errorMessage) },
    );
  }
});

// POST /export/jobs/:jobId/step - Process one resumable export step
app.post('/:jobId/step', async (c) => {
  const requestId = newRequestId();
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const userId = c.get('user').id;
    const accessToken = c.get('access_token');
    const jobId = c.req.param('jobId');
    const body = await c.req.json().catch(() => ({}));
    const cursor = typeof body?.cursor === 'string' ? body.cursor : '';
    const resumeToken = typeof body?.resume_token === 'string' ? body.resume_token : '';
    const maxPlaylistsPerStep = resolveStepSize(body);
    const jobKey = buildExportJobKey(jobId, userId);
    const dataKey = buildExportJobDataKey(jobId, userId);
    const assemblyKey = buildExportJobAssemblyKey(jobId, userId);
    const cacheService = new CacheService(c.env.CACHE_KV);
    const job = await cacheService.get<ResumableExportJobState>(jobKey);
    const exportDataList = await cacheService.get<ExportData[]>(dataKey);
    const assemblyState = await cacheService.get<ResumableExportAssemblyState>(assemblyKey);

    if (!job) {
      return c.json({ error: { code: 'EXPORT_JOB_NOT_FOUND', message: 'Export job not found' } }, { status: 404 as ContentfulStatusCode });
    }

    try {
      ExportService.validateStepRequest(job, cursor, resumeToken);
    } catch (error) {
      const isConflictError = error instanceof ResumableExportConflictError
        || (error instanceof Error
          && error.name === 'ResumableExportConflictError'
          && 'latestCursor' in error
          && 'latestResumeToken' in error);
      if (isConflictError) {
        const conflictError = error as ResumableExportConflictError;
        const latestCursor = conflictError.latestCursor;
        const latestResumeToken = conflictError.latestResumeToken;
        return c.json({
          error: {
            code: 'EXPORT_JOB_CONFLICT',
            message: error instanceof Error ? error.message : 'Stale cursor or resume token',
            request_id: requestId,
            details: {
              latest_cursor: latestCursor,
              latest_resume_token: latestResumeToken,
              trace_id: traceId,
            },
          },
        }, { status: 409 as ContentfulStatusCode });
      }
      throw error;
    }

    const exportService = new ExportService(accessToken);
    const result = await exportService.runResumableStep(
      job,
      Array.isArray(exportDataList) ? exportDataList : [],
      assemblyState || ExportService.createAssemblyState(),
      maxPlaylistsPerStep,
    );
    await cacheService.set(jobKey, result.job, 3600);
    await cacheService.set(dataKey, result.exportDataList, 3600);
    await cacheService.set(assemblyKey, result.assemblyState, 3600);

    if (result.job.status === 'completed') {
      await precacheJobFiles(exportService, cacheService, result.job, result.assemblyState, jobKey);
    }

    return c.json({
      data: result.job,
      meta: { timestamp: new Date().toISOString(), request_id: requestId },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return c.json(
      buildExportErrorPayload('EXPORT_JOB_STEP_FAILED', `Failed to process export job step: ${errorMessage}`, requestId, {
        trace_id: traceId,
      }),
      { status: resolveErrorStatus('EXPORT_JOB_STEP_FAILED', errorMessage) },
    );
  }
});

// GET /export/jobs/:jobId/status - Get resumable export job status
app.get('/:jobId/status', async (c) => {
  try {
    const jobId = c.req.param('jobId');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const job = await cacheService.get<ResumableExportJobState>(buildExportJobKey(jobId, userId));

    if (!job) {
      return c.json({ error: { code: 'EXPORT_JOB_NOT_FOUND', message: 'Export job not found' } }, { status: 404 as ContentfulStatusCode });
    }

    const jobKey = buildExportJobKey(jobId, userId);
    const hasDefaultFile = await cacheService.exists(buildExportFileKey(jobKey));
    const hasLiteFile = await cacheService.exists(buildXlsxVariantKey(jobKey, 'lite'));
    const hasRichFile = await cacheService.exists(buildXlsxVariantKey(jobKey, 'rich'));

    return c.json({
      data: {
        ...job,
        available_render_modes: {
          default: hasDefaultFile,
          lite: hasLiteFile,
          rich: hasRichFile,
        },
      },
      meta: { timestamp: new Date().toISOString() },
    });
  } catch (error) {
    console.error('Failed to get export job status:', error);
    return c.json({ error: { code: 'EXPORT_JOB_STATUS_FAILED', message: 'Failed to get export job status' } }, { status: 500 as ContentfulStatusCode });
  }
});

// GET /export/jobs/:jobId/download - Download resumable export file
app.get('/:jobId/download', async (c) => {
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const jobId = c.req.param('jobId');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const jobKey = buildExportJobKey(jobId, userId);
    const assemblyKey = buildExportJobAssemblyKey(jobId, userId);
    const exportStatus = await cacheService.get<ResumableExportJobState>(jobKey);
    if (!exportStatus) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Export job data not found' } }, { status: 404 as ContentfulStatusCode });
    }
    if (exportStatus.status !== 'completed') {
      return c.json({ error: { code: 'EXPORT_NOT_READY', message: 'Export job is not completed yet' } }, { status: 409 as ContentfulStatusCode });
    }
    const requestedMode = parseXlsxRenderMode(c.req.query('mode'));
    const fileFormat = resolveStoredFormat(exportStatus.file_format);
    const [dlContentType, dlExt] = formatHttpMeta(fileFormat);
    const dlFilename = `playlists_export_${Date.now()}.${dlExt}`;

    const renderMode = fileFormat === 'xlsx'
      ? (requestedMode === 'auto' ? (exportStatus.render_mode_hint || 'auto') : requestedMode)
      : fileFormat;

    const keyChecks =
      fileFormat === 'csv'
        ? [buildPrebuiltFormatKey(jobKey, 'csv'), buildExportFileKey(jobKey)]
        : fileFormat === 'json'
          ? [buildExportFileKey(jobKey)]
          : renderMode === 'rich'
            ? [buildXlsxVariantKey(jobKey, 'rich'), buildExportFileKey(jobKey), buildXlsxVariantKey(jobKey, 'lite')]
            : renderMode === 'lite'
              ? [buildXlsxVariantKey(jobKey, 'lite'), buildExportFileKey(jobKey)]
              : [buildExportFileKey(jobKey), buildXlsxVariantKey(jobKey, 'lite'), buildXlsxVariantKey(jobKey, 'rich')];

    for (const key of keyChecks) {
      const prebuiltBytes = await cacheService.getBuffer(key);
      if (prebuiltBytes) {
        const resolvedMode = key.endsWith(':file:rich')
          ? 'rich'
          : key.endsWith(':file:lite')
            ? 'lite'
            : fileFormat === 'csv'
              ? 'csv'
              : (exportStatus.render_mode_hint || 'auto');
        return new Response(prebuiltBytes, {
          headers: {
            'Content-Type': dlContentType,
            'Content-Disposition': `attachment; filename="${dlFilename}"`,
            'X-SpotiBye-Render-Mode': String(resolvedMode),
          },
        });
      }
    }

    // Fallback: regenerate from cached track data (backward-compat for jobs without a pre-built file).
    const assemblyState = await cacheService.get<ResumableExportAssemblyState>(assemblyKey);
    if (assemblyState && Array.isArray(assemblyState.summary_rows) && exportStatus.phase === 'assemble') {
      const exportService = new ExportService(c.get('access_token'));
      const completedFormat = fileFormat;
      if (completedFormat === 'xlsx') {
        try {
          const preferredMode = renderMode as XlsxRenderMode;
          const rendered = await generateFileBytesFromAssembly(exportService, assemblyState, completedFormat, preferredMode);
          const variant = preferredMode === 'rich' ? 'rich' : preferredMode === 'lite' ? 'lite' : 'default';
          if (variant === 'default') {
            await cacheService.setBuffer(buildExportFileKey(jobKey), rendered, 3600);
          } else {
            await cacheService.setBuffer(buildXlsxVariantKey(jobKey, variant), rendered, 3600);
            await cacheService.setBuffer(buildExportFileKey(jobKey), rendered, 3600);
          }
          return new Response(rendered, {
            headers: {
              'Content-Type': dlContentType,
              'Content-Disposition': `attachment; filename="${dlFilename}"`,
              'X-SpotiBye-Render-Mode': variant === 'default' ? String(exportStatus.render_mode_hint || 'auto') : variant,
            },
          });
        } catch {
          // If rich/auto rendering fails (e.g., CPU), degrade to lightweight render for reliability.
          const liteBytes = await generateFileBytesFromAssembly(exportService, assemblyState, completedFormat, 'lite');
          await cacheService.setBuffer(buildXlsxVariantKey(jobKey, 'lite'), liteBytes, 3600);
          await cacheService.setBuffer(buildExportFileKey(jobKey), liteBytes, 3600);
          return new Response(liteBytes, {
            headers: {
              'Content-Type': dlContentType,
              'Content-Disposition': `attachment; filename="${dlFilename}"`,
              'X-SpotiBye-Render-Mode': 'lite',
              'X-SpotiBye-Render-Warning': 'Degraded-to-lite-due-to-render-failure',
            },
          });
        }
      }

      const fallbackBytes = await generateFileBytesFromAssembly(exportService, assemblyState, completedFormat);
      if (completedFormat === 'csv') {
        await cacheService.setBuffer(buildPrebuiltFormatKey(jobKey, 'csv'), fallbackBytes, 3600);
      }
      await cacheService.setBuffer(buildExportFileKey(jobKey), fallbackBytes, 3600);
      return new Response(fallbackBytes, {
        headers: { 'Content-Type': dlContentType, 'Content-Disposition': `attachment; filename="${dlFilename}"` },
      });
    }

    const exportDataList = await cacheService.get<ExportData[]>(buildExportJobDataKey(jobId, userId));
    if (!Array.isArray(exportDataList) || exportDataList.length === 0) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Export job data not found' } }, { status: 404 as ContentfulStatusCode });
    }
    const exportService = new ExportService(c.get('access_token'));
    const fallbackBytes = await generateFileBytes(exportService, exportDataList, fileFormat);
    await cacheService.setBuffer(buildExportFileKey(jobKey), fallbackBytes, 3600);
    return new Response(fallbackBytes, {
      headers: { 'Content-Type': dlContentType, 'Content-Disposition': `attachment; filename="${dlFilename}"` },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return c.json(
      buildExportErrorPayload(
        'EXPORT_JOB_DOWNLOAD_FAILED',
        `Failed to download export job: ${errorMessage}`,
        newRequestId(),
        { trace_id: traceId },
      ),
      { status: resolveErrorStatus('EXPORT_JOB_DOWNLOAD_FAILED', errorMessage) },
    );
  }
});

export { app as jobsApp };

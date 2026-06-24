import { Hono } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { authMiddleware } from '../middleware/auth';
import {
  ExportService,
  ResumableExportConflictError,
  type ExportData,
  type ResumableExportAssemblyState,
  type XlsxRenderMode,
} from '../services/export';
import { CacheService } from '../services/cache';
import type { Env } from '../types/env';
import type { Variables } from '../types/variables';

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

type ExportFormat = 'xlsx' | 'csv' | 'json';

type BatchExportStatus = {
  job_id: string;
  user_id: string;
  status: 'processing' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  progress: number;
  file_url?: string;
  file_format: ExportFormat;
  file_size?: number;
  playlist_count: number;
  processed_count: number;
  track_count: number;
  playlist_ids: string[];
  next_cursor: number;
  continuation_required: boolean;
  error?: string;
};

type ResumableExportJobStatus = ReturnType<typeof ExportService.createJobState>;

function resolveStepSize(body: Record<string, unknown>): number {
  const requested = Number.isInteger(body?.max_playlists_per_step)
    ? Number(body.max_playlists_per_step)
    : Number.isInteger(body?.chunk_size)
      ? Number(body.chunk_size)
      : 1;
  return Math.min(Math.max(requested, 1), 3);
}

function buildExportJobKey(jobId: string, userId: string): string {
  return `export:job:${jobId}:${userId}`;
}

function buildExportJobDataKey(jobId: string, userId: string): string {
  return `${buildExportJobKey(jobId, userId)}:data`;
}

function buildExportJobAssemblyKey(jobId: string, userId: string): string {
  return `${buildExportJobKey(jobId, userId)}:assembly`;
}

function buildExportFileKey(baseKey: string, mode: 'default' | 'rich' | 'lite' | 'csv' = 'default'): string {
  if (mode === 'default') {
    return `${baseKey}:file`;
  }
  return `${baseKey}:file:${mode}`;
}

function parseXlsxRenderMode(value: string | undefined): XlsxRenderMode {
  const normalized = String(value || '').toLowerCase();
  if (normalized === 'rich' || normalized === 'lite') {
    return normalized;
  }
  return 'auto';
}

function resolveRequestedFormat(body: Record<string, unknown>): ExportFormat {
  const format = String(body?.format || '').toLowerCase();
  if (format === 'csv') return 'csv';
  if (format === 'json') return 'json';
  return 'xlsx';
}

// Normalize a persisted file_format value (untrusted KV/JSON) to a known format.
function resolveStoredFormat(value: unknown): ExportFormat {
  return value === 'csv' ? 'csv' : value === 'json' ? 'json' : 'xlsx';
}

// HTTP Content-Type + filename extension for a given export format.
function formatHttpMeta(format: ExportFormat): [string, string] {
  if (format === 'csv') return ['text/csv; charset=utf-8', 'csv'];
  if (format === 'json') return ['application/json; charset=utf-8', 'json'];
  return ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'];
}

function resolveIncludeAudioFeatures(body: Record<string, unknown>): boolean {
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

// Shared helper: build the final download bytes for a completed export (xlsx, csv, or json).
async function generateFileBytes(
  exportService: ExportService,
  exportDataList: ExportData[],
  fileFormat: ExportFormat,
): Promise<ArrayBuffer> {
  if (fileFormat === 'json') {
    return exportService.generateCombinedJson(exportDataList);
  }
  if (fileFormat === 'csv') {
    const chunks: string[] = [];
    for (const item of exportDataList) {
      const csvBytes = await exportService.generateCsvFile(item);
      chunks.push(new TextDecoder().decode(csvBytes));
    }
    return new TextEncoder().encode(chunks.join('\n\n')).buffer as ArrayBuffer;
  }
  return exportService.generateCombinedExcelFile(exportDataList);
}

async function generateFileBytesFromAssembly(
  exportService: ExportService,
  assemblyState: ResumableExportAssemblyState,
  fileFormat: ExportFormat,
  renderMode: XlsxRenderMode = 'auto',
): Promise<ArrayBuffer> {
  if (fileFormat === 'json') {
    return exportService.generateCombinedJsonFromAssembly(assemblyState);
  }
  if (fileFormat === 'csv') {
    return exportService.generateCombinedCsvFromAssembly(assemblyState);
  }
  return exportService.generateCombinedExcelFileFromAssembly(assemblyState, renderMode);
}

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// POST /export/jobs - Create resumable export job
app.post('/jobs', async (c) => {
  const requestId = crypto.randomUUID();
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
      { status: resolveErrorStatus('EXPORT_JOB_CREATE_FAILED', errorMessage) as ContentfulStatusCode },
    );
  }
});

// POST /export/jobs/:jobId/step - Process one resumable export step
app.post('/jobs/:jobId/step', async (c) => {
  const requestId = crypto.randomUUID();
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
    const job = await cacheService.get<ResumableExportJobStatus>(jobKey);
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
      const worksheetCount = Array.isArray(result.assemblyState?.worksheets) ? result.assemblyState.worksheets.length : 0;
      const trackRows = Array.isArray(result.assemblyState?.worksheets)
        ? result.assemblyState.worksheets.reduce((sum, ws) => sum + (Array.isArray(ws.rows) ? ws.rows.length : 0), 0)
        : 0;
      const richEligible = worksheetCount <= 18 && trackRows <= 2400;

      result.job.render_stats = {
        worksheet_count: worksheetCount,
        track_rows: trackRows,
      };
      result.job.render_mode_hint = richEligible ? 'rich' : 'lite';
      if (!richEligible) {
        result.job.render_warning = 'Large combined export uses reliability mode by default (reduced styling)';
      }

      await cacheService.set(jobKey, result.job, 3600);

      if (result.job.file_format !== 'xlsx') {
        // csv and json are single-variant: prebuild one file (cheap, no rich/lite).
        const completedFormat = result.job.file_format;
        try {
          const fileBytes = await generateFileBytesFromAssembly(exportService, result.assemblyState, completedFormat);
          if (completedFormat === 'csv') {
            await cacheService.setBuffer(buildExportFileKey(jobKey, 'csv'), fileBytes, 3600);
          }
          await cacheService.setBuffer(buildExportFileKey(jobKey), fileBytes, 3600);
          console.info('[export-job] file cached', { jobId, fileFormat: completedFormat });
        } catch (genErr) {
          console.warn('[export-job] file pre-build failed; download will regenerate on demand', {
            jobId,
            error: genErr instanceof Error ? genErr.message : String(genErr),
          });
        }
      } else {
        // Always prebuild lite variant for reliability. Optionally prebuild rich when small enough.
        try {
          const liteBytes = await generateFileBytesFromAssembly(exportService, result.assemblyState, 'xlsx', 'lite');
          await cacheService.setBuffer(buildExportFileKey(jobKey, 'lite'), liteBytes, 3600);
          await cacheService.setBuffer(buildExportFileKey(jobKey), liteBytes, 3600);
        } catch (liteErr) {
          console.warn('[export-job] lite xlsx pre-build failed; download will generate on demand', {
            jobId,
            error: liteErr instanceof Error ? liteErr.message : String(liteErr),
          });
        }

        if (richEligible) {
          try {
            const richBytes = await generateFileBytesFromAssembly(exportService, result.assemblyState, 'xlsx', 'rich');
            await cacheService.setBuffer(buildExportFileKey(jobKey, 'rich'), richBytes, 3600);
          } catch (richErr) {
            console.warn('[export-job] rich xlsx pre-build failed; lite remains available', {
              jobId,
              error: richErr instanceof Error ? richErr.message : String(richErr),
            });
          }
        }
      }
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
      { status: resolveErrorStatus('EXPORT_JOB_STEP_FAILED', errorMessage) as ContentfulStatusCode },
    );
  }
});

// GET /export/jobs/:jobId/status - Get resumable export job status
app.get('/jobs/:jobId/status', async (c) => {
  try {
    const jobId = c.req.param('jobId');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const job = await cacheService.get<ResumableExportJobStatus>(buildExportJobKey(jobId, userId));

    if (!job) {
      return c.json({ error: { code: 'EXPORT_JOB_NOT_FOUND', message: 'Export job not found' } }, { status: 404 as ContentfulStatusCode });
    }

    const jobKey = buildExportJobKey(jobId, userId);
    const hasDefaultFile = await cacheService.exists(buildExportFileKey(jobKey));
    const hasLiteFile = await cacheService.exists(buildExportFileKey(jobKey, 'lite'));
    const hasRichFile = await cacheService.exists(buildExportFileKey(jobKey, 'rich'));

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
app.get('/jobs/:jobId/download', async (c) => {
  const traceId = c.req.header('X-SpotiBye-Trace-Id') || undefined;
  try {
    const jobId = c.req.param('jobId');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const jobKey = buildExportJobKey(jobId, userId);
    const assemblyKey = buildExportJobAssemblyKey(jobId, userId);
    const exportStatus = await cacheService.get<ResumableExportJobStatus>(jobKey);
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

    const prebuiltKeyOrder = fileFormat === 'csv'
      ? [buildExportFileKey(jobKey, 'csv'), buildExportFileKey(jobKey)]
      : fileFormat === 'json'
        ? [buildExportFileKey(jobKey)]
        : renderMode === 'rich'
          ? [buildExportFileKey(jobKey, 'rich'), buildExportFileKey(jobKey), buildExportFileKey(jobKey, 'lite')]
          : renderMode === 'lite'
            ? [buildExportFileKey(jobKey, 'lite'), buildExportFileKey(jobKey)]
            : [buildExportFileKey(jobKey), buildExportFileKey(jobKey, 'lite'), buildExportFileKey(jobKey, 'rich')];

    for (const key of prebuiltKeyOrder) {
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
      if (fileFormat === 'xlsx') {
        try {
          const preferredMode = renderMode === 'csv' ? 'auto' : (renderMode as XlsxRenderMode);
          const rendered = await generateFileBytesFromAssembly(exportService, assemblyState, fileFormat, preferredMode);
          const variant = preferredMode === 'rich' ? 'rich' : preferredMode === 'lite' ? 'lite' : 'default';
          await cacheService.setBuffer(buildExportFileKey(jobKey, variant as 'default' | 'rich' | 'lite'), rendered, 3600);
          await cacheService.setBuffer(buildExportFileKey(jobKey), rendered, 3600);
          return new Response(rendered, {
            headers: {
              'Content-Type': dlContentType,
              'Content-Disposition': `attachment; filename="${dlFilename}"`,
              'X-SpotiBye-Render-Mode': variant === 'default' ? String(exportStatus.render_mode_hint || 'auto') : variant,
            },
          });
        } catch {
          // If rich/auto rendering fails (e.g., CPU), degrade to lightweight render for reliability.
          const liteBytes = await generateFileBytesFromAssembly(exportService, assemblyState, fileFormat, 'lite');
          await cacheService.setBuffer(buildExportFileKey(jobKey, 'lite'), liteBytes, 3600);
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

      const fallbackBytes = await generateFileBytesFromAssembly(exportService, assemblyState, fileFormat);
      if (fileFormat === 'csv') {
        await cacheService.setBuffer(buildExportFileKey(jobKey, 'csv'), fallbackBytes, 3600);
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
    await cacheService.setBuffer(`${jobKey}:file`, fallbackBytes, 3600);
    return new Response(fallbackBytes, {
      headers: { 'Content-Type': dlContentType, 'Content-Disposition': `attachment; filename="${dlFilename}"` },
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return c.json(
      buildExportErrorPayload(
        'EXPORT_JOB_DOWNLOAD_FAILED',
        `Failed to download export job: ${errorMessage}`,
        crypto.randomUUID(),
        { trace_id: traceId },
      ),
      { status: resolveErrorStatus('EXPORT_JOB_DOWNLOAD_FAILED', errorMessage) as ContentfulStatusCode },
    );
  }
});

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
      await cacheService.set(`${exportKey}:data`, exportData, 3600);

      // Pre-build file bytes so the download endpoint only needs a KV read (avoids ExcelJS CPU spike).
      const singleFormat = requestedFormat;
      try {
        const fileBytes = await generateFileBytes(exportService, [exportData], singleFormat);
        await cacheService.setBuffer(`${exportKey}:file`, fileBytes, 3600);
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
        { status: resolveErrorStatus('EXPORT_FAILED', errorMessage) as ContentfulStatusCode }
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
      { status: resolveErrorStatus('EXPORT_START_FAILED', errorMessage) as ContentfulStatusCode }
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
      return c.json({ error: { code: 'INVALID_PLAYLISTS', message: 'playlist_ids must contain at least one playlist id' } }, { status: 400 as ContentfulStatusCode });
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

    if (requestedFormat !== 'xlsx') {
      // csv and json prebuild cheaply; xlsx regenerates on demand.
      try {
        const fileBytes = await generateFileBytes(exportService, exportDataList, requestedFormat);
        await cacheService.setBuffer(`${batchKey}:file`, fileBytes, 3600);
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
      { status: resolveErrorStatus('EXPORT_BATCH_FAILED', errorMessage) as ContentfulStatusCode }
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
      return c.json({ error: { code: 'INVALID_PLAYLISTS', message: 'playlist_ids must contain at least one playlist id' } }, { status: 400 as ContentfulStatusCode });
    }

    const exportService = new ExportService(accessToken);
    const cacheService = new CacheService(c.env.CACHE_KV);
    const jobId = providedJobId || crypto.randomUUID();
    const batchKey = `export:batch:${jobId}:${userId}`;
    const batchDataKey = `${batchKey}:data`;

    const cachedStatus = await cacheService.get<BatchExportStatus>(batchKey);
    const cachedData = await cacheService.get<ExportData[]>(batchDataKey);

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
          await cacheService.setBuffer(`${batchKey}:file`, fileBytes, 3600);
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
      { status: resolveErrorStatus('EXPORT_BATCH_CHUNK_FAILED', errorMessage) as ContentfulStatusCode }
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
      return c.json({ error: { code: 'EXPORT_NOT_FOUND', message: 'Combined export not found' } }, { status: 404 as ContentfulStatusCode });
    }

    return c.json({ data: status, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get combined export status:', error);
    return c.json({ error: { code: 'EXPORT_STATUS_FAILED', message: 'Failed to get combined export status' } }, { status: 500 as ContentfulStatusCode });
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
    const exportStatus = await cacheService.get<Record<string, unknown>>(batchKey);
    if (!exportStatus) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Combined export data not found' } }, { status: 404 as ContentfulStatusCode });
    }
    const batchFileFormat = resolveStoredFormat((exportStatus as Record<string, unknown>).file_format);
    const [bContentType, bExt] = formatHttpMeta(batchFileFormat);
    const bFilename = `playlists_export_${Date.now()}.${bExt}`;

    // Serve pre-built bytes when available.
    const prebuiltBytes = await cacheService.getBuffer(`${batchKey}:file`);
    if (prebuiltBytes) {
      return new Response(prebuiltBytes, {
        headers: { 'Content-Type': bContentType, 'Content-Disposition': `attachment; filename="${bFilename}"` },
      });
    }

    // Fallback: regenerate from cached track data.
    const exportDataList = await cacheService.get(`${batchKey}:data`);
    if (!exportDataList || !Array.isArray(exportDataList) || exportDataList.length === 0) {
      return c.json({ error: { code: 'EXPORT_DATA_NOT_FOUND', message: 'Combined export data not found' } }, { status: 404 as ContentfulStatusCode });
    }
    const exportService = new ExportService(c.get('access_token'));
    const fallbackBytes = await generateFileBytes(exportService, exportDataList, batchFileFormat);
    await cacheService.setBuffer(`${batchKey}:file`, fallbackBytes, 3600);
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
        crypto.randomUUID(),
        { trace_id: traceId },
      ),
      { status: resolveErrorStatus('EXPORT_DOWNLOAD_FAILED', errorMessage) as ContentfulStatusCode }
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
      return c.json({ error: { code: 'EXPORT_NOT_FOUND', message: 'Export not found' } }, { status: 404 as ContentfulStatusCode });
    }

    return c.json({ data: status, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get export status:', error);
    return c.json({ error: { code: 'EXPORT_STATUS_FAILED', message: 'Failed to get export status' } }, { status: 500 as ContentfulStatusCode });
  }
});

// GET /export/playlist/:id/download - Download generated file
app.get('/playlist/:id/download', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);

    const exportKey = `export:${playlistId}:${userId}`;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- backward-compat read: shape varies across schema versions (old format stored ExportData directly)
    const exportStatus = await cacheService.get<any>(exportKey);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any -- backward-compat read: shape varies across schema versions
    let exportData = await cacheService.get<any>(`${exportKey}:data`);
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
    const prebuiltBytes = await cacheService.getBuffer(`${exportKey}:file`);
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
    await cacheService.setBuffer(`${exportKey}:file`, fallbackBytes, 3600);
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
        crypto.randomUUID(),
      ),
      { status: resolveErrorStatus('EXPORT_DOWNLOAD_FAILED', errorMessage) as ContentfulStatusCode }
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
      cacheService.delete(`${exportKey}:data`),
      cacheService.delete(`${exportKey}:file`)
    ]);

    return c.json({ data: { message: 'Export deleted successfully' } });
  } catch (error) {
    console.error('Failed to delete export:', error);
    return c.json({ error: { code: 'EXPORT_DELETE_FAILED', message: 'Failed to delete export' } }, { status: 500 as ContentfulStatusCode });
  }
});

export { app as exportRoutes };

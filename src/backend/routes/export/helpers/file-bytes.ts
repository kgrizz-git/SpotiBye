import type { ExportService } from '../../../services/export';
import type { CacheService } from '../../../services/cache';
import type { ExportData, ResumableExportAssemblyState, ResumableExportJobState } from '../../../services/export-types';
import type { XlsxRenderMode } from '../../../services/export';
import type { ExportFormat } from './types';
import { buildExportFileKey } from './cache-keys';

export async function generateFileBytes(
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

export async function generateFileBytesFromAssembly(
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

export async function precacheJobFiles(
  exportService: ExportService,
  cacheService: CacheService,
  job: ResumableExportJobState,
  assemblyState: ResumableExportAssemblyState,
  jobKey: string,
): Promise<void> {
  const worksheetCount = Array.isArray(assemblyState?.worksheets) ? assemblyState.worksheets.length : 0;
  const trackRows = Array.isArray(assemblyState?.worksheets)
    ? assemblyState.worksheets.reduce((sum, ws) => sum + (Array.isArray(ws.rows) ? ws.rows.length : 0), 0)
    : 0;
  const richEligible = worksheetCount <= 18 && trackRows <= 2400;

  job.render_stats = {
    worksheet_count: worksheetCount,
    track_rows: trackRows,
  };
  job.render_mode_hint = richEligible ? 'rich' : 'lite';
  if (!richEligible) {
    job.render_warning = 'Large combined export uses reliability mode by default (reduced styling)';
  }

  await cacheService.set(jobKey, job, 3600);

  if (job.file_format !== 'xlsx') {
    // csv and json are single-variant: prebuild one file (cheap, no rich/lite).
    const completedFormat = job.file_format;
    try {
      const fileBytes = await generateFileBytesFromAssembly(exportService, assemblyState, completedFormat);
      if (completedFormat === 'csv') {
        await cacheService.setBuffer(buildExportFileKey(jobKey, 'csv'), fileBytes, 3600);
      }
      await cacheService.setBuffer(buildExportFileKey(jobKey), fileBytes, 3600);
      console.info('[export-job] file cached', { jobId: job.job_id, fileFormat: completedFormat });
    } catch (genErr) {
      console.warn('[export-job] file pre-build failed; download will regenerate on demand', {
        jobId: job.job_id,
        error: genErr instanceof Error ? genErr.message : String(genErr),
      });
    }
  } else {
    // Always prebuild lite variant for reliability. Optionally prebuild rich when small enough.
    try {
      const liteBytes = await generateFileBytesFromAssembly(exportService, assemblyState, 'xlsx', 'lite');
      await cacheService.setBuffer(buildExportFileKey(jobKey, 'lite'), liteBytes, 3600);
      await cacheService.setBuffer(buildExportFileKey(jobKey), liteBytes, 3600);
    } catch (liteErr) {
      console.warn('[export-job] lite xlsx pre-build failed; download will generate on demand', {
        jobId: job.job_id,
        error: liteErr instanceof Error ? liteErr.message : String(liteErr),
      });
    }

    if (richEligible) {
      try {
        const richBytes = await generateFileBytesFromAssembly(exportService, assemblyState, 'xlsx', 'rich');
        await cacheService.setBuffer(buildExportFileKey(jobKey, 'rich'), richBytes, 3600);
      } catch (richErr) {
        console.warn('[export-job] rich xlsx pre-build failed; lite remains available', {
          jobId: job.job_id,
          error: richErr instanceof Error ? richErr.message : String(richErr),
        });
      }
    }
  }
}

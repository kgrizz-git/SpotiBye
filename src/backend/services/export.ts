/**
 * Export service — orchestrates multi-playlist export to CSV, XLSX, or JSON.
 *
 * Uses a two-phase cursor approach (Collection → Assembly) to survive Cloudflare
 * Worker CPU time limits when processing large playlists.
 *
 * Golden Principle #3: Cursors are persisted to KV before any destructive step.
 * Never remove cursor persistence or move it after data consumption.
 *
 * Reference: docs/design-docs/resumable-export-cursors.md
 */
import { SpotifyService } from './spotify';
import type { CacheService } from './cache';
import { encodeCursor, decodeCursor } from './export-cursor';
import { createResumeToken, createJobState, validateStepRequest } from './export-job-state';
import { createAssemblyState } from './export-assemble';
import { buildExportTracks, calculateTotalDurationMs, buildPlaylistMetadata } from './export-tracks';
import { generateCombinedExcelFile, generateCombinedExcelFileFromAssembly } from './export-xlsx';
import { generateCsvFile, generateCombinedCsvFromAssembly } from './export-csv';
import { generateCombinedJson, generateCombinedJsonFromAssembly } from './export-json';
import { runCollectStep } from './export-collect';
import { runAssembleStep } from './export-assembly';

export type {
  ExportTrack,
  ExportData,
  ResumableExportJobStatus,
  ResumableExportJobPhase,
  ResumablePlaylistProgress,
  ExportCellValue,
  XlsxRenderMode,
  WorksheetAssemblyData,
  ResumableExportAssemblyState,
  ResumableExportJobState,
  ResumableExportStepResult,
} from './export-types';

export { ResumableExportConflictError } from './export-job-state';

import type {
  ExportData,
  ResumableExportAssemblyState,
  ResumableExportJobState,
  ResumableExportStepResult,
  XlsxRenderMode,
} from './export-types';

export class ExportService {
  private accessToken: string;
  private cache?: CacheService;

  constructor(accessToken: string, cache?: CacheService) {
    this.accessToken = accessToken;
    this.cache = cache;
  }

  static encodeCursor(
    nextPlaylistIndex: number,
    phase: import('./export-types').ResumableExportJobPhase = 'collect',
    nextTrackOffset = 0,
    nextAssembleIndex = 0,
  ): string {
    return encodeCursor(nextPlaylistIndex, phase, nextTrackOffset, nextAssembleIndex);
  }

  static decodeCursor(
    cursor: string | undefined,
    fallbackIndex = 0,
    fallbackTrackOffset = 0,
    fallbackAssembleIndex = 0,
  ) {
    return decodeCursor(cursor, fallbackIndex, fallbackTrackOffset, fallbackAssembleIndex);
  }

  static createAssemblyState(): ResumableExportAssemblyState {
    return createAssemblyState();
  }

  static createResumeToken(): string {
    return createResumeToken();
  }

  static createJobState(options: {
    jobId: string;
    userId: string;
    playlistIds: string[];
    fileFormat: 'xlsx' | 'csv' | 'json';
    includeAudioFeatures: boolean;
    traceId?: string;
  }): ResumableExportJobState {
    return createJobState(options);
  }

  static validateStepRequest(job: ResumableExportJobState, cursor: string, resumeToken: string): void {
    validateStepRequest(job, cursor, resumeToken);
  }

  async runResumableStep(
    job: ResumableExportJobState,
    exportDataList: ExportData[],
    assemblyState: ResumableExportAssemblyState,
    maxPlaylistsPerStep = 1,
  ): Promise<ResumableExportStepResult> {
    if (job.status === 'completed') {
      return { job, exportDataList, assemblyState };
    }

    const decodedCursor = decodeCursor(
      job.current_cursor,
      job.next_playlist_index,
      job.current_track_offset,
      job.assemble_index,
    );

    if (job.phase === 'assemble' || decodedCursor.phase === 'assemble' || job.status === 'assembling') {
      return runAssembleStep(job, exportDataList, assemblyState, maxPlaylistsPerStep, decodedCursor.nextAssembleIndex);
    }

    return runCollectStep(
      this.accessToken,
      job,
      exportDataList,
      assemblyState,
      maxPlaylistsPerStep,
      decodedCursor.nextPlaylistIndex,
      decodedCursor.nextTrackOffset,
      this.cache,
    );
  }

  async generatePlaylistExport(
    playlistId: string,
    options?: { includeAudioFeatures?: boolean },
  ): Promise<ExportData> {
    const spotifyService = new SpotifyService(this.accessToken);
    const includeAudioFeatures = options?.includeAudioFeatures === true;

    const playlist = await spotifyService.getPlaylist(playlistId);

    const allTracks = [];
    let offset = 0;
    const limit = 100;
    while (true) {
      const tracksData = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
      allTracks.push(...tracksData.items);
      // Advance by the raw page size — see export-cursor.ts comments.
      if (tracksData.rawCount < limit) {
        break;
      }
      offset += limit;
    }

    const exportTracks = await buildExportTracks(allTracks, includeAudioFeatures, this.cache);
    const totalDurationMs = calculateTotalDurationMs(allTracks);

    return {
      playlist: buildPlaylistMetadata(playlist, exportTracks.length),
      tracks: exportTracks,
      total_duration_ms: totalDurationMs,
      generated_at: new Date().toISOString(),
    };
  }

  async generateCsvFile(exportData: ExportData): Promise<ArrayBuffer> {
    return generateCsvFile(exportData);
  }

  async generateCombinedCsvFromAssembly(assemblyState: ResumableExportAssemblyState): Promise<ArrayBuffer> {
    return generateCombinedCsvFromAssembly(assemblyState);
  }

  generateCombinedJson(exportDataList: ExportData[]): ArrayBuffer {
    return generateCombinedJson(exportDataList);
  }

  generateCombinedJsonFromAssembly(assemblyState: ResumableExportAssemblyState): ArrayBuffer {
    return generateCombinedJsonFromAssembly(assemblyState);
  }

  async generateCombinedExcelFile(exportDataList: ExportData[]): Promise<ArrayBuffer> {
    return generateCombinedExcelFile(exportDataList);
  }

  async generateCombinedExcelFileFromAssembly(
    assemblyState: ResumableExportAssemblyState,
    renderMode: XlsxRenderMode = 'auto',
  ): Promise<ArrayBuffer> {
    return generateCombinedExcelFileFromAssembly(assemblyState, renderMode);
  }

  async generateExcelFile(exportData: ExportData): Promise<ArrayBuffer> {
    return generateCombinedExcelFile([exportData]);
  }

  async generateAdvancedExcelFile(exportData: ExportData): Promise<ArrayBuffer> {
    return this.generateExcelFile(exportData);
  }
}

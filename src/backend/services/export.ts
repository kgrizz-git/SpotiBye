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
import ExcelJS from 'exceljs';

interface ExportTrack {
  Artist: string;
  Album: string;
  Track: string;
  Duration: string;
  'Spotify URL': string;
  Tempo: number | string;
  Key: string;
  Danceability: number | string;
  Energy: number | string;
  Valence: number | string;
  Acousticness: number | string;
  Instrumentalness: number | string;
  Liveness: number | string;
  Speechiness: number | string;
  Loudness: number | string;
  'Time Signature': number | string;
}

export interface ExportData {
  playlist: {
    id: string;
    name: string;
    description: string;
    total_tracks: number;
    owner: string;
    followers: number;
    url: string;
    cover_image_url?: string;
    created_at?: string;
  };
  tracks: ExportTrack[];
  total_duration_ms: number;
  generated_at: string;
}

export type ResumableExportJobStatus = 'running' | 'assembling' | 'completed' | 'failed';

export type ResumableExportJobPhase = 'collect' | 'assemble';

export interface ResumablePlaylistProgress {
  next_offset: number;
  total_tracks: number;
  collected_tracks: number;
  done: boolean;
}

type ExportCellValue = string | number;

export type XlsxRenderMode = 'auto' | 'rich' | 'lite';

export interface WorksheetAssemblyData {
  sheet_name: string;
  playlist_name: string;
  playlist_owner: string;
  playlist_followers: number;
  playlist_cover_image_url?: string;
  playlist_description: string;
  playlist_url: string;
  total_duration: string;
  headers: string[];
  rows: ExportCellValue[][];
}

export interface ResumableExportAssemblyState {
  summary_headers: string[];
  summary_rows: ExportCellValue[][];
  worksheets: WorksheetAssemblyData[];
  csv_chunks: string[];
  next_assemble_index: number;
}

export interface ResumableExportJobState {
  job_id: string;
  user_id: string;
  status: ResumableExportJobStatus;
  phase: ResumableExportJobPhase;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  playlist_ids: string[];
  playlist_count: number;
  processed_count: number;
  track_count: number;
  file_format: 'xlsx' | 'csv' | 'json';
  include_audio_features: boolean;
  current_cursor: string;
  current_resume_token: string;
  next_playlist_index: number;
  current_track_offset: number;
  assemble_index: number;
  track_page_size: number;
  playlist_progress: Record<string, ResumablePlaylistProgress>;
  continuation_required: boolean;
  progress: number;
  file_url?: string;
  file_size?: number;
  result?: {
    download_id: string;
    filename?: string;
    expires_at?: string;
  };
  last_error?: string;
  trace_id?: string;
  last_completed_cursor?: string;
  last_completed_token?: string;
  render_mode_hint?: 'rich' | 'lite';
  render_warning?: string;
  render_stats?: {
    worksheet_count: number;
    track_rows: number;
  };
}

export interface ResumableExportStepResult {
  job: ResumableExportJobState;
  exportDataList: ExportData[];
  assemblyState: ResumableExportAssemblyState;
}

export class ResumableExportConflictError extends Error {
  latestCursor: string;
  latestResumeToken: string;

  constructor(message: string, latestCursor: string, latestResumeToken: string) {
    super(message);
    this.name = 'ResumableExportConflictError';
    this.latestCursor = latestCursor;
    this.latestResumeToken = latestResumeToken;
  }
}

export class ExportService {
  private accessToken: string;

  constructor(accessToken: string) {
    this.accessToken = accessToken;
  }

  static encodeCursor(nextPlaylistIndex: number, phase: ResumableExportJobPhase = 'collect', nextTrackOffset = 0, nextAssembleIndex = 0): string {
    return JSON.stringify({
      next_playlist_index: nextPlaylistIndex,
      next_track_offset: nextTrackOffset,
      next_assemble_index: nextAssembleIndex,
      phase,
    });
  }

  static decodeCursor(
    cursor: string | undefined,
    fallbackIndex = 0,
    fallbackTrackOffset = 0,
    fallbackAssembleIndex = 0,
  ): { nextPlaylistIndex: number; nextTrackOffset: number; nextAssembleIndex: number; phase: ResumableExportJobPhase } {
    if (!cursor) {
      return {
        nextPlaylistIndex: fallbackIndex,
        nextTrackOffset: fallbackTrackOffset,
        nextAssembleIndex: fallbackAssembleIndex,
        phase: 'collect',
      };
    }

    try {
      const parsed = JSON.parse(cursor);
      const nextPlaylistIndex = Number.isInteger(parsed?.next_playlist_index) && parsed.next_playlist_index >= 0
        ? parsed.next_playlist_index
        : fallbackIndex;
      const nextTrackOffset = Number.isInteger(parsed?.next_track_offset) && parsed.next_track_offset >= 0
        ? parsed.next_track_offset
        : fallbackTrackOffset;
      const nextAssembleIndex = Number.isInteger(parsed?.next_assemble_index) && parsed.next_assemble_index >= 0
        ? parsed.next_assemble_index
        : fallbackAssembleIndex;
      const phase = parsed?.phase === 'assemble' ? 'assemble' : 'collect';
      return { nextPlaylistIndex, nextTrackOffset, nextAssembleIndex, phase };
    } catch {
      return {
        nextPlaylistIndex: fallbackIndex,
        nextTrackOffset: fallbackTrackOffset,
        nextAssembleIndex: fallbackAssembleIndex,
        phase: 'collect',
      };
    }
  }

  static createAssemblyState(): ResumableExportAssemblyState {
    return {
      summary_headers: ['Playlist Name', 'Owner', 'Track Count', 'Duration'],
      summary_rows: [],
      worksheets: [],
      csv_chunks: [],
      next_assemble_index: 0,
    };
  }

  static createResumeToken(): string {
    return crypto.randomUUID();
  }

  static createJobState(options: {
    jobId: string;
    userId: string;
    playlistIds: string[];
    fileFormat: 'xlsx' | 'csv' | 'json';
    includeAudioFeatures: boolean;
    traceId?: string;
  }): ResumableExportJobState {
    const cursor = ExportService.encodeCursor(0, 'collect', 0);
    return {
      job_id: options.jobId,
      user_id: options.userId,
      status: 'running',
      phase: 'collect',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      playlist_ids: options.playlistIds,
      playlist_count: options.playlistIds.length,
      processed_count: 0,
      track_count: 0,
      file_format: options.fileFormat,
      include_audio_features: options.includeAudioFeatures,
      current_cursor: cursor,
      current_resume_token: ExportService.createResumeToken(),
      next_playlist_index: 0,
      current_track_offset: 0,
      assemble_index: 0,
      track_page_size: 100,
      playlist_progress: {},
      continuation_required: options.playlistIds.length > 0,
      progress: 0,
      trace_id: options.traceId,
    };
  }

  static validateStepRequest(job: ResumableExportJobState, cursor: string, resumeToken: string): void {
    if (job.status === 'completed') {
      return;
    }

    if (cursor !== job.current_cursor || resumeToken !== job.current_resume_token) {
      throw new ResumableExportConflictError(
        'Stale cursor or resume token',
        job.current_cursor,
        job.current_resume_token,
      );
    }
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

    const decodedCursor = ExportService.decodeCursor(
      job.current_cursor,
      job.next_playlist_index,
      job.current_track_offset,
      job.assemble_index,
    );

    if (job.phase === 'assemble' || decodedCursor.phase === 'assemble' || job.status === 'assembling') {
      return this.runAssemblePhaseStep(job, exportDataList, assemblyState, maxPlaylistsPerStep, decodedCursor.nextAssembleIndex);
    }

    let nextPlaylistIndex = decodedCursor.nextPlaylistIndex;
    let nextTrackOffset = decodedCursor.nextTrackOffset;
    let remainingSlices = Math.max(maxPlaylistsPerStep, 1);

    while (remainingSlices > 0 && nextPlaylistIndex < job.playlist_ids.length) {
      const playlistId = job.playlist_ids[nextPlaylistIndex];
      const existingExportData = exportDataList.find((item) => item.playlist.id === playlistId);
      const playlistProgress = job.playlist_progress[playlistId] || {
        next_offset: nextTrackOffset,
        total_tracks: existingExportData?.playlist.total_tracks || 0,
        collected_tracks: existingExportData?.tracks.length || 0,
        done: false,
      };
      const slice = await this.generatePlaylistExportSlice(playlistId, {
        includeAudioFeatures: job.include_audio_features,
        offset: playlistProgress.next_offset,
        limit: job.track_page_size,
        existingExportData,
      });

      const mergedExportData = this.mergeExportSlice(existingExportData, slice.exportData);
      const existingIndex = exportDataList.findIndex((item) => item.playlist.id === playlistId);

      const totalTracks = slice.totalTracks || mergedExportData.playlist.total_tracks || mergedExportData.tracks.length;
      const collectedTracks = mergedExportData.tracks.length;
      // Advance the Spotify cursor by the raw page size (Spotify's `total` and
      // offsets count local/unavailable items that we filter out of `items`).
      // Using the filtered count here would skip offsets (duplicating later
      // pages) or stop early on a page whose valid tracks are all filtered out.
      const rawOffsetAfter = playlistProgress.next_offset + slice.rawCount;
      const playlistDone = slice.rawCount === 0
        || slice.rawCount < job.track_page_size
        || rawOffsetAfter >= totalTracks;

      job.playlist_progress[playlistId] = {
        next_offset: rawOffsetAfter,
        total_tracks: totalTracks,
        collected_tracks: collectedTracks,
        done: playlistDone,
      };

      if (playlistDone) {
        // Pre-assemble immediately to prevent raw track data accumulating in KV across steps.
        // Worksheet/CSV is built now and tracks are discarded, keeping exportDataList lean.
        if (job.file_format === 'csv') {
          assemblyState.csv_chunks.push(await this.buildCsvChunk(mergedExportData));
        } else {
          const usedNames = new Set(assemblyState.worksheets.map((w) => w.sheet_name.toLowerCase()));
          assemblyState.worksheets.push(this.buildWorksheetAssembly(mergedExportData, usedNames));
        }
        assemblyState.summary_rows.push([
          mergedExportData.playlist.name,
          mergedExportData.playlist.owner,
          mergedExportData.tracks.length,
          this.formatDuration(mergedExportData.total_duration_ms),
        ]);
        assemblyState.next_assemble_index = (assemblyState.next_assemble_index || 0) + 1;

        // Store a tracks-free sentinel so the assemble phase can identify pre-assembled entries.
        const strippedData = { ...mergedExportData, tracks: [] as typeof mergedExportData.tracks };
        if (existingIndex >= 0) {
          exportDataList[existingIndex] = strippedData;
        } else {
          exportDataList.push(strippedData);
        }

        nextPlaylistIndex += 1;
        nextTrackOffset = 0;
      } else {
        if (existingIndex >= 0) {
          exportDataList[existingIndex] = mergedExportData;
        } else {
          exportDataList.push(mergedExportData);
        }
        nextTrackOffset = job.playlist_progress[playlistId].next_offset;
      }

      remainingSlices -= 1;
    }

    job.next_playlist_index = nextPlaylistIndex;
    job.current_track_offset = nextTrackOffset;
    job.processed_count = Object.values(job.playlist_progress).filter((progress) => progress.done).length;
    // Use playlist_progress totals since tracks are cleared from exportDataList upon completion.
    job.track_count = Object.values(job.playlist_progress).reduce((sum, p) => sum + p.collected_tracks, 0);
    job.updated_at = new Date().toISOString();
    job.last_completed_cursor = job.current_cursor;
    job.last_completed_token = job.current_resume_token;

    if (job.next_playlist_index >= job.playlist_ids.length) {
      const preAssembledCount = assemblyState.next_assemble_index || 0;
      const totalPlaylists = job.playlist_ids.length;
      job.phase = 'assemble';
      job.assemble_index = preAssembledCount;

      if (preAssembledCount >= totalPlaylists) {
        // All playlists were pre-assembled inline during collect — complete immediately.
        job.status = 'completed';
        job.progress = 100;
        job.continuation_required = false;
        job.completed_at = new Date().toISOString();
        job.file_url = `/export/jobs/${job.job_id}/download`;
        job.file_size = JSON.stringify(assemblyState).length;
        job.result = { download_id: job.job_id };
      } else {
        job.status = 'assembling';
        job.progress = this.calculateAssembleProgress(job, totalPlaylists);
        job.continuation_required = true;
      }

      job.current_cursor = ExportService.encodeCursor(job.next_playlist_index, 'assemble', 0, job.assemble_index);
      job.current_resume_token = ExportService.createResumeToken();
      return { job, exportDataList, assemblyState };
    }

    job.phase = 'collect';
    job.status = 'running';
    job.continuation_required = true;
    job.progress = this.calculateJobProgress(job);
    job.current_cursor = ExportService.encodeCursor(job.next_playlist_index, 'collect', job.current_track_offset, job.assemble_index);
    job.current_resume_token = ExportService.createResumeToken();

    return { job, exportDataList, assemblyState };
  }

  private async runAssemblePhaseStep(
    job: ResumableExportJobState,
    exportDataList: ExportData[],
    assemblyState: ResumableExportAssemblyState,
    maxPlaylistsPerStep: number,
    startAssembleIndex: number,
  ): Promise<ResumableExportStepResult> {
    const totalPlaylists = exportDataList.length;
    let assembleIndex = Math.max(0, startAssembleIndex || assemblyState.next_assemble_index || job.assemble_index || 0);
    let remaining = Math.max(maxPlaylistsPerStep, 1);

    while (remaining > 0 && assembleIndex < totalPlaylists) {
      const exportData = exportDataList[assembleIndex];

      // Playlists with no tracks were pre-assembled inline during the collect phase — skip them.
      if (exportData.tracks.length === 0) {
        assembleIndex += 1;
        continue;
      }

      if (job.file_format === 'csv') {
        assemblyState.csv_chunks.push(await this.buildCsvChunk(exportData));
      } else {
        const usedNames = new Set(assemblyState.worksheets.map((w) => w.sheet_name.toLowerCase()));
        assemblyState.worksheets.push(this.buildWorksheetAssembly(exportData, usedNames));
      }
      assemblyState.summary_rows.push([
        exportData.playlist.name,
        exportData.playlist.owner,
        exportData.tracks.length,
        this.formatDuration(exportData.total_duration_ms),
      ]);
      assembleIndex += 1;
      remaining -= 1;
    }

    assemblyState.next_assemble_index = assembleIndex;
    job.phase = 'assemble';
    job.status = assembleIndex >= totalPlaylists ? 'completed' : 'assembling';
    job.assemble_index = assembleIndex;
    job.updated_at = new Date().toISOString();
    job.last_completed_cursor = job.current_cursor;
    job.last_completed_token = job.current_resume_token;

    if (assembleIndex >= totalPlaylists) {
      job.progress = 100;
      job.continuation_required = false;
      job.completed_at = new Date().toISOString();
      job.file_url = `/export/jobs/${job.job_id}/download`;
      job.file_size = JSON.stringify(assemblyState).length;
      job.result = {
        download_id: job.job_id,
      };
    } else {
      job.progress = this.calculateAssembleProgress(job, totalPlaylists);
      job.continuation_required = true;
    }

    job.current_cursor = ExportService.encodeCursor(job.next_playlist_index, 'assemble', 0, assembleIndex);
    job.current_resume_token = ExportService.createResumeToken();
    return { job, exportDataList, assemblyState };
  }

  async generatePlaylistExport(playlistId: string, options?: { includeAudioFeatures?: boolean }): Promise<ExportData> {
    const spotifyService = new SpotifyService(this.accessToken);
    const includeAudioFeatures = options?.includeAudioFeatures === true;

    // Get playlist details
    const playlist = await spotifyService.getPlaylist(playlistId);

    // Get all tracks (handle pagination)
    const allTracks = [];
    let offset = 0;
    const limit = 100;

    let hasMore = true;
    while (hasMore) {
      const tracksData = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
      allTracks.push(...tracksData.items);

      // Advance by the raw page size and stop on a short page. Using the filtered
      // items.length here would stop early or skip offsets on playlists that
      // contain local/unavailable items.
      if (tracksData.rawCount < limit) { hasMore = false; break; }
      offset += limit;
    }

    const exportTracks = await this.buildExportTracks(allTracks, includeAudioFeatures, spotifyService);
    const totalDurationMs = this.calculateTotalDurationMs(allTracks);

    return {
      playlist: this.buildPlaylistMetadata(playlist, exportTracks.length),
      tracks: exportTracks,
      total_duration_ms: totalDurationMs,
      generated_at: new Date().toISOString()
    };
  }

  async generatePlaylistExportSlice(
    playlistId: string,
    options: {
      includeAudioFeatures?: boolean;
      offset?: number;
      limit?: number;
      existingExportData?: ExportData;
    },
  ): Promise<{ exportData: ExportData; fetchedCount: number; rawCount: number; totalTracks: number }> {
    const spotifyService = new SpotifyService(this.accessToken);
    const includeAudioFeatures = options.includeAudioFeatures === true;
    const offset = Math.max(0, options.offset || 0);
    const limit = Math.max(1, options.limit || 100);
    const existingExportData = options.existingExportData;
    const playlist = existingExportData?.playlist.id === playlistId
      ? undefined
      : await spotifyService.getPlaylist(playlistId);
    const tracksData = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
    const exportTracks = await this.buildExportTracks(tracksData.items, includeAudioFeatures, spotifyService);
    const totalDurationMs = this.calculateTotalDurationMs(tracksData.items);
    const playlistMetadata = existingExportData?.playlist || this.buildPlaylistMetadata(playlist, tracksData.total);

    return {
      exportData: {
        playlist: {
          ...playlistMetadata,
          total_tracks: tracksData.total || playlistMetadata.total_tracks,
        },
        tracks: exportTracks,
        total_duration_ms: totalDurationMs,
        generated_at: new Date().toISOString(),
      },
      fetchedCount: tracksData.items.length,
      rawCount: tracksData.rawCount,
      totalTracks: tracksData.total,
    };
  }

  private mergeExportSlice(existingExportData: ExportData | undefined, sliceExportData: ExportData): ExportData {
    if (!existingExportData) {
      return sliceExportData;
    }

    return {
      playlist: {
        ...existingExportData.playlist,
        ...sliceExportData.playlist,
      },
      tracks: [...existingExportData.tracks, ...sliceExportData.tracks],
      total_duration_ms: existingExportData.total_duration_ms + sliceExportData.total_duration_ms,
      generated_at: sliceExportData.generated_at,
    };
  }

  private calculateJobProgress(job: ResumableExportJobState): number {
    const playlistIds = job.playlist_ids;
    if (playlistIds.length === 0) {
      return 100;
    }

    let aggregateProgress = 0;
    for (const playlistId of playlistIds) {
      const progress = job.playlist_progress[playlistId];
      if (!progress) {
        continue;
      }
      if (progress.done) {
        aggregateProgress += 1;
        continue;
      }
      if (progress.total_tracks > 0) {
        aggregateProgress += Math.min(progress.collected_tracks / progress.total_tracks, 0.99);
      }
    }

    return Math.min(99, Math.floor((aggregateProgress / playlistIds.length) * 100));
  }

  private calculateAssembleProgress(job: ResumableExportJobState, totalPlaylists: number): number {
    if (totalPlaylists <= 0) {
      return 100;
    }
    const assembleProgress = Math.min(job.assemble_index / totalPlaylists, 0.99);
    return Math.min(99, 95 + Math.floor(assembleProgress * 4));
  }

  private async buildCsvChunk(exportData: ExportData): Promise<string> {
    const csvBytes = await this.generateCsvFile(exportData);
    return new TextDecoder().decode(csvBytes);
  }

  private buildWorksheetAssembly(exportData: ExportData, usedSheetNames: Set<string>): WorksheetAssemblyData {
    const headers = this.getTrackHeaders();
    const baseName = this.sanitizeSheetName(`${exportData.playlist.name} - ${exportData.playlist.owner}`);
    return {
      sheet_name: this.uniquifySheetName(baseName, usedSheetNames),
      playlist_name: exportData.playlist.name,
      playlist_owner: exportData.playlist.owner,
      playlist_followers: exportData.playlist.followers,
      playlist_cover_image_url: exportData.playlist.cover_image_url,
      playlist_description: exportData.playlist.description || 'N/A',
      playlist_url: exportData.playlist.url || '',
      total_duration: this.formatDuration(exportData.total_duration_ms),
      headers,
      rows: exportData.tracks.map((track) => headers.map((header) => (track as any)[header] ?? '')),
    };
  }

  async generateCombinedExcelFileFromAssembly(
    assemblyState: ResumableExportAssemblyState,
    renderMode: XlsxRenderMode = 'auto',
  ): Promise<ArrayBuffer> {
    const totalWorksheets = Array.isArray(assemblyState.worksheets) ? assemblyState.worksheets.length : 0;
    const totalTrackRows = (assemblyState.worksheets || []).reduce(
      (sum, worksheet) => sum + (Array.isArray(worksheet.rows) ? worksheet.rows.length : 0),
      0,
    );

    // Rich ExcelJS rendering (tables + cover images) is CPU heavy on large jobs under
    // Workers CPU limits. Use it when safely sized; otherwise degrade to a lightweight
    // renderer that prioritizes successful combined download.
    const useRichRenderer = renderMode === 'rich'
      ? true
      : renderMode === 'lite'
        ? false
        : totalWorksheets <= 18 && totalTrackRows <= 2400;
    if (!useRichRenderer) {
      console.warn('[export] using lightweight XLSX assembly renderer due to job size', {
        worksheetCount: totalWorksheets,
        trackRows: totalTrackRows,
      });
      return this.generateCombinedExcelFileFromAssemblyLite(assemblyState);
    }

    // Reconstruct lightweight ExportData objects and reuse the full ExcelJS renderer
    // so assembled resumable exports keep table styles and embedded cover images.
    const exportDataList: ExportData[] = assemblyState.worksheets.map((worksheet) => {
      const tracks = worksheet.rows.map((row) => {
        const track: Partial<ExportTrack> = {};
        for (let i = 0; i < worksheet.headers.length; i += 1) {
          const key = worksheet.headers[i] as keyof ExportTrack;
          (track as any)[key] = row[i] ?? '';
        }
        return track as ExportTrack;
      });

      return {
        playlist: {
          id: '',
          name: worksheet.playlist_name,
          description: worksheet.playlist_description || '',
          total_tracks: tracks.length,
          owner: worksheet.playlist_owner,
          followers: worksheet.playlist_followers,
          url: worksheet.playlist_url || '',
          cover_image_url: worksheet.playlist_cover_image_url,
        },
        tracks,
        total_duration_ms: 0,
        generated_at: new Date().toISOString(),
      };
    });

    return this.generateCombinedExcelFile(exportDataList);
  }

  private async generateCombinedExcelFileFromAssemblyLite(assemblyState: ResumableExportAssemblyState): Promise<ArrayBuffer> {
    const workbook = new ExcelJS.Workbook();

    const summarySheet = workbook.addWorksheet('Playlists');
    summarySheet.columns = [
      { key: 'A', width: 29 },
      { key: 'B', width: 24 },
      { key: 'C', width: 16 },
      { key: 'D', width: 19 },
    ];
    summarySheet.addRow(assemblyState.summary_headers);
    for (const row of assemblyState.summary_rows) {
      summarySheet.addRow(row);
    }

    for (const worksheet of assemblyState.worksheets) {
      const sheet = workbook.addWorksheet(worksheet.sheet_name);
      sheet.columns = [
        { key: 'A', width: 30 },
        { key: 'B', width: 40 },
        { key: 'C', width: 40 },
        { key: 'D', width: 15 },
        { key: 'E', width: 60 },
        { key: 'F', width: 12 },
        { key: 'G', width: 14 },
        { key: 'H', width: 12 },
        { key: 'I', width: 12 },
        { key: 'J', width: 12 },
        { key: 'K', width: 12 },
        { key: 'L', width: 16 },
        { key: 'M', width: 12 },
        { key: 'N', width: 12 },
        { key: 'O', width: 12 },
        { key: 'P', width: 14 },
      ];

      sheet.addRow([worksheet.playlist_name]);
      sheet.addRow([`Created by: ${worksheet.playlist_owner}`]);
      sheet.addRow([`Followers: ${worksheet.playlist_followers}`]);
      sheet.addRow([`Tracks exported: ${worksheet.rows.length}`]);
      sheet.addRow([`Total duration: ${worksheet.total_duration}`]);
      if (worksheet.playlist_url) {
        sheet.addRow([{
          text: `Playlist URL: ${worksheet.playlist_url}`,
          hyperlink: worksheet.playlist_url,
        }]);
      } else {
        sheet.addRow(['Playlist URL: N/A']);
      }
      sheet.addRow([`Description: ${worksheet.playlist_description || 'N/A'}`]);
      sheet.addRow([]);
      sheet.addRow([]);
      sheet.addRow([]);
      sheet.addRow(worksheet.headers);

      for (const row of worksheet.rows) {
        const excelRow = sheet.addRow(row);
        const spotifyUrl = row[4];
        if (typeof spotifyUrl === 'string' && spotifyUrl.startsWith('http')) {
          const cell = excelRow.getCell(5);
          cell.value = { text: spotifyUrl, hyperlink: spotifyUrl };
          cell.font = {
            color: { argb: 'FF0563C1' },
            underline: true,
          };
        }
      }

      if (worksheet.rows.length > 0) {
        sheet.autoFilter = {
          from: {
            row: 11,
            column: 1,
          },
          to: {
            row: 11 + worksheet.rows.length,
            column: worksheet.headers.length,
          }
        };
      }
    }

    const buffer = await workbook.xlsx.writeBuffer();
    return buffer as ArrayBuffer;
  }

  async generateCombinedCsvFromAssembly(assemblyState: ResumableExportAssemblyState): Promise<ArrayBuffer> {
    return new TextEncoder().encode(assemblyState.csv_chunks.join('\n\n')).buffer as ArrayBuffer;
  }

  /**
   * Serialize export data as nested per-playlist JSON: a top-level object with
   * a `playlists` array, each carrying playlist metadata and a `tracks` array
   * of track objects (same fields as the XLSX columns).
   */
  generateCombinedJson(exportDataList: ExportData[]): ArrayBuffer {
    const payload = {
      generated_at: new Date().toISOString(),
      playlist_count: exportDataList.length,
      playlists: exportDataList.map((exportData) => ({
        name: exportData.playlist.name,
        owner: exportData.playlist.owner,
        followers: exportData.playlist.followers,
        description: exportData.playlist.description || '',
        url: exportData.playlist.url || '',
        cover_image_url: exportData.playlist.cover_image_url,
        total_tracks: exportData.playlist.total_tracks,
        total_duration: this.formatDuration(exportData.total_duration_ms),
        tracks: exportData.tracks,
      })),
    };
    return new TextEncoder().encode(JSON.stringify(payload, null, 2)).buffer as ArrayBuffer;
  }

  /**
   * Same nested per-playlist JSON, reconstructed from the assembly worksheets
   * used by the resumable export path (track objects are zipped back from the
   * worksheet headers + rows).
   */
  generateCombinedJsonFromAssembly(assemblyState: ResumableExportAssemblyState): ArrayBuffer {
    const payload = {
      generated_at: new Date().toISOString(),
      playlist_count: assemblyState.worksheets.length,
      playlists: assemblyState.worksheets.map((worksheet) => ({
        name: worksheet.playlist_name,
        owner: worksheet.playlist_owner,
        followers: worksheet.playlist_followers,
        description: worksheet.playlist_description || '',
        url: worksheet.playlist_url || '',
        cover_image_url: worksheet.playlist_cover_image_url,
        total_tracks: worksheet.rows.length,
        total_duration: worksheet.total_duration,
        tracks: worksheet.rows.map((row) => {
          const track: Record<string, ExportCellValue> = {};
          for (let i = 0; i < worksheet.headers.length; i += 1) {
            track[worksheet.headers[i]] = row[i] ?? '';
          }
          return track;
        }),
      })),
    };
    return new TextEncoder().encode(JSON.stringify(payload, null, 2)).buffer as ArrayBuffer;
  }

  private buildPlaylistMetadata(playlist: any, fallbackTrackCount: number): ExportData['playlist'] {
    return {
      id: playlist?.id || '',
      name: playlist?.name || 'Unknown Playlist',
      description: playlist?.description || '',
      total_tracks: playlist?.items?.total ?? playlist?.tracks?.total ?? fallbackTrackCount,
      owner: playlist?.owner?.display_name || 'Unknown',
      followers: playlist?.followers?.total || 0,
      url: playlist?.external_urls?.spotify || '',
      cover_image_url: Array.isArray(playlist?.images) && playlist.images.length > 0 ? playlist.images[0]?.url : undefined,
    };
  }

  private calculateTotalDurationMs(items: any[]): number {
    return items
      .filter((item: any) => item.track && typeof item.track.duration_ms === 'number')
      .reduce((acc: number, item: any) => acc + (item.track.duration_ms || 0), 0);
  }

  private async buildExportTracks(allTracks: any[], includeAudioFeatures: boolean, spotifyService: SpotifyService): Promise<ExportTrack[]> {
    const trackIds = allTracks
      .filter((item: any) => item.track && item.track.id)
      .map((item: any) => item.track.id);

    const audioFeaturesMap = await this.loadAudioFeaturesMap(trackIds, includeAudioFeatures, spotifyService);

    return allTracks
      .filter((item: any) => item.track)
      .map((item: any) => this.mapTrackForExport(item.track, audioFeaturesMap.get(item.track.id)));
  }

  private async loadAudioFeaturesMap(trackIds: string[], includeAudioFeatures: boolean, spotifyService: SpotifyService): Promise<Map<string, any>> {
    const audioFeaturesMap = new Map<string, any>();
    let audioFeaturesUnavailable = false;

    if (!includeAudioFeatures || trackIds.length === 0) {
      return audioFeaturesMap;
    }

    for (let i = 0; i < trackIds.length; i += 100) {
      if (audioFeaturesUnavailable) {
        break;
      }
      const batch = trackIds.slice(i, i + 100);
      try {
        const audioFeatures = await spotifyService.getMultipleAudioFeatures(batch);
        audioFeatures.forEach((feature) => {
          if (feature) {
            audioFeaturesMap.set(feature.id, feature);
          }
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        if (/HTTP\s+(401|403)/i.test(message)) {
          audioFeaturesUnavailable = true;
          console.warn('Audio-features API unavailable for this token; skipping remaining batches', {
            batchStart: i,
            batchSize: batch.length,
            error: message,
          });
          continue;
        }
        console.warn('Audio-features batch failed; continuing without those features', {
          batchStart: i,
          batchSize: batch.length,
          error: message,
        });
      }
    }

    return audioFeaturesMap;
  }

  private mapTrackForExport(track: any, audioFeatures: any): ExportTrack {
    const keyMap = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const modeMap: Record<number, string> = { 0: 'minor', 1: 'major' };
    const keyName = typeof audioFeatures?.key === 'number' && audioFeatures.key >= 0 && audioFeatures.key < keyMap.length
      ? keyMap[audioFeatures.key]
      : null;
    const modeName = typeof audioFeatures?.mode === 'number' ? modeMap[audioFeatures.mode] : null;
    const keyValue = keyName ? `${keyName}${modeName ? ` ${modeName}` : ''}` : 'N/A';

    return {
      Artist: track.artists.map((artist: any) => artist.name).join(', '),
      Album: track.album?.name || '',
      Track: track.name,
      Duration: this.formatDuration(track.duration_ms),
      'Spotify URL': track.external_urls?.spotify || '',
      Tempo: typeof audioFeatures?.tempo === 'number' ? Number(audioFeatures.tempo.toFixed(2)) : 'N/A',
      Key: keyValue,
      Danceability: typeof audioFeatures?.danceability === 'number' ? Number(audioFeatures.danceability.toFixed(3)) : 'N/A',
      Energy: typeof audioFeatures?.energy === 'number' ? Number(audioFeatures.energy.toFixed(3)) : 'N/A',
      Valence: typeof audioFeatures?.valence === 'number' ? Number(audioFeatures.valence.toFixed(3)) : 'N/A',
      Acousticness: typeof audioFeatures?.acousticness === 'number' ? Number(audioFeatures.acousticness.toFixed(3)) : 'N/A',
      Instrumentalness: typeof audioFeatures?.instrumentalness === 'number' ? Number(audioFeatures.instrumentalness.toFixed(3)) : 'N/A',
      Liveness: typeof audioFeatures?.liveness === 'number' ? Number(audioFeatures.liveness.toFixed(3)) : 'N/A',
      Speechiness: typeof audioFeatures?.speechiness === 'number' ? Number(audioFeatures.speechiness.toFixed(3)) : 'N/A',
      Loudness: typeof audioFeatures?.loudness === 'number' ? Number(audioFeatures.loudness.toFixed(1)) : 'N/A',
      'Time Signature': typeof audioFeatures?.time_signature === 'number' ? audioFeatures.time_signature : 'N/A',
    };
  }

  async generateCsvFile(exportData: ExportData): Promise<ArrayBuffer> {
    const headers = this.getTrackHeaders();

    // Create CSV content
    let csvContent = headers.join(',') + '\n';

    // Add playlist info as first row
    csvContent += `"Playlist: ${exportData.playlist.name}",,,,"Total Tracks: ${exportData.playlist.total_tracks}",,,,"Owner: ${exportData.playlist.owner}",,,,,,,\n`;
    csvContent += '\n'; // Empty row

    // Add track data
    for (const track of exportData.tracks) {
      const row = headers.map((header) => this.escapeCsvValue(String((track as any)[header] ?? '')));

      csvContent += row.join(',') + '\n';
    }

    // Convert to ArrayBuffer
    const encoder = new TextEncoder();
    return encoder.encode(csvContent).buffer as ArrayBuffer;
  }

  async generateExcelFile(exportData: ExportData): Promise<ArrayBuffer> {
    return this.generateCombinedExcelFile([exportData]);
  }

  async generateCombinedExcelFile(exportDataList: ExportData[]): Promise<ArrayBuffer> {
    const workbook = new ExcelJS.Workbook();
    const summarySheet = workbook.addWorksheet('Playlists');
    summarySheet.columns = [
      { header: 'Playlist Name', key: 'name', width: 29 },
      { header: 'Owner', key: 'owner', width: 24 },
      { header: 'Track Count', key: 'track_count', width: 16 },
      { header: 'Duration', key: 'duration', width: 19 },
    ];

    const summaryHeader = summarySheet.getRow(1);
    summaryHeader.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 13 };
    summaryHeader.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF4F81BD' },
    };

    for (const exportData of exportDataList) {
      summarySheet.addRow({
        name: exportData.playlist.name,
        owner: exportData.playlist.owner,
        track_count: exportData.tracks.length,
        duration: this.formatDuration(exportData.total_duration_ms),
      });
    }

    const headers = this.getTrackHeaders();
    const usedSheetNames = new Set<string>();

    for (const exportData of exportDataList) {
      const baseName = this.sanitizeSheetName(`${exportData.playlist.name} - ${exportData.playlist.owner}`);
      const sheetName = this.uniquifySheetName(baseName, usedSheetNames);

      const sheet = workbook.addWorksheet(sheetName);
      sheet.columns = [
        { key: 'A', width: 30 },
        { key: 'B', width: 40 },
        { key: 'C', width: 40 },
        { key: 'D', width: 15 },
        { key: 'E', width: 60 },
        { key: 'F', width: 12 },
        { key: 'G', width: 14 },
        { key: 'H', width: 12 },
        { key: 'I', width: 12 },
        { key: 'J', width: 12 },
        { key: 'K', width: 12 },
        { key: 'L', width: 16 },
        { key: 'M', width: 12 },
        { key: 'N', width: 12 },
        { key: 'O', width: 12 },
        { key: 'P', width: 14 },
      ];

      sheet.getCell('A1').value = exportData.playlist.name;
      sheet.getCell('A1').font = { bold: true, size: 16 };
      sheet.getCell('A2').value = `Created by: ${exportData.playlist.owner}`;
      sheet.getCell('A3').value = `Followers: ${exportData.playlist.followers}`;
      sheet.getCell('A4').value = `Tracks exported: ${exportData.tracks.length}`;
      sheet.getCell('A5').value = `Total duration: ${this.formatDuration(exportData.total_duration_ms)}`;
      sheet.getCell('A6').value = `Playlist URL: ${exportData.playlist.url || 'N/A'}`;
      sheet.getCell('A7').value = `Description: ${exportData.playlist.description || 'N/A'}`;

      if (exportData.playlist.url) {
        sheet.getCell('A6').value = {
          text: `Playlist URL: ${exportData.playlist.url}`,
          hyperlink: exportData.playlist.url,
        };
      }

      // Try to embed a cover image like legacy desktop export. Failure should never block export.
      await this.tryAddCoverImage(workbook, sheet, exportData.playlist.cover_image_url);

      sheet.getRow(11).values = headers;
      const headerRow = sheet.getRow(11);
      headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
      headerRow.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FF4F81BD' },
      };

      let rowNumber = 12;
      for (const track of exportData.tracks) {
        const rowValues = headers.map((header) => (track as any)[header] ?? '');
        sheet.getRow(rowNumber).values = rowValues;
        const urlValue = (track as any)['Spotify URL'];
        if (typeof urlValue === 'string' && urlValue.startsWith('http')) {
          sheet.getCell(`E${rowNumber}`).value = { text: urlValue, hyperlink: urlValue };
          sheet.getCell(`E${rowNumber}`).font = { color: { argb: 'FF0563C1' }, underline: true };
        }
        rowNumber += 1;
      }

      if (rowNumber > 12) {
        // Compute last column letter (headers.length <= 26 covers all our column sets).
        const lastColLetter = String.fromCharCode(64 + headers.length);
        const fullRef = `A11:${lastColLetter}${rowNumber - 1}`;
        const tableName = `tbl_${sheetName.replace(/[^A-Za-z0-9_]/g, '').slice(0, 20)}_${Math.floor(Math.random() * 1000)}`;
        // Pass rows:[] so ExcelJS's store() writes no cells (they are already populated above).
        // Then patch tableRef / autoFilterRef so the XML declares the full data range.
        const tbl = sheet.addTable({
          name: tableName,
          ref: 'A11',
          headerRow: true,
          style: {
            theme: 'TableStyleMedium9',
            showRowStripes: true,
          },
          columns: headers.map((header) => ({ name: header })),
          rows: [],
        });
        (tbl as any).table.tableRef = fullRef;
        (tbl as any).table.autoFilterRef = fullRef;
      }

      for (let r = 1; r <= rowNumber; r += 1) {
        const row = sheet.getRow(r);
        row.alignment = { vertical: 'middle', horizontal: 'left', wrapText: r > 7 };
      }
    }

    const buffer = await workbook.xlsx.writeBuffer();
    return buffer as ArrayBuffer;
  }

  private async tryAddCoverImage(workbook: ExcelJS.Workbook, sheet: ExcelJS.Worksheet, imageUrl?: string): Promise<void> {
    if (!imageUrl) {
      return;
    }

    try {
      const response = await fetch(imageUrl);
      if (!response.ok) {
        console.warn('[export] cover image fetch failed', { imageUrl, status: response.status });
        return;
      }
      const bytes = await response.arrayBuffer();
      const contentType = response.headers.get('content-type') || '';
      const extension = contentType.includes('jpeg') || contentType.includes('jpg') ? 'jpeg' : 'png';
      const mimeType = extension === 'jpeg' ? 'image/jpeg' : 'image/png';
      const base64 = this.arrayBufferToBase64(bytes);
      const imageId = workbook.addImage({
        base64: `data:${mimeType};base64,${base64}`,
        extension,
      });
      sheet.addImage(imageId, {
        tl: { col: 1.1, row: 0.1 },
        ext: { width: 120, height: 120 },
      });
    } catch (error) {
      // Ignore image failures to keep export resilient, but log for diagnosis.
      console.warn('[export] cover image embedding failed', {
        imageUrl,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private arrayBufferToBase64(bytes: ArrayBuffer): string {
    if (typeof Buffer !== 'undefined') {
      return Buffer.from(bytes).toString('base64');
    }

    const byteArray = new Uint8Array(bytes);
    const chars = new Array<string>(byteArray.length);
    for (let i = 0; i < byteArray.length; i++) {
      chars[i] = String.fromCharCode(byteArray[i]);
    }
    return btoa(chars.join(''));
  }

  private formatDuration(ms: number): string {
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    if (hours > 0) {
      return `${hours}:${remainingMinutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    return `${remainingMinutes}:${seconds.toString().padStart(2, '0')}`;
  }

  private sanitizeSheetName(name: string): string {
    const cleaned = name.replace(/[\\/*?:[\]]/g, ' ').trim();
    return (cleaned || 'Playlist').slice(0, 31);
  }

  // Make a sheet name unique within `usedNames` (case-insensitive, per Excel).
  // Appends " (N)" with N starting at 2, shrinking the base to fit within 31 chars.
  private uniquifySheetName(base: string, usedNames: Set<string>): string {
    const key = base.toLowerCase();
    if (!usedNames.has(key)) {
      usedNames.add(key);
      return base;
    }
    for (let n = 2; n <= 9999; n += 1) {
      const suffix = ` (${n})`;
      const candidate = base.slice(0, 31 - suffix.length) + suffix;
      const candidateKey = candidate.toLowerCase();
      if (!usedNames.has(candidateKey)) {
        usedNames.add(candidateKey);
        return candidate;
      }
    }
    return base; // unreachable in practice
  }

  private getTrackHeaders(): string[] {
    return [
      'Artist',
      'Album',
      'Track',
      'Duration',
      'Spotify URL',
      'Tempo',
      'Key',
      'Danceability',
      'Energy',
      'Valence',
      'Acousticness',
      'Instrumentalness',
      'Liveness',
      'Speechiness',
      'Loudness',
      'Time Signature',
    ];
  }

  private escapeCsvValue(value: string): string {
    if (value.includes(',') || value.includes('"') || value.includes('\n')) {
      return `"${value.replace(/"/g, '""')}"`;
    }
    return value;
  }

  async generateAdvancedExcelFile(exportData: ExportData): Promise<ArrayBuffer> {
    // Keep advanced export aligned with the primary XLSX output.
    return this.generateExcelFile(exportData);
  }
}

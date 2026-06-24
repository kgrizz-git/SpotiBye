export interface ExportTrack {
  [key: string]: string | number;
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

export type ExportCellValue = string | number;

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

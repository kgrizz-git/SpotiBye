// ResumableExportJobState lives in services/export-types.ts and is imported directly from there. We do not re-export it here to keep helpers/types.ts as a leaf module.

export type ExportFormat = 'xlsx' | 'csv' | 'json';

export type BatchExportStatus = {
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

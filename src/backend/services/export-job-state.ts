import type { ResumableExportJobState } from './export-types';
import { encodeCursor } from './export-cursor';

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

export function createResumeToken(): string {
  return crypto.randomUUID();
}

export function createJobState(options: {
  jobId: string;
  userId: string;
  playlistIds: string[];
  fileFormat: 'xlsx' | 'csv' | 'json';
  includeAudioFeatures: boolean;
  traceId?: string;
}): ResumableExportJobState {
  const cursor = encodeCursor(0, 'collect', 0);
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
    current_resume_token: createResumeToken(),
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

export function validateStepRequest(job: ResumableExportJobState, cursor: string, resumeToken: string): void {
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

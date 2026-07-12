export interface AnalysisQueueMessage {
  job_id: string;
  playlist_id: string;
  user_id: string;
  session_id: string;
  enqueued_at: string;
  attempt: number;
  /** When true, per-track ReccoBeats cache keys are cleared before refetch. */
  force_enrichment?: boolean;
}

export type AnalysisJobStatus =
  | 'queued'
  | 'processing'
  | 'retrying'
  | 'completed'
  | 'failed';

export interface AnalysisStatusRecord {
  job_id: string;
  playlist_id: string;
  user_id: string;
  status: AnalysisJobStatus;
  progress: number;
  queued_at?: string;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  retry_after?: string;
  attempt?: number;
  error?: string;
  updated_at?: string;
}

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

/** Fan-out batch message: one chunk of a large-playlist analysis job. */
export interface AnalysisChunkMessage extends AnalysisQueueMessage {
  chunk_id: string;
  chunk_index: number;
  chunk_count: number;
  track_ids: string[];
  artist_ids: string[];
  /**
   * Skip per-track cache lookup and refetch. Never deletes — POST clears
   * once via deleteKnownKeys; chunks must not re-delete sibling keys.
   */
  force_resolve?: boolean;
}

/** DO-side fan-out countdown state (NOT part of the user status record). */
export interface FanoutCountdownState {
  expected: number;
  received: Record<string, 'ok' | 'failed'>;
  /** ISO timestamp of the finalizer claim, or null when unclaimed. */
  finalizerClaimedAt: string | null;
  /** Chunk holding the finalizer claim (for same-chunk re-grant). */
  finalizerClaimedBy: string | null;
  created_at: string;
}

export interface ChunkRegistration {
  isFinalizer: boolean;
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

import { describe, it, expect } from 'vitest';
import { createJobState, validateStepRequest, createResumeToken, ResumableExportConflictError } from '../services/export-job-state';
import { decodeCursor } from '../services/export-cursor';

describe('createJobState', () => {
  const base = {
    jobId: 'j1',
    userId: 'u1',
    playlistIds: ['p1', 'p2'],
    fileFormat: 'xlsx' as const,
    includeAudioFeatures: false,
  };

  it('sets status to running and phase to collect', () => {
    const job = createJobState(base);
    expect(job.status).toBe('running');
    expect(job.phase).toBe('collect');
  });

  it('sets track_page_size to 100', () => {
    expect(createJobState(base).track_page_size).toBe(100);
  });

  it('sets continuation_required to true when playlistIds non-empty', () => {
    expect(createJobState(base).continuation_required).toBe(true);
  });

  it('sets continuation_required to false for empty playlistIds', () => {
    const job = createJobState({ ...base, playlistIds: [] });
    expect(job.continuation_required).toBe(false);
  });

  it('encodes a collect cursor at index 0', () => {
    const job = createJobState(base);
    const decoded = decodeCursor(job.current_cursor);
    expect(decoded.phase).toBe('collect');
    expect(decoded.nextPlaylistIndex).toBe(0);
  });

  it('populates identifiers correctly', () => {
    const job = createJobState({ ...base, traceId: 'trace-abc' });
    expect(job.job_id).toBe('j1');
    expect(job.user_id).toBe('u1');
    expect(job.trace_id).toBe('trace-abc');
    expect(job.playlist_count).toBe(2);
  });
});

describe('validateStepRequest', () => {
  function makeJob(overrides: Partial<any> = {}) {
    return {
      status: 'running',
      current_cursor: 'cursor-a',
      current_resume_token: 'token-a',
      ...overrides,
    } as any;
  }

  it('returns silently for completed jobs regardless of cursor/token', () => {
    expect(() =>
      validateStepRequest(makeJob({ status: 'completed' }), 'wrong', 'wrong'),
    ).not.toThrow();
  });

  it('passes matching cursor and token', () => {
    expect(() =>
      validateStepRequest(makeJob(), 'cursor-a', 'token-a'),
    ).not.toThrow();
  });

  it('throws ResumableExportConflictError on stale cursor', () => {
    expect(() =>
      validateStepRequest(makeJob(), 'old-cursor', 'token-a'),
    ).toThrow(ResumableExportConflictError);
  });

  it('throws ResumableExportConflictError on stale token', () => {
    expect(() =>
      validateStepRequest(makeJob(), 'cursor-a', 'old-token'),
    ).toThrow(ResumableExportConflictError);
  });

  it('conflict error carries latestCursor and latestResumeToken', () => {
    try {
      validateStepRequest(makeJob(), 'old', 'old');
    } catch (err) {
      expect(err).toBeInstanceOf(ResumableExportConflictError);
      expect((err as ResumableExportConflictError).latestCursor).toBe('cursor-a');
      expect((err as ResumableExportConflictError).latestResumeToken).toBe('token-a');
    }
  });
});

describe('createResumeToken', () => {
  it('returns a non-empty string', () => {
    expect(typeof createResumeToken()).toBe('string');
    expect(createResumeToken().length).toBeGreaterThan(0);
  });

  it('returns unique values on each call', () => {
    expect(createResumeToken()).not.toBe(createResumeToken());
  });
});

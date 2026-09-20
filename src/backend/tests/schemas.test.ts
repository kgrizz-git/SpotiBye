import { describe, it, expect } from 'vitest';
import { SessionDataSchema } from '../validation/schemas/session';
import { AnalysisQueueMessagePayloadSchema, parseQueuePayload } from '../validation/schemas/queue';
import { safeParseSession } from '../middleware/auth';

describe('SessionDataSchema', () => {
  it('parses valid session JSON', () => {
    const raw = JSON.stringify({
      user_id: 'user-1',
      access_token: 'token',
      refresh_token: 'refresh',
      expires_at: Date.now() + 60_000,
    });
    expect(safeParseSession(raw, 'session-1')).toEqual({
      user_id: 'user-1',
      access_token: 'token',
      refresh_token: 'refresh',
      expires_at: expect.any(Number),
    });
  });

  it('returns null for malformed session JSON', () => {
    expect(safeParseSession('not-json', 'session-1')).toBeNull();
    expect(safeParseSession(JSON.stringify({ user_id: 'x' }), 'session-1')).toBeNull();
  });

  it('accepts optional refresh_token in schema', () => {
    const result = SessionDataSchema.safeParse({
      user_id: 'user-1',
      access_token: 'token',
      expires_at: 1,
    });
    expect(result.success).toBe(true);
  });
});

describe('AnalysisQueueMessagePayloadSchema', () => {
  it('accepts payloads without attempt (set later from message.attempts)', () => {
    const result = AnalysisQueueMessagePayloadSchema.safeParse({
      job_id: '11111111-1111-4111-8111-111111111111',
      playlist_id: 'playlist1',
      user_id: 'user-1',
      session_id: 'session-1',
      enqueued_at: new Date().toISOString(),
    });
    expect(result.success).toBe(true);
  });

  it('rejects empty job_id', () => {
    const result = AnalysisQueueMessagePayloadSchema.safeParse({
      job_id: '',
      playlist_id: 'playlist1',
      user_id: 'user-1',
      session_id: 'session-1',
      enqueued_at: new Date().toISOString(),
    });
    expect(result.success).toBe(false);
  });

  it('preserves force_enrichment when present', () => {
    const result = AnalysisQueueMessagePayloadSchema.safeParse({
      job_id: '11111111-1111-4111-8111-111111111111',
      playlist_id: 'playlist1',
      user_id: 'user-1',
      session_id: 'session-1',
      enqueued_at: new Date().toISOString(),
      force_enrichment: true,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.force_enrichment).toBe(true);
    }
  });
});

describe('parseQueuePayload', () => {
  const base = {
    job_id: '11111111-1111-4111-8111-111111111111',
    playlist_id: 'playlist1',
    user_id: 'user-1',
    session_id: 'session-1',
    enqueued_at: new Date().toISOString(),
  };

  it('routes chunk bodies to the chunk schema without stripping coordinates', () => {
    const parsed = parseQueuePayload({
      ...base,
      chunk_id: 'job-1#0',
      chunk_index: 0,
      chunk_count: 3,
      track_ids: ['t1', 't2'],
      artist_ids: ['a1'],
    });
    expect(parsed.kind).toBe('chunk');
    if (parsed.kind === 'chunk') {
      expect(parsed.payload.chunk_id).toBe('job-1#0');
      expect(parsed.payload.track_ids).toEqual(['t1', 't2']);
    }
  });

  it('rejects chunk bodies with empty track_ids', () => {
    const parsed = parseQueuePayload({
      ...base,
      chunk_id: 'job-1#0',
      chunk_index: 0,
      chunk_count: 3,
      track_ids: [],
      artist_ids: [],
    });
    expect(parsed.kind).toBe('invalid');
  });

  it('rejects chunk bodies with negative index', () => {
    const parsed = parseQueuePayload({
      ...base,
      chunk_id: 'job-1#0',
      chunk_index: -1,
      chunk_count: 3,
      track_ids: ['t1'],
      artist_ids: ['a1'],
    });
    expect(parsed.kind).toBe('invalid');
  });

  it('keeps legacy single messages on the single path', () => {
    const parsed = parseQueuePayload(base);
    expect(parsed.kind).toBe('single');
  });
});

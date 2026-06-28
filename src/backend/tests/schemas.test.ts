import { describe, it, expect } from 'vitest';
import { SessionDataSchema } from '../validation/schemas/session';
import { AnalysisQueueMessagePayloadSchema } from '../validation/schemas/queue';
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
});

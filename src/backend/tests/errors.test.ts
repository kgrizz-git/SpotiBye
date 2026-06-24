import { describe, it, expect } from 'vitest';
import {
  resolveErrorStatus,
  parseUpstreamStatus,
  buildExportErrorPayload,
} from '../routes/export/helpers/errors';

describe('errors helper', () => {
  describe('resolveErrorStatus', () => {
    it('returns correct error status codes based on message', () => {
      expect(resolveErrorStatus('EXPORT_FAILED', 'exceeded cpu limit')).toBe(503);
      expect(resolveErrorStatus('EXPORT_FAILED', 'HTTP 401 Unauthorized')).toBe(401);
      expect(resolveErrorStatus('EXPORT_FAILED', 'HTTP 429 Too Many Requests')).toBe(429);
      expect(resolveErrorStatus('DOWNLOAD_FAILED', 'something else')).toBe(503);
      expect(resolveErrorStatus('EXPORT_FAILED', 'something else')).toBe(500);
    });
  });

  describe('parseUpstreamStatus', () => {
    it('extracts standard status codes', () => {
      expect(parseUpstreamStatus('Failed with HTTP 404 Not Found')).toBe(404);
      expect(parseUpstreamStatus('Failed with HTTP 500 Internal Error')).toBe(500);
      expect(parseUpstreamStatus('No code here')).toBeUndefined();
    });
  });

  describe('buildExportErrorPayload', () => {
    it('structures error payloads correctly', () => {
      const payload = buildExportErrorPayload('CODE', 'Failed with HTTP 403 Forbidden', 'req-1', { extra: 'info' });
      expect(payload).toEqual({
        error: {
          code: 'CODE',
          message: 'Failed with HTTP 403 Forbidden',
          request_id: 'req-1',
          details: {
            extra: 'info',
            upstream: 'spotify',
            upstream_status: 403,
            cpu_limited: false,
          },
        },
      });
    });
  });
});

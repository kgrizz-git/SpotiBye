import { describe, it, expect } from 'vitest';
import { formatDuration, sanitizeSheetName, uniquifySheetName, getTrackHeaders } from '../services/export-format-helpers';

describe('formatDuration', () => {
  it('formats 0 ms', () => expect(formatDuration(0)).toBe('0:00'));
  it('formats 59 seconds', () => expect(formatDuration(59000)).toBe('0:59'));
  it('formats exactly 60 seconds', () => expect(formatDuration(60000)).toBe('1:00'));
  it('formats 3599 seconds', () => expect(formatDuration(3599000)).toBe('59:59'));
  it('formats exactly 1 hour', () => expect(formatDuration(3600000)).toBe('1:00:00'));
  it('formats 1 hour with padding', () => expect(formatDuration(3661000)).toBe('1:01:01'));
  it('formats large duration', () => expect(formatDuration(3_600_000)).toBe('1:00:00'));
});

describe('sanitizeSheetName', () => {
  it('strips illegal chars', () => {
    expect(sanitizeSheetName('a\\b/c*d?e:f[g]')).toBe('a b c d e f g');
  });

  it('clamps to 31 chars', () => {
    const long = 'A'.repeat(40);
    expect(sanitizeSheetName(long).length).toBe(31);
  });

  it('returns Playlist for empty input', () => {
    expect(sanitizeSheetName('')).toBe('Playlist');
  });

  it('returns Playlist for whitespace-only input after stripping', () => {
    expect(sanitizeSheetName('   ')).toBe('Playlist');
  });
});

describe('uniquifySheetName', () => {
  it('returns base name on first use', () => {
    const used = new Set<string>();
    expect(uniquifySheetName('MySheet', used)).toBe('MySheet');
    expect(used.has('mysheet')).toBe(true);
  });

  it('appends (2) on first collision', () => {
    const used = new Set(['mysheet']);
    expect(uniquifySheetName('MySheet', used)).toBe('MySheet (2)');
  });

  it('increments suffix on repeated collisions', () => {
    const used = new Set(['mysheet', 'mysheet (2)']);
    expect(uniquifySheetName('MySheet', used)).toBe('MySheet (3)');
  });

  it('is case-insensitive', () => {
    const used = new Set(['mysheet']);
    expect(uniquifySheetName('MYSHEET', used)).toBe('MYSHEET (2)');
  });

  it('shrinks base to fit suffix within 31 chars', () => {
    const base = 'A'.repeat(29); // 29 chars
    const used = new Set([base.toLowerCase()]);
    const result = uniquifySheetName(base, used);
    expect(result.length).toBeLessThanOrEqual(31);
    expect(result).toContain('(2)');
  });
});

describe('getTrackHeaders', () => {
  it('includes all 16 expected headers', () => {
    const headers = getTrackHeaders();
    expect(headers).toContain('Artist');
    expect(headers).toContain('Spotify URL');
    expect(headers).toContain('Time Signature');
    expect(headers).toHaveLength(16);
  });
});

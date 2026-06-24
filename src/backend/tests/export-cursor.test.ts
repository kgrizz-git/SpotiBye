import { describe, it, expect } from 'vitest';
import { encodeCursor, decodeCursor } from '../services/export-cursor';

describe('encodeCursor / decodeCursor', () => {
  it('round-trips collect phase with defaults', () => {
    const cursor = encodeCursor(3);
    const decoded = decodeCursor(cursor);
    expect(decoded).toEqual({ nextPlaylistIndex: 3, nextTrackOffset: 0, nextAssembleIndex: 0, phase: 'collect' });
  });

  it('round-trips assemble phase', () => {
    const cursor = encodeCursor(5, 'assemble', 0, 4);
    const decoded = decodeCursor(cursor);
    expect(decoded).toEqual({ nextPlaylistIndex: 5, nextTrackOffset: 0, nextAssembleIndex: 4, phase: 'assemble' });
  });

  it('round-trips all fields', () => {
    const cursor = encodeCursor(2, 'collect', 50, 1);
    const decoded = decodeCursor(cursor);
    expect(decoded.nextPlaylistIndex).toBe(2);
    expect(decoded.nextTrackOffset).toBe(50);
    expect(decoded.nextAssembleIndex).toBe(1);
    expect(decoded.phase).toBe('collect');
  });

  it('returns fallbacks for undefined cursor', () => {
    const decoded = decodeCursor(undefined, 7, 10, 3);
    expect(decoded).toEqual({ nextPlaylistIndex: 7, nextTrackOffset: 10, nextAssembleIndex: 3, phase: 'collect' });
  });

  it('returns fallbacks for null cursor (falsy)', () => {
    const decoded = decodeCursor(null as any, 1, 2, 3);
    expect(decoded.nextPlaylistIndex).toBe(1);
  });

  it('returns fallbacks for malformed JSON', () => {
    const decoded = decodeCursor('not-json', 5, 6, 7);
    expect(decoded).toEqual({ nextPlaylistIndex: 5, nextTrackOffset: 6, nextAssembleIndex: 7, phase: 'collect' });
  });

  it('uses fallback for negative next_playlist_index', () => {
    const cursor = JSON.stringify({ next_playlist_index: -1, next_track_offset: 0, next_assemble_index: 0, phase: 'collect' });
    const decoded = decodeCursor(cursor, 9);
    expect(decoded.nextPlaylistIndex).toBe(9);
  });

  it('uses fallback for non-numeric next_playlist_index', () => {
    const cursor = JSON.stringify({ next_playlist_index: 'abc', phase: 'collect' });
    const decoded = decodeCursor(cursor, 4);
    expect(decoded.nextPlaylistIndex).toBe(4);
  });

  it('defaults unknown phase to collect', () => {
    const cursor = JSON.stringify({ next_playlist_index: 0, phase: 'unknown' });
    expect(decodeCursor(cursor).phase).toBe('collect');
  });

  it('missing phase field defaults to collect', () => {
    const cursor = JSON.stringify({ next_playlist_index: 0 });
    expect(decodeCursor(cursor).phase).toBe('collect');
  });
});

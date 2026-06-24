import type { ResumableExportJobPhase } from './export-types';

export function encodeCursor(
  nextPlaylistIndex: number,
  phase: ResumableExportJobPhase = 'collect',
  nextTrackOffset = 0,
  nextAssembleIndex = 0,
): string {
  return JSON.stringify({
    next_playlist_index: nextPlaylistIndex,
    next_track_offset: nextTrackOffset,
    next_assemble_index: nextAssembleIndex,
    phase,
  });
}

export function decodeCursor(
  cursor: string | undefined,
  fallbackIndex = 0,
  fallbackTrackOffset = 0,
  fallbackAssembleIndex = 0,
): { nextPlaylistIndex: number; nextTrackOffset: number; nextAssembleIndex: number; phase: ResumableExportJobPhase } {
  if (!cursor) {
    return {
      nextPlaylistIndex: fallbackIndex,
      nextTrackOffset: fallbackTrackOffset,
      nextAssembleIndex: fallbackAssembleIndex,
      phase: 'collect',
    };
  }

  try {
    const parsed = JSON.parse(cursor);
    const nextPlaylistIndex = Number.isInteger(parsed?.next_playlist_index) && parsed.next_playlist_index >= 0
      ? parsed.next_playlist_index
      : fallbackIndex;
    const nextTrackOffset = Number.isInteger(parsed?.next_track_offset) && parsed.next_track_offset >= 0
      ? parsed.next_track_offset
      : fallbackTrackOffset;
    const nextAssembleIndex = Number.isInteger(parsed?.next_assemble_index) && parsed.next_assemble_index >= 0
      ? parsed.next_assemble_index
      : fallbackAssembleIndex;
    const phase = parsed?.phase === 'assemble' ? 'assemble' : 'collect';
    return { nextPlaylistIndex, nextTrackOffset, nextAssembleIndex, phase };
  } catch {
    return {
      nextPlaylistIndex: fallbackIndex,
      nextTrackOffset: fallbackTrackOffset,
      nextAssembleIndex: fallbackAssembleIndex,
      phase: 'collect',
    };
  }
}

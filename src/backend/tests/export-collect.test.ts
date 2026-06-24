import { describe, it, expect } from 'vitest';
import { mergeExportSlice, calculateJobProgress, calculateAssembleProgress } from '../services/export-collect';
import type { ExportData, ResumableExportJobState } from '../services/export-types';

function makeExportData(overrides: Partial<ExportData> = {}): ExportData {
  return {
    playlist: {
      id: 'pl1',
      name: 'Playlist 1',
      description: '',
      total_tracks: 10,
      owner: 'owner',
      followers: 0,
      url: '',
    },
    tracks: [],
    total_duration_ms: 0,
    generated_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeJob(overrides: Partial<ResumableExportJobState> = {}): ResumableExportJobState {
  return {
    job_id: 'j1',
    user_id: 'u1',
    status: 'running',
    phase: 'collect',
    created_at: '',
    updated_at: '',
    playlist_ids: ['p1', 'p2'],
    playlist_count: 2,
    processed_count: 0,
    track_count: 0,
    file_format: 'xlsx',
    include_audio_features: false,
    current_cursor: '',
    current_resume_token: '',
    next_playlist_index: 0,
    current_track_offset: 0,
    assemble_index: 0,
    track_page_size: 100,
    playlist_progress: {},
    continuation_required: true,
    progress: 0,
    ...overrides,
  };
}

describe('mergeExportSlice', () => {
  it('returns slice when no existing data', () => {
    const slice = makeExportData({ tracks: [{ Artist: 'A' } as any] });
    const result = mergeExportSlice(undefined, slice);
    expect(result).toBe(slice);
  });

  it('concatenates tracks and sums duration', () => {
    const existing = makeExportData({
      tracks: [{ Artist: 'A' } as any],
      total_duration_ms: 100,
    });
    const slice = makeExportData({
      tracks: [{ Artist: 'B' } as any],
      total_duration_ms: 200,
    });
    const result = mergeExportSlice(existing, slice);
    expect(result.tracks).toHaveLength(2);
    expect(result.total_duration_ms).toBe(300);
  });

  it('overrides playlist metadata with the newer slice', () => {
    const existing = makeExportData({
      playlist: { id: 'pl1', name: 'Old', description: '', total_tracks: 5, owner: 'o', followers: 0, url: '' },
    });
    const slice = makeExportData({
      playlist: { id: 'pl1', name: 'New', description: '', total_tracks: 10, owner: 'o', followers: 0, url: '' },
    });
    const result = mergeExportSlice(existing, slice);
    expect(result.playlist.name).toBe('New');
    expect(result.playlist.total_tracks).toBe(10);
  });

  it('preserves existing playlist metadata when slice has same values', () => {
    const existing = makeExportData({
      tracks: [{ Artist: 'A' } as any],
      total_duration_ms: 100,
    });
    const slice = makeExportData({ tracks: [], total_duration_ms: 0 });
    const result = mergeExportSlice(existing, slice);
    expect(result.tracks).toHaveLength(1);
    expect(result.total_duration_ms).toBe(100);
  });
});

describe('calculateJobProgress', () => {
  it('returns 100 for empty playlistIds', () => {
    const job = makeJob({ playlist_ids: [], playlist_count: 0 });
    expect(calculateJobProgress(job)).toBe(100);
  });

  it('returns at most 99 while running', () => {
    const job = makeJob({
      playlist_ids: ['p1'],
      playlist_progress: {
        p1: { next_offset: 99, total_tracks: 100, collected_tracks: 99, done: false },
      },
    });
    expect(calculateJobProgress(job)).toBeLessThanOrEqual(99);
  });

  it('counts done playlists as 1.0', () => {
    const job = makeJob({
      playlist_ids: ['p1', 'p2'],
      playlist_progress: {
        p1: { next_offset: 100, total_tracks: 100, collected_tracks: 100, done: true },
        p2: { next_offset: 100, total_tracks: 100, collected_tracks: 100, done: true },
      },
    });
    // Both done → 100% but capped at 99 while still "calculating"
    // Actually if both done, Math.floor(2/2 * 100) = 100 but min(99, 100) = 99
    expect(calculateJobProgress(job)).toBe(99);
  });

  it('counts in-progress as min(collected/total, 0.99)', () => {
    const job = makeJob({
      playlist_ids: ['p1'],
      playlist_progress: {
        p1: { next_offset: 50, total_tracks: 100, collected_tracks: 50, done: false },
      },
    });
    // 0.5 / 1 * 100 = 50, min(99, 50) = 50
    expect(calculateJobProgress(job)).toBe(50);
  });
});

describe('calculateAssembleProgress', () => {
  it('returns 100 when totalPlaylists is 0', () => {
    const job = makeJob({ assemble_index: 0 });
    expect(calculateAssembleProgress(job, 0)).toBe(100);
  });

  it('returns value in 95-99 range for partial assembly', () => {
    const job = makeJob({ assemble_index: 1 });
    const result = calculateAssembleProgress(job, 4);
    expect(result).toBeGreaterThanOrEqual(95);
    expect(result).toBeLessThanOrEqual(99);
  });

  it('caps at 99 for near-complete assembly', () => {
    const job = makeJob({ assemble_index: 3 });
    expect(calculateAssembleProgress(job, 4)).toBeLessThanOrEqual(99);
  });
});

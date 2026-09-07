import { afterEach, describe, expect, it, vi } from 'vitest';
import { runAnalysisPipeline } from './helpers/analysis-job';
import { createSpotifyArtist, createSpotifyTrack, defaultReccoBeatsTrackMetadata } from './helpers/spotify';
import type { AnalysisResult } from '../types/analysis';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('AnalysisJobService end-to-end pipeline', () => {
  it('populates KV with a full AnalysisResult including ReccoBeats enrichment', async () => {
    const { outcome, resultsRaw, statusStore } = await runAnalysisPipeline({
      tracks: [
        createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1' }),
        createSpotifyTrack({ id: 'track2', artistId: 'artist2', artistName: 'Artist 2' }),
      ],
      artists: [
        createSpotifyArtist('artist1', 'Artist 1'),
        createSpotifyArtist('artist2', 'Artist 2'),
      ],
      trackMetadata: defaultReccoBeatsTrackMetadata(),
    });

    expect(outcome).toEqual({ acknowledged: true, reason: 'completed' });

    expect(resultsRaw).not.toBeNull();
    const result = JSON.parse(resultsRaw as string) as AnalysisResult;

    expect(result.schema_version).toBe('1.1');
    expect(result.errors).toEqual([]);
    expect(result.overview?.total_tracks).toBe(2);
    expect(result.audio_features?.track_count).toBe(2);
    expect(result.audio_features?.key_mode_distribution).toEqual({
      key_percentages: { C: 100 },
      dominant_key: 'C',
      dominant_key_percentage: 100,
      mode_percentages: { major: 100, minor: 0 },
      dominant_mode: 'major',
    });
    expect(result.reccobeats_metadata).toMatchObject({
      isrc_available: 1,
      popularity_min: 55,
      popularity_max: 75,
    });

    const status = await statusStore.getStatus('user1', 'playlist1');
    expect(status?.status).toBe('completed');
    expect(status?.progress).toBe(100);
  });
});

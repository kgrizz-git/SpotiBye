import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnalysisJobService } from '../services/analysis-job';
import { AnalysisStatusStore } from '../services/analysis-status-object';
import { SpotifyService } from '../services/spotify';
import { kvNamespace, envWithKv } from './helpers/kv';
import { createReccoBeatsFetchMock, createSpotifyArtist, createSpotifyTrack } from './helpers/spotify';
import type { AnalysisQueueMessage } from '../types/analysis-queue';
import type { AnalysisResult } from '../types/analysis';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('AnalysisJobService end-to-end pipeline', () => {
  it('populates KV with a full AnalysisResult including ReccoBeats enrichment', async () => {
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 2,
      rawCount: 2,
      items: [
        { added_by: null, track: createSpotifyTrack({ id: 'track1', artistId: 'artist1', artistName: 'Artist 1' }) },
        { added_by: null, track: createSpotifyTrack({ id: 'track2', artistId: 'artist2', artistName: 'Artist 2' }) },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([
      createSpotifyArtist('artist1', 'Artist 1'),
      createSpotifyArtist('artist2', 'Artist 2'),
    ]);

    const fetchMock = createReccoBeatsFetchMock({
      trackMetadata: [
        {
          id: 'm1', href: 'https://open.spotify.com/track/track1', trackTitle: 'Track 1',
          artists: [{ id: 'a1', name: 'Artist 1', href: 'https://open.spotify.com/artist/artist1' }],
          durationMs: 200000, isrc: 'ISRC1', popularity: 55,
        },
        {
          id: 'm2', href: 'https://open.spotify.com/track/track2', trackTitle: 'Track 2',
          artists: [{ id: 'a2', name: 'Artist 2', href: 'https://open.spotify.com/artist/artist2' }],
          durationMs: 200000, popularity: 75,
        },
      ],
    });
    vi.stubGlobal('fetch', fetchMock);

    const resultsKey = 'analysis:playlist1:user1:results';
    const cacheKv = kvNamespace();
    const sessionsKv = kvNamespace({
      session1: {
        user_id: 'user1',
        access_token: 'token',
        refresh_token: 'refresh',
        expires_at: Date.now() + 3_600_000,
      },
    });

    const message: AnalysisQueueMessage = {
      job_id: 'job1',
      playlist_id: 'playlist1',
      user_id: 'user1',
      session_id: 'session1',
      enqueued_at: new Date().toISOString(),
      attempt: 0,
    };

    const env = envWithKv(cacheKv, sessionsKv);
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user1', 'playlist1', {
      job_id: 'job1',
      playlist_id: 'playlist1',
      user_id: 'user1',
      status: 'queued',
      progress: 0,
    });
    const service = new AnalysisJobService(env);
    const outcome = await service.process(message);

    expect(outcome).toEqual({ acknowledged: true, reason: 'completed' });

    const resultsRaw = await cacheKv.get(resultsKey);
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

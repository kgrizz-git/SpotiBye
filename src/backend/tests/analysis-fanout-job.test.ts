import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnalysisJobService } from '../services/analysis-job';
import { AnalysisService } from '../services/analysis';
import { SpotifyService } from '../services/spotify';
import { AnalysisStatusStore } from '../services/analysis-status-object';
import { chunkResultKey, fanoutTracksKey } from '../services/analysis-fanout';
import { createSpotifyArtist, createSpotifyTrack } from './helpers/spotify';
import { kvNamespace, envWithKv } from './helpers/kv';
import type {
  AnalysisChunkMessage,
  AnalysisQueueMessage,
  AnalysisStatusRecord,
} from '../types/analysis-queue';
import type { AnalysisResult, PlaylistInsights } from '../types/analysis';

const queuedStatus = (jobId = 'job-1'): AnalysisStatusRecord => ({
  job_id: jobId,
  playlist_id: 'playlist-1',
  user_id: 'user-1',
  status: 'queued',
  progress: 0,
  queued_at: new Date().toISOString(),
});

const sessionsKv = () =>
  kvNamespace({
    'session-1': {
      user_id: 'user-1',
      access_token: 'fresh-token',
      refresh_token: 'refresh-token',
      expires_at: Date.now() + 3_600_000,
    },
  });

const singleMessage = (overrides: Partial<AnalysisQueueMessage> = {}): AnalysisQueueMessage => ({
  job_id: 'job-1',
  playlist_id: 'playlist-1',
  user_id: 'user-1',
  session_id: 'session-1',
  enqueued_at: new Date().toISOString(),
  attempt: 1,
  ...overrides,
});

const chunkMessage = (overrides: Partial<AnalysisChunkMessage> = {}): AnalysisChunkMessage => ({
  ...singleMessage(),
  chunk_id: 'job-1#0',
  chunk_index: 0,
  chunk_count: 2,
  track_ids: ['t1'],
  artist_ids: ['a1'],
  ...overrides,
});

const insightsFixture: PlaylistInsights = {
  overview: { total_tracks: 2, total_duration_ms: 2, average_duration_ms: 1, formatted_duration: '2s' },
  artists: { unique_artists: 1, top_artists: [], diversity: 0 },
  genre_distribution: {},
  insights: [],
};

function mockAnalysis(impls: {
  list?: { tracks: { id: string; artists?: { id: string }[] }[]; artistIds: string[] };
  chunk?: (chunkId: string, trackIds: string[]) => Record<string, unknown>;
} = {}) {
  vi.spyOn(AnalysisService.prototype, 'listPlaylistTracks').mockResolvedValue(
    (impls.list ?? { tracks: [], artistIds: [] }) as never
  );
  vi.spyOn(AnalysisService.prototype, 'analyzeChunk').mockImplementation(
    async (_playlistId: string, chunkId: string, trackIds: string[]) =>
      ({
        chunk_id: chunkId,
        track_ids: trackIds,
        artistData: [],
        audioFeatures: [],
        trackMetadata: [],
        errors: [],
        audioFeaturesResolvedCount: 0,
        trackMetadataResolvedCount: 0,
        enrichmentResolvedTrackCount: 0,
        schema_version: '1.1',
        ...(impls.chunk ? impls.chunk(chunkId, trackIds) : {}),
      }) as never
  );
  vi.spyOn(AnalysisService.prototype, 'generatePlaylistInsights').mockResolvedValue(
    insightsFixture
  );
  vi.spyOn(AnalysisService.prototype, 'analyzePlaylist').mockResolvedValue({
    job_id: 'job-1',
  } as never);
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('fan-out seed', () => {
  it('keeps tiny playlists on the inline path without sending batches', async () => {
    const cacheKv = kvNamespace();
    const sendBatch = vi.fn(async () => undefined);
    const env = envWithKv(cacheKv, sessionsKv());
    (env as { ANALYSIS_QUEUE: unknown }).ANALYSIS_QUEUE = { send: vi.fn(), sendBatch };
    mockAnalysis({
      list: {
        tracks: [
          { id: 't1', artists: [] },
          { id: 't2', artists: [] },
        ] as never,
        artistIds: ['a1'],
      },
    });
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
    const service = new AnalysisJobService(env);

    const outcome = await service.process(singleMessage());

    expect(outcome).toEqual({ acknowledged: true, reason: 'completed' });
    expect(sendBatch).not.toHaveBeenCalled();
  });

  it('fans out large playlists: snapshot, countdown, and covering batches', async () => {
    const cacheKv = kvNamespace();
    let sent: { body: AnalysisChunkMessage }[] = [];
    const sendBatch = vi.fn(async (batch: { body: AnalysisChunkMessage }[]) => {
      sent = batch;
    });
    const env = envWithKv(cacheKv, sessionsKv());
    (env as { ANALYSIS_QUEUE: unknown }).ANALYSIS_QUEUE = { send: vi.fn(), sendBatch };
    const tracks: { id: string; artists: { id: string }[] }[] = Array.from(
      { length: 12 },
      (_, i) => ({ id: `t${i}`, artists: [{ id: `a${i}` }] })
    );
    const artistIds = Array.from({ length: 12 }, (_, i) => `a${i}`);
    mockAnalysis({ list: { tracks, artistIds } });
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
    const service = new AnalysisJobService(env);

    const outcome = await service.process(singleMessage());

    expect(outcome).toEqual({ acknowledged: true, reason: 'fanned-out' });
    expect(sendBatch).toHaveBeenCalledTimes(1);
    const batch = sent;
    expect(batch.length).toBeGreaterThan(1);
    // Every track in exactly one chunk; coordinates consistent.
    const covered = batch.flatMap((m) => m.body.track_ids).sort();
    expect(covered).toEqual(tracks.map((t) => t.id).sort());
    for (const [i, m] of batch.entries()) {
      expect(m.body.chunk_index).toBe(i);
      expect(m.body.chunk_count).toBe(batch.length);
      expect(m.body.chunk_id).toBe(`job-1#${i}`);
    }
    // Countdown initialized; snapshot persisted (read back state, not mocks).
    const countdown = await statusStore.getFanoutCountdown('user-1', 'playlist-1', 'job-1');
    expect(countdown?.expected).toBe(batch.length);
    const snapshotRaw = await cacheKv.get(fanoutTracksKey('playlist-1', 'user-1', 'job-1'));
    expect(snapshotRaw).not.toBeNull();
  });
});

describe('processChunk', () => {
  it('completes the job on the finalizer with merged results', async () => {
    const cacheKv = kvNamespace();
    const env = envWithKv(cacheKv, sessionsKv());
    mockAnalysis();
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
    await statusStore.initFanoutCountdown('user-1', 'playlist-1', 'job-1', 2);
    // Snapshot the job input for finalize-time insights.
    await cacheKv.put(
      fanoutTracksKey('playlist-1', 'user-1', 'job-1'),
      JSON.stringify({
        tracks: [{ id: 't1' }, { id: 't2' }],
        chunkIds: ['job-1#0', 'job-1#1'],
        forceEnrichment: false,
      })
    );
    const service = new AnalysisJobService(env);

    const first = await service.processChunk(chunkMessage());
    expect(first).toEqual({ acknowledged: true, reason: 'completed' });
    // Not terminal yet: results absent, status not completed.
    expect(await statusStore.getStatus('user-1', 'playlist-1')).not.toMatchObject({
      status: 'completed',
    });

    const second = await service.processChunk(
      chunkMessage({ chunk_id: 'job-1#1', chunk_index: 1, track_ids: ['t2'] })
    );
    expect(second).toEqual({ acknowledged: true, reason: 'completed' });

    const status = await statusStore.getStatus('user-1', 'playlist-1');
    expect(status?.status).toBe('completed');
    expect(status?.progress).toBe(100);
    const raw = await cacheKv.get('analysis:playlist-1:user-1:results');
    expect(raw).not.toBeNull();
    const partial0 = await cacheKv.get(chunkResultKey('playlist-1', 'user-1', 'job-1', 'job-1#0'));
    expect(partial0).not.toBeNull();
  });

  it('returns stale for job_id mismatch and terminal status', async () => {
    const cacheKv = kvNamespace();
    const env = envWithKv(cacheKv, sessionsKv());
    mockAnalysis();
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus('other-job'));
    const service = new AnalysisJobService(env);

    expect(await service.processChunk(chunkMessage())).toEqual({
      acknowledged: true,
      reason: 'stale',
    });

    await statusStore.writeStatus('user-1', 'playlist-1', {
      ...queuedStatus('job-1'),
      status: 'completed',
      progress: 100,
    });
    expect(await service.processChunk(chunkMessage())).toEqual({
      acknowledged: true,
      reason: 'stale',
    });
  });

  it('registerChunkFailure writes a marker without terminal status', async () => {
    const cacheKv = kvNamespace();
    const env = envWithKv(cacheKv, sessionsKv());
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
    await statusStore.initFanoutCountdown('user-1', 'playlist-1', 'job-1', 2);
    const service = new AnalysisJobService(env);

    await service.registerChunkFailure(chunkMessage(), new Error('boom'));

    const countdown = await statusStore.getFanoutCountdown('user-1', 'playlist-1', 'job-1');
    expect(countdown?.received).toEqual({ 'job-1#0': 'failed' });
    const status = await statusStore.getStatus('user-1', 'playlist-1');
    expect(status?.status).not.toBe('completed');
    expect(status?.status).not.toBe('failed');
  });

  it('finalize fails loudly naming missing chunks', async () => {
    const cacheKv = kvNamespace();
    const env = envWithKv(cacheKv, sessionsKv());
    mockAnalysis();
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
    await statusStore.initFanoutCountdown('user-1', 'playlist-1', 'job-1', 2);
    await cacheKv.put(
      fanoutTracksKey('playlist-1', 'user-1', 'job-1'),
      JSON.stringify({ tracks: [], chunkIds: ['job-1#0', 'job-1#1'], forceEnrichment: false })
    );
    const service = new AnalysisJobService(env);

    // Only chunk 0 completes; chunk 1's partial never lands.
    await service.processChunk(chunkMessage());
    await service.registerChunkFailure(
      chunkMessage({ chunk_id: 'job-1#1', chunk_index: 1, track_ids: ['t2'] }),
      new Error('worker gone')
    );
    // Drive finalize directly: the countdown is complete (1 ok + 1 failed).
    await (service as unknown as {
      finalizeJob: (m: AnalysisChunkMessage, a: AnalysisService) => Promise<void>;
    }).finalizeJob(
      chunkMessage({ chunk_id: 'job-1#1', chunk_index: 1, track_ids: ['t2'] }),
      new AnalysisService('fresh-token')
    );

    const status = await statusStore.getStatus('user-1', 'playlist-1');
    expect(status?.status).toBe('failed');
    expect(status?.error).toContain('job-1#1');
  });
});

describe('finalizer lease recovery', () => {  it('re-claims finalize after the lease expires without terminal status', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-19T00:00:00Z'));
    try {
      const env = envWithKv(kvNamespace(), sessionsKv());
      const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
      await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
      await statusStore.initFanoutCountdown('user-1', 'playlist-1', 'job-1', 1);

      const first = await statusStore.registerChunkResult(
        'user-1', 'playlist-1', 'job-1', 'job-1#0', true
      );
      expect(first.isFinalizer).toBe(true);
      // Simulate the crash: no terminal write. Redelivery within lease: no claim.
      const again = await statusStore.registerChunkResult(
        'user-1', 'playlist-1', 'job-1', 'job-1#0', true
      );
      expect(again.isFinalizer).toBe(false);
      // Past the 5-minute lease with status still non-terminal: re-claim.
      vi.setSystemTime(new Date('2026-09-19T00:06:01Z'));
      const recovered = await statusStore.registerChunkResult(
        'user-1', 'playlist-1', 'job-1', 'job-1#0', true
      );
      expect(recovered.isFinalizer).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('end-to-end fan-out on a large playlist', () => {
  it('fans out, processes every chunk with real helpers, and merges', async () => {
    const N = 60;
    const tracks = Array.from({ length: N }, (_, i) =>
      createSpotifyTrack({ id: `t${i}`, artistId: `a${i}`, artistName: `Artist ${i}` })
    );
    const artists = Array.from({ length: N }, (_, i) =>
      createSpotifyArtist(`a${i}`, `Artist ${i}`)
    );
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockImplementation(
      async (_playlistId: string, limit?: number, offset?: number) => {
        const items = tracks
          .slice(offset ?? 0, (offset ?? 0) + (limit ?? 100))
          .map((track) => ({ added_by: null, track }));
        return { total: tracks.length, rawCount: items.length, items };
      }
    );
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockImplementation(
      async (ids: string[]) => artists.filter((a) => ids.includes(a.id))
    );
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = new URL(String(input));
        // Repeated ?ids= params (one per track ID), not comma-joined.
        const ids = url.searchParams.getAll('ids').filter(Boolean);
        const isTrack = url.pathname === '/v1/track';
        const content = ids.map((id) =>
          isTrack
            ? {
                id: `m-${id}`,
                href: `https://open.spotify.com/track/${id}`,
                trackTitle: id,
                artists: [],
                durationMs: 200000,
                isrc: `ISRC-${id}`,
                popularity: 50,
              }
            : {
                id: `r-${id}`,
                href: `https://open.spotify.com/track/${id}`,
                acousticness: 0.1,
                danceability: 0.2,
                energy: 0.3,
                instrumentalness: 0.1,
                liveness: 0.1,
                loudness: -5,
                speechiness: 0.1,
                tempo: 100,
                valence: 0.4,
                key: 0,
                mode: 1,
                isrc: `ISRC-${id}`,
              }
        );
        return new Response(JSON.stringify({ content }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      })
    );

    const cacheKv = kvNamespace();
    let sent: { body: AnalysisChunkMessage }[] = [];
    const env = envWithKv(cacheKv, sessionsKv());
    (env as { ANALYSIS_QUEUE: unknown }).ANALYSIS_QUEUE = {
      send: vi.fn(),
      sendBatch: vi.fn(async (batch: { body: AnalysisChunkMessage }[]) => {
        sent = batch;
      }),
    };
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus('job-e2e'));
    const service = new AnalysisJobService(env);

    const seed = await service.process(singleMessage({ job_id: 'job-e2e' }));
    expect(seed).toEqual({ acknowledged: true, reason: 'fanned-out' });
    expect(sent.length).toBeGreaterThan(1);

    for (const m of sent) {
      const outcome = await service.processChunk({ ...m.body, attempt: 1 });
      expect(outcome).toEqual({ acknowledged: true, reason: 'completed' });
    }

    const status = await statusStore.getStatus('user-1', 'playlist-1');
    expect(status?.status).toBe('completed');
    expect(status?.progress).toBe(100);
    const raw = await cacheKv.get('analysis:playlist-1:user-1:results');
    expect(raw).not.toBeNull();
    const result = JSON.parse(raw as string) as AnalysisResult;
    expect(result.unique_track_count).toBe(N);
    expect(result.audio_features?.track_count).toBe(N);
    expect(result.genre_distribution?.pop?.count).toBe(N);
    expect(result.errors).toEqual([]);
  });
});

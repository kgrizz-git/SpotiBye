/**
 * End-to-end harness for `AnalysisJobService.process` tests.
 *
 * `analysis-pipeline.test.ts` and `openapi-schema.test.ts` ran the same
 * ~30-line setup (Spotify spies, ReccoBeats fetch stub, session KV, queue
 * message, status seeding, service invocation) with only the fixture payloads
 * differing. The harness runs that setup verbatim from options and returns
 * the raw artifacts; assertions stay in the calling test.
 */
import { vi } from 'vitest';
import { AnalysisJobService } from '../../services/analysis-job';
import { AnalysisStatusStore } from '../../services/analysis-status-object';
import { SpotifyService } from '../../services/spotify';
import { envWithKv, kvNamespace } from './kv';
import { createReccoBeatsFetchMock } from './spotify';
import type { AnalysisJobOutcome } from '../../services/analysis-job';
import type { AnalysisQueueMessage } from '../../types/analysis-queue';
import type { SpotifyArtistFull, SpotifyTrack } from '../../types/spotify';

export interface AnalysisPipelineRunOptions {
  tracks: SpotifyTrack[];
  artists: SpotifyArtistFull[];
  /** Per-test `/v1/track` metadata content (join keys differ per caller). */
  trackMetadata: unknown[];
  audioFeatures?: unknown[];
  userId?: string;
  playlistId?: string;
  jobId?: string;
  sessionId?: string;
  /** Extra seed entries for CACHE_KV (keys map to stored values). */
  cacheSeed?: Record<string, unknown>;
}

export interface AnalysisPipelineRun {
  outcome: AnalysisJobOutcome;
  resultsKey: string;
  resultsRaw: string | null;
  cacheKv: ReturnType<typeof kvNamespace>;
  statusStore: AnalysisStatusStore;
}

export const runAnalysisPipeline = async (
  options: AnalysisPipelineRunOptions,
): Promise<AnalysisPipelineRun> => {
  const {
    tracks,
    artists,
    trackMetadata,
    audioFeatures,
    userId = 'user1',
    playlistId = 'playlist1',
    jobId = 'job1',
    sessionId = 'session1',
    cacheSeed = {},
  } = options;

  vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
    total: tracks.length,
    rawCount: tracks.length,
    items: tracks.map((track) => ({ added_by: null, track })),
  });
  vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue(artists);
  vi.stubGlobal('fetch', createReccoBeatsFetchMock({ trackMetadata, audioFeatures }));

  const resultsKey = `analysis:${playlistId}:${userId}:results`;
  const cacheKv = kvNamespace(cacheSeed);
  const sessionsKv = kvNamespace({
    [sessionId]: {
      user_id: userId,
      access_token: 'token',
      refresh_token: 'refresh',
      expires_at: Date.now() + 3_600_000,
    },
  });

  const message: AnalysisQueueMessage = {
    job_id: jobId,
    playlist_id: playlistId,
    user_id: userId,
    session_id: sessionId,
    enqueued_at: new Date().toISOString(),
    attempt: 0,
  };

  const env = envWithKv(cacheKv, sessionsKv);
  const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
  await statusStore.writeStatus(userId, playlistId, {
    job_id: jobId,
    playlist_id: playlistId,
    user_id: userId,
    status: 'queued',
    progress: 0,
  });
  const service = new AnalysisJobService(env);
  const outcome = await service.process(message);

  const resultsRaw = await cacheKv.get(resultsKey);
  return { outcome, resultsKey, resultsRaw, cacheKv, statusStore };
};

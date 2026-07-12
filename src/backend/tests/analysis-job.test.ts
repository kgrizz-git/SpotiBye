import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnalysisJobService } from '../services/analysis-job';
import { AnalysisService } from '../services/analysis';
import { AnalysisStatusStore } from '../services/analysis-status-object';
import { kvNamespace, envWithKv } from './helpers/kv';
import type { AnalysisQueueMessage, AnalysisStatusRecord } from '../types/analysis-queue';

const analysisMessage: AnalysisQueueMessage = {
  job_id: 'job-1',
  playlist_id: 'playlist-1',
  user_id: 'user-1',
  session_id: 'session-1',
  enqueued_at: new Date().toISOString(),
  attempt: 1,
};

const analysisResult = {
  job_id: 'job-1',
  playlist_id: 'playlist-1',
  user_id: 'user-1',
  status: 'completed' as const,
  computed_at: '2026-06-19T00:00:00.000Z',
  completed_at: '2026-06-19T00:00:01.000Z',
  unique_track_count: 0,
  audio_features_resolved_count: 0,
  track_metadata_resolved_count: 0,
  enrichment_resolved_track_count: 0,
  errors: [],
  schema_version: '1.1',
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('AnalysisJobService stale-snapshot prevention', () => {
  it('retains values written by intermediate progress calls during subsequent progress calls', async () => {
    const cacheKv = kvNamespace();
    const sessionsKv = kvNamespace({
      'session-1': {
        user_id: 'user-1',
        access_token: 'fresh-token',
        refresh_token: 'refresh-token',
        expires_at: Date.now() + 3_600_000,
      },
    });

    vi.spyOn(AnalysisService.prototype, 'analyzePlaylist').mockImplementation(
      async (playlistId, userId, jobId, onProgress) => {
        if (onProgress) {
          await onProgress(10);
          await onProgress(60);
        }
        throw new Error('Spotify API Error');
      }
    );

    const env = envWithKv(cacheKv, sessionsKv);
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
    const service = new AnalysisJobService(env);
    await expect(service.process(analysisMessage)).rejects.toThrow('Spotify API Error');

    const status = await statusStore.getStatus('user-1', 'playlist-1');

    expect(status?.status).toBe('retrying');
    expect(status?.progress).toBe(60);
    expect(status?.started_at).toBeDefined();
    expect(status?.updated_at).toBeDefined();

    const startMs = new Date(status!.started_at!).getTime();
    const updateMs = new Date(status!.updated_at!).getTime();
    expect(updateMs).toBeGreaterThanOrEqual(startMs);
  });

  it('preserves progress callback data in the completion write', async () => {
    const cacheKv = kvNamespace();
    const sessionsKv = kvNamespace({
      'session-1': {
        user_id: 'user-1',
        access_token: 'fresh-token',
        refresh_token: 'refresh-token',
        expires_at: Date.now() + 3_600_000,
      },
    });

    vi.spyOn(AnalysisService.prototype, 'analyzePlaylist').mockImplementation(
      async (playlistId, userId, jobId, onProgress) => {
        if (onProgress) {
          await onProgress(50);
        }
        return analysisResult;
      }
    );

    const env = envWithKv(cacheKv, sessionsKv);
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
    const service = new AnalysisJobService(env);
    await service.process(analysisMessage);

    const finalStatus = await statusStore.getStatus('user-1', 'playlist-1');

    expect(finalStatus).toBeDefined();
    expect(finalStatus?.status).toBe('completed');
    expect(finalStatus?.started_at).toBeDefined();
    expect(finalStatus?.completed_at).toBeDefined();
  });

  it('preserves progress callback data in the retry/error write', async () => {
    const cacheKv = kvNamespace();
    const sessionsKv = kvNamespace({
      'session-1': {
        user_id: 'user-1',
        access_token: 'fresh-token',
        refresh_token: 'refresh-token',
        expires_at: Date.now() + 3_600_000,
      },
    });

    vi.spyOn(AnalysisService.prototype, 'analyzePlaylist').mockImplementation(
      async (playlistId, userId, jobId, onProgress) => {
        if (onProgress) {
          await onProgress(50);
        }
        throw new Error('Spotify API Error');
      }
    );

    const env = envWithKv(cacheKv, sessionsKv);
    const statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
    await statusStore.writeStatus('user-1', 'playlist-1', queuedStatus());
    const service = new AnalysisJobService(env);
    await expect(service.process(analysisMessage)).rejects.toThrow('Spotify API Error');

    const finalStatus = await statusStore.getStatus('user-1', 'playlist-1');

    expect(finalStatus).toBeDefined();
    expect(finalStatus?.status).toBe('retrying');
    expect(finalStatus?.progress).toBe(50);
    expect(finalStatus?.started_at).toBeDefined();
    expect(finalStatus?.retry_after).toBeDefined();
    expect(finalStatus?.error).toBe('Spotify API Error');
  });
});

function queuedStatus(): AnalysisStatusRecord {
  return {
    job_id: 'job-1',
    playlist_id: 'playlist-1',
    user_id: 'user-1',
    status: 'queued',
    progress: 0,
  };
}

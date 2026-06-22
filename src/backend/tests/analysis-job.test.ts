import { afterEach, describe, expect, it, vi, type Mock } from 'vitest';
import { AnalysisJobService } from '../services/analysis-job';
import { AnalysisService } from '../services/analysis';
import { kvNamespace, envWithKv } from './helpers/kv';
import type { AnalysisQueueMessage, AnalysisStatusRecord } from '../types/analysis-queue';
import type { KVNamespace } from '@cloudflare/workers-types';

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
  tracks: [],
};

const statusPutsFor = (cacheKv: KVNamespace, key: string): AnalysisStatusRecord[] => {
  const put = cacheKv.put as unknown as Mock;
  return put.mock.calls
    .filter((call: unknown[]) => call[0] === key)
    .map((call: unknown[]) => JSON.parse(call[1] as string) as AnalysisStatusRecord);
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('AnalysisJobService stale-snapshot prevention', () => {
  it('retains values written by intermediate progress calls during subsequent progress calls', async () => {
    const statusKey = 'analysis:playlist-1:user-1:status';
    const cacheKv = kvNamespace({
      [statusKey]: {
        job_id: 'job-1',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'queued',
        progress: 0,
      },
    });
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
        return analysisResult;
      }
    );

    const service = new AnalysisJobService(envWithKv(cacheKv, sessionsKv));
    await service.process(analysisMessage);

    const puts = statusPutsFor(cacheKv, statusKey);

    expect(puts.length).toBeGreaterThanOrEqual(4);

    const progress10Write = puts.find((p) => p.progress === 10 && p.status === 'processing');
    const progress60Write = puts.find((p) => p.progress === 60 && p.status === 'processing');

    expect(progress10Write).toBeDefined();
    expect(progress60Write).toBeDefined();
    expect(progress10Write?.started_at).toBeDefined();
    expect(progress60Write?.started_at).toBe(progress10Write?.started_at);
    expect(progress60Write?.updated_at).toBeDefined();
    
    const startMs = new Date(progress60Write!.started_at!).getTime();
    const updateMs = new Date(progress60Write!.updated_at!).getTime();
    expect(updateMs).toBeGreaterThanOrEqual(startMs);
  });

  it('preserves progress callback data in the completion write', async () => {
    const statusKey = 'analysis:playlist-1:user-1:status';
    const cacheKv = kvNamespace({
      [statusKey]: {
        job_id: 'job-1',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'queued',
        progress: 0,
      },
    });
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

    const service = new AnalysisJobService(envWithKv(cacheKv, sessionsKv));
    await service.process(analysisMessage);

    const finalPut = statusPutsFor(cacheKv, statusKey).pop();

    expect(finalPut).toBeDefined();
    expect(finalPut?.status).toBe('completed');
    expect(finalPut?.started_at).toBeDefined();
    expect(finalPut?.completed_at).toBeDefined();
  });

  it('preserves progress callback data in the retry/error write', async () => {
    const statusKey = 'analysis:playlist-1:user-1:status';
    const cacheKv = kvNamespace({
      [statusKey]: {
        job_id: 'job-1',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'queued',
        progress: 0,
      },
    });
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

    const service = new AnalysisJobService(envWithKv(cacheKv, sessionsKv));
    await expect(service.process(analysisMessage)).rejects.toThrow('Spotify API Error');

    const finalPut = statusPutsFor(cacheKv, statusKey).pop();

    expect(finalPut).toBeDefined();
    expect(finalPut?.status).toBe('retrying');
    expect(finalPut?.progress).toBe(50);
    expect(finalPut?.started_at).toBeDefined();
    expect(finalPut?.retry_after).toBeDefined();
    expect(finalPut?.error).toBe('Spotify API Error');
  });
});

import { describe, expect, it } from 'vitest';
import { AnalysisStatusStore, createAnalysisStatusNamespaceStub } from '../services/analysis-status-object';
import type { AnalysisStatusRecord } from '../types/analysis-queue';

describe('AnalysisStatusStore', () => {
  it('returns the latest status immediately after a merge write', async () => {
    const namespace = createAnalysisStatusNamespaceStub();
    const store = new AnalysisStatusStore(namespace);
    const queued: AnalysisStatusRecord = {
      job_id: 'job-1',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      status: 'queued',
      queued_at: '2026-07-12T00:00:00.000Z',
      progress: 0,
    };

    await store.writeStatus('user-1', 'playlist-1', queued);
    await store.mergeStatus('user-1', 'playlist-1', {
      status: 'processing',
      progress: 65,
      updated_at: '2026-07-12T00:00:01.000Z',
    });

    expect(await store.getStatus('user-1', 'playlist-1')).toEqual({
      ...queued,
      status: 'processing',
      progress: 65,
      updated_at: '2026-07-12T00:00:01.000Z',
    });
  });

  it('deletes only the named user playlist status', async () => {
    const namespace = createAnalysisStatusNamespaceStub();
    const store = new AnalysisStatusStore(namespace);
    const status = (playlistId: string): AnalysisStatusRecord => ({
      job_id: `job-${playlistId}`,
      playlist_id: playlistId,
      user_id: 'user-1',
      status: 'queued',
      progress: 0,
    });

    await store.writeStatus('user-1', 'playlist-1', status('playlist-1'));
    await store.writeStatus('user-1', 'playlist-2', status('playlist-2'));

    await store.deleteStatus('user-1', 'playlist-1');

    expect(await store.getStatus('user-1', 'playlist-1')).toBeNull();
    expect(await store.getStatus('user-1', 'playlist-2')).toEqual(status('playlist-2'));
  });
});

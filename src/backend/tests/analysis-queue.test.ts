import { afterEach, describe, expect, it, vi } from 'vitest';
import worker from '../index';
import { AnalysisJobService } from '../services/analysis-job';
import { AnalysisService } from '../services/analysis';
import { kvNamespace, envWithKv } from './helpers/kv';

const analysisResult = {
  job_id: 'job-1',
  playlist_id: 'playlist-1',
  user_id: 'user-1',
  status: 'completed',
  computed_at: '2026-06-19T00:00:00.000Z',
  completed_at: '2026-06-19T00:00:01.000Z',
  overview: {
    total_tracks: 1,
    total_duration_ms: 180000,
    average_duration_ms: 180000,
    formatted_duration: '3m 0s',
  },
  artists: {
    unique_artists: 1,
    top_artists: [{ artist: 'Artist 1', count: 1 }],
    diversity: 1,
  },
  genre_distribution: {},
  insights: [],
};

const analysisMessage = {
  job_id: 'job-1',
  playlist_id: 'playlist-1',
  user_id: 'user-1',
  session_id: 'session-1',
  enqueued_at: '2026-06-19T00:00:00.000Z',
  attempt: 0,
};

const queueMessage = (body: unknown, attempts = 1) => ({
  id: 'message-1',
  timestamp: new Date('2026-06-19T00:00:00.000Z'),
  body,
  attempts,
  ack: vi.fn(),
  retry: vi.fn(),
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('analysis queue env binding', () => {
  it('accepts the ANALYSIS_QUEUE binding used by route and consumer tests', async () => {
    const env = envWithKv();

    await env.ANALYSIS_QUEUE.send(analysisMessage);

    expect(env.ANALYSIS_QUEUE.send).toHaveBeenCalledTimes(1);
  });
});

describe('AnalysisJobService', () => {
  it('persists completed results and completed status for the current job', async () => {
    const statusKey = 'analysis:playlist-1:user-1:status';
    const resultsKey = 'analysis:playlist-1:user-1:results';
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
    vi.spyOn(AnalysisService.prototype, 'analyzePlaylist').mockResolvedValue(analysisResult);

    const service = new AnalysisJobService(envWithKv(cacheKv, sessionsKv));

    const outcome = await service.process(analysisMessage);

    expect(outcome).toEqual({ acknowledged: true, reason: 'completed' });
    expect(cacheKv.put).toHaveBeenCalledWith(resultsKey, JSON.stringify(analysisResult), { expirationTtl: 86400 });
    expect(cacheKv.put).toHaveBeenCalledWith(
      statusKey,
      expect.stringContaining('"status":"completed"'),
      { expirationTtl: 3600 }
    );
  });

  it('acknowledges stale duplicate deliveries without overwriting a newer job', async () => {
    const statusKey = 'analysis:playlist-1:user-1:status';
    const cacheKv = kvNamespace({
      [statusKey]: {
        job_id: 'job-newer',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'queued',
        progress: 0,
      },
    });
    const service = new AnalysisJobService(envWithKv(cacheKv));
    const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist');

    const outcome = await service.process({ ...analysisMessage, job_id: 'job-old' });

    expect(outcome).toEqual({ acknowledged: true, reason: 'stale' });
    expect(analyzeSpy).not.toHaveBeenCalled();
  });

  it('refreshes an expired session token before analyzing', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      access_token: 'refreshed-token',
      expires_in: 3600,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));
    const cacheKv = kvNamespace({
      'analysis:playlist-1:user-1:status': {
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
        access_token: 'expired-token',
        refresh_token: 'refresh-token',
        expires_at: Date.now() - 1000,
      },
    });
    const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist').mockResolvedValue({
      ...analysisResult,
      overview: { total_tracks: 0, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
      artists: { unique_artists: 0, top_artists: [], diversity: 0 },
    });

    const service = new AnalysisJobService(envWithKv(cacheKv, sessionsKv));

    await service.process(analysisMessage);

    expect(analyzeSpy.mock.instances[0]).toBeInstanceOf(AnalysisService);
    expect(fetch).toHaveBeenCalledWith(
      'https://accounts.spotify.com/api/token',
      expect.objectContaining({ method: 'POST' })
    );
    expect(sessionsKv.put).toHaveBeenCalledWith(
      'session-1',
      expect.stringContaining('"access_token":"refreshed-token"'),
      { expirationTtl: 2592000 }
    );
  });

  it('acknowledges duplicate delivery after completion without re-running analysis', async () => {
    const cacheKv = kvNamespace({
      'analysis:playlist-1:user-1:status': {
        job_id: 'job-1',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'completed',
        progress: 100,
        completed_at: '2026-06-19T00:00:01.000Z',
      },
    });
    const service = new AnalysisJobService(envWithKv(cacheKv));
    const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist');

    const outcome = await service.process({ ...analysisMessage, attempt: 1 });

    expect(outcome).toEqual({ acknowledged: true, reason: 'already-completed' });
    expect(analyzeSpy).not.toHaveBeenCalled();
  });
});

describe('analysis queue consumer', () => {
  it('processes each message in the queue batch', async () => {
    const processSpy = vi
      .spyOn(AnalysisJobService.prototype, 'process')
      .mockResolvedValue({ acknowledged: true, reason: 'completed' });
    const batch = {
      queue: 'spotibye-analysis-dev',
      messages: [queueMessage(analysisMessage)],
      retryAll: vi.fn(),
      ackAll: vi.fn(),
    } as unknown as MessageBatch<typeof analysisMessage>;

    await worker.queue(batch, envWithKv(), {} as ExecutionContext);

    expect(processSpy).toHaveBeenCalledWith(expect.objectContaining({
      job_id: 'job-1',
      attempt: 1,
    }));
    expect(batch.messages[0].ack).toHaveBeenCalledTimes(1);
  });

  it('marks the job failed instead of retrying after the final queue attempt', async () => {
    vi.spyOn(AnalysisJobService.prototype, 'process').mockRejectedValue(new Error('Spotify timeout'));
    const markFailedSpy = vi.spyOn(AnalysisJobService.prototype, 'markFailed').mockResolvedValue(undefined);
    const message = queueMessage(analysisMessage, 3);
    const batch = {
      queue: 'spotibye-analysis-dev',
      messages: [message],
      retryAll: vi.fn(),
      ackAll: vi.fn(),
    } as unknown as MessageBatch<typeof analysisMessage>;

    await worker.queue(batch, envWithKv(), {} as ExecutionContext);

    expect(markFailedSpy).toHaveBeenCalledWith(expect.objectContaining({
      job_id: 'job-1',
      attempt: 3,
    }), expect.any(Error));
    expect(message.ack).toHaveBeenCalledTimes(1);
    expect(message.retry).not.toHaveBeenCalled();
  });

  it('still acks the message when markFailed throws (BE-LOG-5)', async () => {
    // BE-LOG-5 / BE-ERR-4: a KV write failure inside markFailed must not
    // prevent the message from being acked, otherwise it would loop past
    // max_retries indefinitely.
    vi.spyOn(AnalysisJobService.prototype, 'process').mockRejectedValue(new Error('process failed'));
    vi.spyOn(AnalysisJobService.prototype, 'markFailed').mockRejectedValue(new Error('KV write failed'));
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    const message = queueMessage(analysisMessage, 3);
    const batch = {
      queue: 'spotibye-analysis-dev',
      messages: [message],
      retryAll: vi.fn(),
      ackAll: vi.fn(),
    } as unknown as MessageBatch<typeof analysisMessage>;

    await worker.queue(batch, envWithKv(), {} as ExecutionContext);

    expect(message.ack).toHaveBeenCalledTimes(1);
    expect(message.retry).not.toHaveBeenCalled();
    expect(errorSpy).toHaveBeenCalledWith(
      expect.stringContaining('markFailed threw'),
      expect.any(Error)
    );
  });
});

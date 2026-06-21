import { AnalysisService, type AnalysisResult } from './analysis';
import { CacheService } from './cache';
import { SpotifyAuthService } from './spotify-auth';
import { SPOTIFY_SESSION_TTL_SECONDS } from '../types/auth';
import type { AnalysisQueueMessage, AnalysisStatusRecord } from '../types/analysis-queue';
import type { Env } from '../types/env';

interface SessionRecord {
  user_id: string;
  access_token: string;
  refresh_token?: string;
  expires_at: number;
}

interface RefreshedToken {
  access_token: string;
  expires_in: number;
  refresh_token?: string;
}

export interface AnalysisJobOutcome {
  acknowledged: boolean;
  reason: 'completed' | 'stale' | 'already-completed';
}

export class AnalysisJobService {
  private cache: CacheService;

  constructor(private env: Env) {
    this.cache = new CacheService(env.CACHE_KV);
  }

  async process(message: AnalysisQueueMessage): Promise<AnalysisJobOutcome> {
    const statusKey = this.statusKey(message);
    const resultsKey = this.resultsKey(message);
    const current = await this.cache.get<AnalysisStatusRecord>(statusKey);

    if (!current) {
      // KV is eventually consistent. The status write from the route might not have propagated to this edge node yet.
      const ageMs = Date.now() - new Date(message.enqueued_at).getTime();
      if (ageMs < 15000) {
        throw new Error(`Status record not found for job ${message.job_id} - waiting for KV replication (age: ${ageMs}ms)`);
      }
      return { acknowledged: true, reason: 'stale' };
    }

    if (current.job_id !== message.job_id) {
      return { acknowledged: true, reason: 'stale' };
    }

    if (current.status === 'completed') {
      return { acknowledged: true, reason: 'already-completed' };
    }

    await this.writeStatus(statusKey, {
      ...current,
      status: 'processing',
      progress: 10,
      started_at: new Date().toISOString(),
      attempt: message.attempt,
    });

    try {
      const accessToken = await this.getAccessToken(message.session_id);
      const analysis = new AnalysisService(accessToken);
      const result = await analysis.analyzePlaylist(
        message.playlist_id,
        message.user_id,
        message.job_id,
        async (progressPercentage) => {
          await this.writeStatus(statusKey, {
            ...current,
            status: 'processing',
            progress: progressPercentage,
            attempt: message.attempt,
          });
        }
      );

      await this.cache.set(resultsKey, result satisfies AnalysisResult, 86400);
      await this.writeStatus(statusKey, {
        ...current,
        status: 'completed',
        progress: 100,
        completed_at: new Date().toISOString(),
        attempt: message.attempt,
      });

      return { acknowledged: true, reason: 'completed' };
    } catch (error) {
      await this.writeStatus(statusKey, {
        ...current,
        status: 'retrying',
        progress: current.progress,
        retry_after: new Date(Date.now() + 60_000).toISOString(),
        attempt: message.attempt + 1,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  async markFailed(message: AnalysisQueueMessage, error: unknown): Promise<void> {
    const statusKey = this.statusKey(message);
    const current = await this.cache.get<AnalysisStatusRecord>(statusKey);
    if (!current || current.job_id !== message.job_id || current.status === 'completed') {
      return;
    }

    await this.writeStatus(statusKey, {
      ...current,
      status: 'failed',
      progress: current.progress,
      failed_at: new Date().toISOString(),
      attempt: message.attempt,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  private async getAccessToken(sessionId: string): Promise<string> {
    const raw = await this.env.SESSIONS_KV.get(sessionId);
    if (!raw) {
      throw new Error('Analysis session not found');
    }

    let session = JSON.parse(raw) as SessionRecord;
    if (Date.now() <= session.expires_at) {
      return session.access_token;
    }

    if (!session.refresh_token) {
      throw new Error('Analysis session has no refresh token');
    }

    const spotifyAuth = new SpotifyAuthService(
      this.env.SPOTIFY_CLIENT_ID,
      this.env.SPOTIFY_CLIENT_SECRET
    );
    const refreshed = await spotifyAuth.refreshAccessToken(session.refresh_token) as RefreshedToken;
    session = {
      ...session,
      access_token: refreshed.access_token,
      refresh_token: refreshed.refresh_token || session.refresh_token,
      expires_at: Date.now() + refreshed.expires_in * 1000,
    };

    await this.env.SESSIONS_KV.put(sessionId, JSON.stringify(session), {
      expirationTtl: SPOTIFY_SESSION_TTL_SECONDS,
    });

    return session.access_token;
  }

  private async writeStatus(key: string, status: AnalysisStatusRecord): Promise<void> {
    await this.cache.set(key, status, 3600);
  }

  private statusKey(message: AnalysisQueueMessage): string {
    return `analysis:${message.playlist_id}:${message.user_id}:status`;
  }

  private resultsKey(message: AnalysisQueueMessage): string {
    return `analysis:${message.playlist_id}:${message.user_id}:results`;
  }
}

import { AnalysisService } from './analysis';
import { AnalysisStatusStore } from './analysis-status-object';
import { CacheService } from './cache';
import { SpotifyAuthService } from './spotify-auth';
import { SPOTIFY_SESSION_TTL_SECONDS } from '../types/auth';
import { ANALYSIS_RESULTS_TTL_SECONDS } from '../utils/constants';
import type { AnalysisQueueMessage, AnalysisStatusRecord } from '../types/analysis-queue';
import type { AnalysisResult } from '../types/analysis';
import type { Env } from '../types/env';
import { AuthRequiredException, NonRetryableError } from '../types/errors';

interface SessionRecord {
  user_id: string;
  access_token: string;
  refresh_token?: string;
  expires_at: number;
}

export interface AnalysisJobOutcome {
  acknowledged: boolean;
  reason: 'completed' | 'stale' | 'already-completed';
}

export class AnalysisJobService {
  private cache: CacheService;
  private statusStore: AnalysisStatusStore;

  constructor(private env: Env) {
    this.cache = new CacheService(env.CACHE_KV);
    this.statusStore = new AnalysisStatusStore(env.ANALYSIS_STATUS);
  }

  async process(message: AnalysisQueueMessage): Promise<AnalysisJobOutcome> {
    const resultsKey = this.resultsKey(message);
    const current = await this.statusStore.getStatus(message.user_id, message.playlist_id);

    if (!current) {
      return { acknowledged: true, reason: 'stale' };
    }

    if (current.job_id !== message.job_id) {
      return { acknowledged: true, reason: 'stale' };
    }

    if (current.status === 'completed') {
      return { acknowledged: true, reason: 'already-completed' };
    }

    await this.writeStatus(message, {
      ...current,
      status: 'processing',
      progress: 10,
      started_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      attempt: message.attempt,
    });

    try {
      const accessToken = await this.getAccessToken(message.session_id);
      const analysis = new AnalysisService(accessToken, this.cache);
      const result = await analysis.analyzePlaylist(
        message.playlist_id,
        message.user_id,
        message.job_id,
        async (progressPercentage) => {
          await this.writeStatusMerged(message, {
            status: 'processing',
            progress: progressPercentage,
            attempt: message.attempt,
          });
        },
        { forceEnrichment: message.force_enrichment === true },
      );

      await this.cache.set(resultsKey, result satisfies AnalysisResult, this.resultsTtlSeconds());
      await this.writeStatusMerged(message, {
        status: 'completed',
        progress: 100,
        completed_at: new Date().toISOString(),
        attempt: message.attempt,
      });

      // Invalidate single-export cache after successful force enrichment so
      // the next export reflects refreshed ReccoBeats data. In-flight job/batch
      // export keys are not cleared (see export DELETE route comments).
      if (message.force_enrichment) {
        // Matches `buildSingleExportPrefix` in routes/export/helpers/cache-keys.ts
        await this.cache.clearPrefixPaginated(
          `export:${message.playlist_id}:${message.user_id}`,
        );
      }

      return { acknowledged: true, reason: 'completed' };
    } catch (error) {
      if (error instanceof AuthRequiredException) {
        await this.env.SESSIONS_KV.delete(message.session_id);
        await this.writeStatus(message, {
          ...current,
          status: 'failed',
          progress: current.progress,
          failed_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          attempt: message.attempt,
          error: 'Spotify session expired or revoked. Please sign in again.',
        });
        throw new NonRetryableError('Spotify session expired or revoked. Please sign in again.');
      }
      await this.writeStatusMerged(message, {
        status: 'retrying',
        retry_after: new Date(Date.now() + 60_000).toISOString(),
        attempt: message.attempt + 1,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  async markFailed(message: AnalysisQueueMessage, error: unknown): Promise<void> {
    const current = await this.statusStore.getStatus(message.user_id, message.playlist_id);
    if (!current || current.job_id !== message.job_id || current.status === 'completed') {
      return;
    }

    await this.writeStatus(message, {
      ...current,
      status: 'failed',
      progress: current.progress,
      failed_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      attempt: message.attempt,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  private async getAccessToken(sessionId: string): Promise<string> {
    const raw = await this.env.SESSIONS_KV.get(sessionId);
    if (!raw) {
      throw new AuthRequiredException('Analysis session expired');
    }

    let session = JSON.parse(raw) as SessionRecord;
    if (Date.now() <= session.expires_at) {
      return session.access_token;
    }

    if (!session.refresh_token) {
      throw new AuthRequiredException('Analysis session expired');
    }

    const spotifyAuth = new SpotifyAuthService(
      this.env.SPOTIFY_CLIENT_ID,
      this.env.SPOTIFY_CLIENT_SECRET
    );
    const refreshed = await spotifyAuth.refreshAccessToken(session.refresh_token);
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

  private async writeStatus(message: AnalysisQueueMessage, status: AnalysisStatusRecord): Promise<void> {
    await this.statusStore.writeStatus(message.user_id, message.playlist_id, status);
  }

  private async writeStatusMerged(
    message: AnalysisQueueMessage,
    partial: Partial<AnalysisStatusRecord>,
  ): Promise<void> {
    const latest = await this.statusStore.getStatus(message.user_id, message.playlist_id);
    if (!latest) return; // Defensive, status record should always exist
    await this.writeStatus(message, {
      ...latest,
      ...partial,
      updated_at: new Date().toISOString()
    });
  }

  private resultsKey(message: AnalysisQueueMessage): string {
    return `analysis:${message.playlist_id}:${message.user_id}:results`;
  }

  private resultsTtlSeconds(): number {
    const override = this.env.ANALYSIS_RESULTS_TTL_SECONDS;
    const parsed = override ? Number(override) : NaN;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : ANALYSIS_RESULTS_TTL_SECONDS;
  }
}

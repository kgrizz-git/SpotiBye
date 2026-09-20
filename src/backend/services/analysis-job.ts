import { AnalysisService } from './analysis';
import {
  chunkResultKey,
  chunkTrackIds,
  fanoutTracksKey,
  mergePartials,
  resolveMergedSchemaVersion,
  shouldFanOut,
  type AnalysisChunkPartial,
  type FanoutTracksSnapshot,
  type TrackArtistIndex,
} from './analysis-fanout';
import { AnalysisStatusStore } from './analysis-status-object';
import { CacheService } from './cache';
import { ReccoBeatsTrackCacheService } from './reccobeats-track-cache';
import { SpotifyAuthService } from './spotify-auth';
import { SPOTIFY_SESSION_TTL_SECONDS } from '../types/auth';
import { ANALYSIS_RESULTS_TTL_SECONDS, FANOUT_STATE_TTL_SECONDS } from '../utils/constants';
import type { AnalysisChunkMessage, AnalysisQueueMessage, AnalysisStatusRecord } from '../types/analysis-queue';
import type { AnalysisResult } from '../types/analysis';
import type { Env } from '../types/env';
import type { SpotifyTrack } from '../types/spotify';
import { AuthRequiredException, NonRetryableError } from '../types/errors';

interface SessionRecord {
  user_id: string;
  access_token: string;
  refresh_token?: string;
  expires_at: number;
}

export interface AnalysisJobOutcome {
  acknowledged: boolean;
  reason: 'completed' | 'stale' | 'already-completed' | 'fanned-out';
}

/** Bounded wait between missing-partial reads during finalize. */
function delayMs(ms: number): Promise<void> {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
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
      if (!('chunk_id' in message)) {
        try {
          const { tracks, artistIds } = await analysis.listPlaylistTracks(message.playlist_id);
          if (shouldFanOut(tracks.length, artistIds.length)) {
            return this.fanoutSeed(message, tracks);
          }
        } catch {
          // Enumeration failed: fall through to the inline path, which
          // surfaces the error with the established semantics (and keeps
          // existing single-path tests byte-identical).
        }
      }
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

  /**
   * Fan-out seed: split a large playlist into per-chunk queue messages.
   * Runs inside the seed message's delivery (worker-side fan-out, so the
   * session/token context already exists and POST stays thin).
   */
  private async fanoutSeed(
    message: AnalysisQueueMessage,
    tracks: SpotifyTrack[]
  ): Promise<AnalysisJobOutcome> {
    const force = message.force_enrichment === true;
    if (force) {
      // Single pre-enqueue clear for the whole job; chunks never re-delete.
      const trackCache = new ReccoBeatsTrackCacheService(this.cache);
      await trackCache.clearTrackKeys(tracks.map((track) => track.id));
    }
    const artistByTrack = new Map<string, string[]>();
    for (const track of tracks) {
      artistByTrack.set(
        track.id,
        (track.artists ?? []).map((artist) => artist.id)
      );
    }
    const index: TrackArtistIndex[] = tracks.map((track) => ({
      trackId: track.id,
      artistIds: artistByTrack.get(track.id) ?? [],
    }));
    const groups = chunkTrackIds(index);
    const chunkIds = groups.map((_, i) => `${message.job_id}#${i}`);
    const now = new Date().toISOString();
    const snapshot: FanoutTracksSnapshot = { tracks, chunkIds, forceEnrichment: force };
    await this.cache.set(
      fanoutTracksKey(message.playlist_id, message.user_id, message.job_id),
      snapshot,
      FANOUT_STATE_TTL_SECONDS
    );
    await this.statusStore.initFanoutCountdown(
      message.user_id,
      message.playlist_id,
      message.job_id,
      groups.length
    );
    const batch: AnalysisChunkMessage[] = groups.map((trackIds, i) => {
      const artistIds = [
        ...new Set(trackIds.flatMap((id) => artistByTrack.get(id) ?? [])),
      ];
      return {
        job_id: message.job_id,
        playlist_id: message.playlist_id,
        user_id: message.user_id,
        session_id: message.session_id,
        enqueued_at: now,
        attempt: 0,
        chunk_id: chunkIds[i],
        chunk_index: i,
        chunk_count: groups.length,
        track_ids: trackIds,
        artist_ids: artistIds,
        ...(force ? { force_resolve: true } : {}),
      };
    });
    try {
      await this.env.ANALYSIS_QUEUE.sendBatch(batch.map((chunk) => ({ body: chunk })));
    } catch (error) {
      // Compensating path: terminal user-visible failed write (valid status,
      // no type change) plus countdown reset so nothing hangs.
      await this.statusStore.cancelFanoutCountdown(
        message.user_id,
        message.playlist_id,
        message.job_id
      );
      const current = await this.statusStore.getStatus(message.user_id, message.playlist_id);
      if (current && current.job_id === message.job_id) {
        await this.writeStatus(message, {
          ...current,
          status: 'failed',
          progress: current.progress,
          failed_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          attempt: message.attempt,
          error: 'Fan-out enqueue aborted before chunks were sent.',
        });
      }
      throw error;
    }
    await this.writeStatusMerged(message, {
      status: 'processing',
      progress: 20,
      attempt: message.attempt,
    });
    return { acknowledged: true, reason: 'fanned-out' };
  }

  /**
   * Process one fan-out chunk: stale/terminal short-circuit, chunk analysis,
   * partial write, exactly-once countdown registration. Never writes
   * terminal user status (finalize owns it).
   */
  async processChunk(message: AnalysisChunkMessage): Promise<AnalysisJobOutcome> {
    const current = await this.statusStore.getStatus(message.user_id, message.playlist_id);
    if (!current || current.job_id !== message.job_id) {
      return { acknowledged: true, reason: 'stale' };
    }
    if (current.status === 'completed' || current.status === 'failed') {
      return { acknowledged: true, reason: 'stale' };
    }
    const accessToken = await this.getAccessToken(message.session_id);
    const analysis = new AnalysisService(accessToken, this.cache);
    // Map the chunk-local 65→85 enrichment band onto this chunk's share so
    // shared DO progress stays roughly monotonic across chunks.
    const bandStart = 65 + Math.round((message.chunk_index * 20) / message.chunk_count);
    const bandEnd = 65 + Math.round(((message.chunk_index + 1) * 20) / message.chunk_count);
    try {
      const partial = await analysis.analyzeChunk(
        message.playlist_id,
        message.chunk_id,
        message.track_ids,
        message.artist_ids,
        {
          forceResolve: message.force_resolve === true,
          onProgress: async (progress: number) => {
            const clamped = Math.min(85, Math.max(65, progress));
            const mapped =
              bandStart + Math.round(((clamped - 65) / 20) * (bandEnd - bandStart));
            await this.writeStatusMerged(message, {
              status: 'processing',
              progress: mapped,
              attempt: message.attempt,
            });
          },
        }
      );
      await this.cache.set(
        chunkResultKey(message.playlist_id, message.user_id, message.job_id, message.chunk_id),
        partial,
        FANOUT_STATE_TTL_SECONDS
      );
      const registration = await this.statusStore.registerChunkResult(
        message.user_id,
        message.playlist_id,
        message.job_id,
        message.chunk_id,
        true
      );
      if (registration.isFinalizer) {
        await this.finalizeJob(message, analysis);
      }
      return { acknowledged: true, reason: 'completed' };
    } catch (error) {
      if (error instanceof AuthRequiredException) {
        await this.env.SESSIONS_KV.delete(message.session_id);
        throw new NonRetryableError('Spotify session expired or revoked. Please sign in again.');
      }
      throw error;
    }
  }

  /**
   * Register a chunk failure marker (non-terminal) so the DO countdown
   * completes even when the message DLQs. Terminal status stays owned by
   * finalizeJob. Safe to call repeatedly: first registration wins.
   */
  async registerChunkFailure(message: AnalysisChunkMessage, error: unknown): Promise<void> {
    const detail = error instanceof Error ? error.message : String(error);
    await this.statusStore.registerChunkResult(
      message.user_id,
      message.playlist_id,
      message.job_id,
      message.chunk_id,
      false
    );
    await this.statusStore.mergeStatus(message.user_id, message.playlist_id, {
      error: `Chunk ${message.chunk_id} failed: ${detail}`,
      updated_at: new Date().toISOString(),
    });
  }

  /**
   * Merge all chunk partials into the final result. Runs inline exactly once
   * per job: only the worker whose atomic registerChunkResult returns
   * isFinalizer, plus stuck-finalize lease recovery. Owns ALL terminal
   * writes for fan-out jobs.
   */
  private async finalizeJob(message: AnalysisChunkMessage, analysis: AnalysisService): Promise<void> {
    const snapshot = (await this.cache.get(
      fanoutTracksKey(message.playlist_id, message.user_id, message.job_id)
    )) as FanoutTracksSnapshot | null;
    if (!snapshot || !Array.isArray(snapshot.tracks) || !Array.isArray(snapshot.chunkIds)) {
      await this.markFailed(message, new Error(`Fan-out snapshot missing for job ${message.job_id}`));
      return;
    }
    const partials: AnalysisChunkPartial[] = [];
    const missing: string[] = [];
    for (const chunkId of snapshot.chunkIds) {
      let raw: unknown = null;
      // Bounded retries for KV read-after-write propagation (usually
      // millisecond-scale; total worst case ~2.25s per missing chunk).
      for (let attempt = 0; attempt < 3; attempt++) {
        raw = await this.cache.get(
          chunkResultKey(message.playlist_id, message.user_id, message.job_id, chunkId)
        );
        if (raw) break;
        await delayMs(750);
      }
      if (!raw) {
        missing.push(chunkId);
        continue;
      }
      partials.push(raw as AnalysisChunkPartial);
    }
    const countdown = await this.statusStore.getFanoutCountdown(
      message.user_id,
      message.playlist_id,
      message.job_id
    );
    const failed = Object.entries(countdown?.received ?? {})
      .filter(([, outcome]) => outcome === 'failed')
      .map(([chunkId]) => chunkId);
    if (missing.length > 0 || failed.length > 0) {
      await this.markFailed(
        message,
        new Error(
          `Fan-out incomplete — missing: ${missing.join(', ') || 'none'}; failed: ${failed.join(', ') || 'none'}`
        )
      );
      return;
    }
    let schemaVersion: string;
    try {
      const mergedForVersion = mergePartials(partials);
      schemaVersion = resolveMergedSchemaVersion(mergedForVersion.schemaVersions);
    } catch (error) {
      await this.markFailed(message, error);
      return;
    }
    const merged = mergePartials(partials);
    const insights = await analysis.generatePlaylistInsights(
      snapshot.tracks,
      merged.artistData,
      merged.audioFeatures,
      merged.trackMetadata
    );
    const now = new Date().toISOString();
    const result: AnalysisResult = {
      job_id: message.job_id,
      playlist_id: message.playlist_id,
      user_id: message.user_id,
      status: 'completed',
      computed_at: now,
      ...insights,
      unique_track_count: snapshot.tracks.length,
      audio_features_resolved_count: merged.audioFeaturesResolvedCount,
      track_metadata_resolved_count: merged.trackMetadataResolvedCount,
      enrichment_resolved_track_count: merged.enrichmentResolvedTrackCount,
      completed_at: now,
      errors: merged.errors,
      schema_version: schemaVersion,
    };
    await this.cache.set(this.resultsKey(message), result satisfies AnalysisResult, this.resultsTtlSeconds());
    await this.writeStatusMerged(message, {
      status: 'completed',
      progress: 100,
      completed_at: now,
      attempt: message.attempt,
    });
    // Post-success export invalidation mirrors the single path (moved here
    // from process() so fan-out jobs refresh exports after force runs).
    if (snapshot.forceEnrichment) {
      await this.cache.clearPrefixPaginated(
        `export:${message.playlist_id}:${message.user_id}`,
      );
    }
    // Best-effort countdown cleanup; the 24h DO alarm covers orphans.
    await this.statusStore.cancelFanoutCountdown(
      message.user_id,
      message.playlist_id,
      message.job_id
    );
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

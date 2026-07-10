import { SpotifyService } from './spotify';
import { CacheService } from './cache';
import { createFetchWithRetry } from '../utils/http-retry';
import { logger } from '../utils/logger';
import { ANALYSIS_SCHEMA_VERSION, MUSIC_KEYS, RECCOBEATS_JITTER_DELAY_MS } from '../utils/constants';
import type { SpotifyArtistFull, SpotifyTrack, SpotifyPlaylistTrackItem } from '../types/spotify';
import type {
  AnalysisResult,
  AudioFeatureAverages,
  AudioFeatureSummary,
  CachedRawEnrichment,
  KeyModeDistribution,
  PlaylistInsights,
  ReccoBeatsAudioFeature,
  ReccoBeatsAudioFeaturesResponse,
  ReccoBeatsTrackMetadata,
  ReccoBeatsTrackMetadataResponse,
} from '../types/analysis';

// Raw ReccoBeats enrichment (audio features + track metadata) is cached for
// 24h, keyed by playlist only (see `rawEnrichmentCacheKey`).
const RAW_ENRICHMENT_CACHE_TTL_SECONDS = 86400;

const BATCH_SIZE = 30;
const CONCURRENCY = 3;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function chunk<T>(items: T[], size: number): T[][] {
  const result: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    result.push(items.slice(i, i + size));
  }
  return result;
}

function truncateResponseBody(body: string, maxLength = 500): string {
  return body.length > maxLength ? `${body.slice(0, maxLength)}...` : body;
}

export class AnalysisService {
  private accessToken: string;
  private reccoBeatsUrl = 'https://api.reccobeats.com/v1';
  private fetchWithRetry = createFetchWithRetry();
  private emittedWarmKeepalive = false;
  private cache?: CacheService;

  constructor(accessToken: string, cache?: CacheService) {
    this.accessToken = accessToken;
    this.cache = cache;
  }

  async analyzePlaylist(
    playlistId: string,
    userId: string,
    jobId: string,
    onProgress?: (progress: number) => Promise<void>
  ): Promise<AnalysisResult> {
    const errors: Array<{ source: string; message: string }> = [];
    try {
      const spotifyService = new SpotifyService(this.accessToken);

      logger.info('Fetching playlist tracks', { playlistId });
      await onProgress?.(20);

      // Get all playlist tracks, paginating by raw page size to correctly
      // advance offsets past local/unavailable items.
      const allItems: typeof tracksData.items = [];
      let offset = 0;
      const limit = 100;
      let tracksData: Awaited<ReturnType<typeof spotifyService.getPlaylistTracks>>;
      do {
        tracksData = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
        allItems.push(...tracksData.items);
        offset += limit;
      } while (tracksData.rawCount === limit && offset < tracksData.total);

      // Normalize items: handle both .track (old) and .item (Feb-2026 shape)
      const tracks = allItems
        .map((item: SpotifyPlaylistTrackItem) => item.track ?? item.item)
        .filter((t): t is SpotifyTrack => t?.id !== undefined);

      // Collect unique artist IDs and fetch full artist objects (for genre data)
      const artistIdSet = new Set<string>();
      for (const track of tracks) {
        for (const artist of (track.artists ?? [])) {
          if (artist.id) artistIdSet.add(artist.id);
        }
      }
      let artistData: SpotifyArtistFull[] = [];
      try {
        logger.info('Fetching Spotify artist metadata', { playlistId, artistCount: artistIdSet.size });
        await onProgress?.(50);
        artistData = await spotifyService.getArtists([...artistIdSet]);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        logger.warn('Failed to fetch Spotify artist metadata; continuing without genre insights', {
          playlistId,
          artistCount: artistIdSet.size,
          error: message,
        });
        errors.push({ source: 'spotify:artists', message });
      }

      await onProgress?.(65);

      // NOTE: Spotify /audio-features was removed in the Feb 2026 API migration.
      // ReccoBeats audio features + track metadata are best-effort enrichment;
      // core insights use Spotify track metadata and artist genres.
      const trackIds = tracks.map((track) => track.id);
      const { audioFeatures, trackMetadata } = await this.fetchReccoBeatsEnrichment(
        playlistId,
        trackIds,
        errors,
        onProgress
      );

      logger.info('Generating insights from metadata', { playlistId });
      await onProgress?.(95);
      const spotifyInsights = await this.generatePlaylistInsights(
        tracks,
        artistData,
        audioFeatures,
        trackMetadata
      );

      return {
        job_id: jobId,
        playlist_id: playlistId,
        user_id: userId,
        status: 'completed',
        computed_at: new Date().toISOString(),
        ...spotifyInsights,
        completed_at: new Date().toISOString(),
        errors,
        schema_version: ANALYSIS_SCHEMA_VERSION,
      };
    } catch (error) {
      logger.error('Analysis error', {
        playlistId,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  /**
   * Fetches ReccoBeats audio features + track metadata in parallel
   * (best-effort — failures are recorded in `errors` rather than thrown),
   * using a shared 24h raw-enrichment cache keyed by playlist only.
   */
  private async fetchReccoBeatsEnrichment(
    playlistId: string,
    trackIds: string[],
    errors: Array<{ source: string; message: string }>,
    onProgress?: (progress: number) => Promise<void>
  ): Promise<{ audioFeatures: ReccoBeatsAudioFeature[]; trackMetadata: ReccoBeatsTrackMetadata[] }> {
    if (trackIds.length === 0) {
      await onProgress?.(85);
      return { audioFeatures: [], trackMetadata: [] };
    }

    const rawKey = this.rawEnrichmentCacheKey(playlistId);
    const cached = this.cache ? await this.cache.get<CachedRawEnrichment>(rawKey) : null;
    const cacheValid =
      !!cached &&
      cached.schema_version === ANALYSIS_SCHEMA_VERSION &&
      cached.track_count === trackIds.length;

    let audioFeatures: ReccoBeatsAudioFeature[] =
      cacheValid && cached!.audio_features.length > 0 ? cached!.audio_features : [];
    let trackMetadata: ReccoBeatsTrackMetadata[] =
      cacheValid && cached!.track_metadata.length > 0 ? cached!.track_metadata : [];

    const needsAudioFeatures = audioFeatures.length === 0;
    const needsTrackMetadata = trackMetadata.length === 0;

    if (needsAudioFeatures || needsTrackMetadata) {
      logger.info('Fetching ReccoBeats enrichment', {
        playlistId,
        trackCount: trackIds.length,
        needsAudioFeatures,
        needsTrackMetadata,
      });

      const [audioFeaturesResult, trackMetadataResult] = await Promise.allSettled([
        needsAudioFeatures
          ? this.fetchReccoBeatsAudioFeatures(trackIds, onProgress)
          : Promise.resolve(audioFeatures),
        needsTrackMetadata
          ? this.fetchReccoBeatsTrackMetadata(trackIds, onProgress)
          : Promise.resolve(trackMetadata),
      ]);

      if (audioFeaturesResult.status === 'fulfilled') {
        audioFeatures = audioFeaturesResult.value;
      } else {
        const message = errorMessage(audioFeaturesResult.reason);
        logger.warn('Failed to fetch ReccoBeats audio features; continuing with Spotify-only analysis', {
          playlistId,
          trackCount: trackIds.length,
          error: message,
        });
        errors.push({ source: 'reccobeats:audio-features', message });
        audioFeatures = [];
      }

      if (trackMetadataResult.status === 'fulfilled') {
        trackMetadata = trackMetadataResult.value;
      } else {
        const message = errorMessage(trackMetadataResult.reason);
        logger.warn('Failed to fetch ReccoBeats track metadata; continuing without metadata aggregates', {
          playlistId,
          trackCount: trackIds.length,
          error: message,
        });
        errors.push({ source: 'reccobeats:track-metadata', message });
        trackMetadata = [];
      }

      if (this.cache) {
        await this.cache.set(
          rawKey,
          {
            audio_features: audioFeatures,
            track_metadata: trackMetadata,
            schema_version: ANALYSIS_SCHEMA_VERSION,
            cached_at: new Date().toISOString(),
            track_count: trackIds.length,
          } satisfies CachedRawEnrichment,
          RAW_ENRICHMENT_CACHE_TTL_SECONDS
        );
      }
    }

    await onProgress?.(85);
    return { audioFeatures, trackMetadata };
  }

  private rawEnrichmentCacheKey(playlistId: string): string {
    // Deliberately omits `userId`: raw ReccoBeats data is derived from the
    // playlist's tracks alone, not from anything user-specific, so sharing it
    // across users for the same playlist is safe and avoids duplicate
    // fetches. This differs from the `analysis:{playlistId}:{userId}:*`
    // namespacing used by the job status/results keys.
    return `analysis:playlist:${playlistId}:raw-enrichment`;
  }

  private async emitWarmKeepaliveOnce(onProgress?: (progress: number) => Promise<void>): Promise<void> {
    if (this.emittedWarmKeepalive) return;
    this.emittedWarmKeepalive = true;
    await onProgress?.(70);
  }

  private async fetchReccoBeatsAudioFeatures(
    trackIds: string[],
    onProgress?: (progress: number) => Promise<void>
  ): Promise<ReccoBeatsAudioFeature[]> {
    const uniqueIds = [...new Set(trackIds.filter(Boolean))];
    if (uniqueIds.length === 0) return [];

    const batches = chunk(uniqueIds, BATCH_SIZE);
    const allFeatures: ReccoBeatsAudioFeature[] = [];

    // Process batches with bounded concurrency
    for (let i = 0; i < batches.length; i += CONCURRENCY) {
      const group = batches.slice(i, i + CONCURRENCY);
      const results = await Promise.all(
        group.map((batch) => this.fetchReccoBeatsAudioFeaturesBatch(batch))
      );
      for (const features of results) {
        allFeatures.push(...features);
      }
      await this.emitWarmKeepaliveOnce(onProgress);
      if (i + CONCURRENCY < batches.length) {
        await sleep(RECCOBEATS_JITTER_DELAY_MS);
      }
    }

    return allFeatures;
  }

  private async fetchReccoBeatsAudioFeaturesBatch(
    batchIds: string[]
  ): Promise<ReccoBeatsAudioFeature[]> {
    const url = new URL(`${this.reccoBeatsUrl}/audio-features`);
    for (const trackId of batchIds) {
      url.searchParams.append('ids', trackId);
    }

    let response: Response;
    try {
      response = await this.fetchWithRetry(url.toString());
    } catch (error) {
      throw new Error(`ReccoBeats API error: ${errorMessage(error)}`, { cause: error });
    }

    if (!response.ok) {
      throw new Error(`ReccoBeats API error: HTTP ${response.status}: ${response.statusText}`);
    }

    const parsed = await this.parseReccoBeatsResponse(response, 'audio-features', batchIds.length);
    const rawData = parsed.data;
    if (!this.isReccoBeatsAudioFeaturesResponse(rawData)) {
      logger.warn('Invalid ReccoBeats audio features response shape', {
        endpoint: 'audio-features',
        status: response.status,
        batchSize: batchIds.length,
        bodyPreview: parsed.bodyPreview,
      });
      throw new Error('Invalid ReccoBeats audio features response shape');
    }

    return rawData.content;
  }

  private async fetchReccoBeatsTrackMetadata(
    trackIds: string[],
    onProgress?: (progress: number) => Promise<void>
  ): Promise<ReccoBeatsTrackMetadata[]> {
    const uniqueIds = [...new Set(trackIds.filter(Boolean))];
    if (uniqueIds.length === 0) return [];

    const batches = chunk(uniqueIds, BATCH_SIZE);
    const allMetadata: ReccoBeatsTrackMetadata[] = [];

    for (let i = 0; i < batches.length; i += CONCURRENCY) {
      const group = batches.slice(i, i + CONCURRENCY);
      const results = await Promise.all(
        group.map((batch) => this.fetchReccoBeatsTrackMetadataBatch(batch))
      );
      for (const metadata of results) {
        allMetadata.push(...metadata);
      }
      await this.emitWarmKeepaliveOnce(onProgress);
    }

    return allMetadata;
  }

  private async fetchReccoBeatsTrackMetadataBatch(
    batchIds: string[]
  ): Promise<ReccoBeatsTrackMetadata[]> {
    const url = new URL(`${this.reccoBeatsUrl}/track`);
    for (const trackId of batchIds) {
      url.searchParams.append('ids', trackId);
    }

    let response: Response;
    try {
      response = await this.fetchWithRetry(url.toString());
    } catch (error) {
      throw new Error(`ReccoBeats API error: ${errorMessage(error)}`, { cause: error });
    }

    if (!response.ok) {
      throw new Error(`ReccoBeats API error: HTTP ${response.status}: ${response.statusText}`);
    }

    const parsed = await this.parseReccoBeatsResponse(response, 'track', batchIds.length);
    const rawData = parsed.data;
    if (!this.isReccoBeatsTrackMetadataResponse(rawData)) {
      logger.warn('Invalid ReccoBeats track metadata response shape', {
        endpoint: 'track',
        status: response.status,
        batchSize: batchIds.length,
        bodyPreview: parsed.bodyPreview,
      });
      throw new Error('Invalid ReccoBeats track metadata response shape');
    }

    return rawData.content;
  }

  private async parseReccoBeatsResponse(
    response: Response,
    endpoint: 'audio-features' | 'track',
    batchSize: number
  ): Promise<{ data: unknown; bodyPreview: string }> {
    const bodyText = await response.text();
    const bodyPreview = truncateResponseBody(bodyText);

    try {
      return { data: JSON.parse(bodyText), bodyPreview };
    } catch (error) {
      logger.warn('Invalid ReccoBeats JSON response', {
        endpoint,
        status: response.status,
        batchSize,
        bodyPreview,
        error: errorMessage(error),
      });
      throw new Error(`Invalid ReccoBeats ${endpoint} response JSON`, { cause: error });
    }
  }

  private async generatePlaylistInsights(
    tracks: SpotifyTrack[],
    artistData: SpotifyArtistFull[] = [],
    reccoBeatsAudioFeatures: ReccoBeatsAudioFeature[] = [],
    reccoBeatsTrackMetadata: ReccoBeatsTrackMetadata[] = []
  ): Promise<PlaylistInsights> {
    const totalTracks = tracks.length;
    if (totalTracks === 0) {
      return {
        overview: { total_tracks: 0, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
        artists: { unique_artists: 0, top_artists: [], diversity: 0 },
        genre_distribution: {},
        insights: []
      };
    }

    const totalDuration = tracks.reduce((sum, track) => sum + (track.duration_ms ?? 0), 0);
    const avgDuration = totalDuration / totalTracks;

    const artistCounts = this.countArtists(tracks);
    const topArtists = Object.entries(artistCounts)
      .sort(([, a], [, b]) => (b as number) - (a as number))
      .slice(0, 10)
      .map(([artist, count]) => ({ artist, count }));

    const genreDistribution = this.aggregateGenres(artistData);
    const insights = this.generateInsightsFromMetadata(tracks, genreDistribution);
    const audioFeatureSummary = this.aggregateReccoBeatsAudioFeatures(reccoBeatsAudioFeatures);
    const reccoBeatsMetadata = this.buildReccoBeatsMetadataSummary(reccoBeatsAudioFeatures, reccoBeatsTrackMetadata);

    return {
      overview: {
        total_tracks: totalTracks,
        total_duration_ms: totalDuration,
        average_duration_ms: avgDuration,
        formatted_duration: this.formatDuration(totalDuration)
      },
      artists: {
        unique_artists: Object.keys(artistCounts).length,
        top_artists: topArtists,
        diversity: Object.keys(artistCounts).length / totalTracks,
      },
      genre_distribution: genreDistribution,
      ...(audioFeatureSummary ? { audio_features: audioFeatureSummary } : {}),
      insights,
      ...(reccoBeatsMetadata ? { reccobeats_metadata: reccoBeatsMetadata } : {}),
    };
  }

  private aggregateGenres(artists: SpotifyArtistFull[]): Record<string, { count: number; percentage: number }> {
    const raw: Record<string, number> = {};
    for (const artist of artists) {
      for (const genre of (artist.genres ?? [])) {
        raw[genre] = (raw[genre] ?? 0) + 1;
      }
    }
    const total = Object.values(raw).reduce((s, n) => s + n, 0);
    if (total === 0) return {};

    return Object.fromEntries(
      Object.entries(raw)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 15)
        .map(([genre, count]) => [genre, { count, percentage: Math.round((count / total) * 1000) / 10 }])
    );
  }

  private aggregateReccoBeatsAudioFeatures(features: ReccoBeatsAudioFeature[]): AudioFeatureSummary | undefined {
    if (features.length === 0) {
      return undefined;
    }

    const fields: Array<keyof AudioFeatureAverages> = [
      'acousticness',
      'danceability',
      'energy',
      'instrumentalness',
      'liveness',
      'loudness',
      'speechiness',
      'tempo',
      'valence',
    ];
    const averages = fields.reduce((acc, field) => {
      const total = features.reduce((sum, feature) => sum + feature[field], 0);
      acc[field] = Math.round((total / features.length) * 10000) / 10000;
      return acc;
    }, {} as AudioFeatureAverages);

    const keyModeDistribution = this.aggregateKeyModeDistribution(features);

    return {
      track_count: features.length,
      averages,
      ...(keyModeDistribution ? { key_mode_distribution: keyModeDistribution } : {}),
    };
  }

  private aggregateKeyModeDistribution(features: ReccoBeatsAudioFeature[]): KeyModeDistribution | undefined {
    const valid = features.filter(
      (f) =>
        typeof f.key === 'number' &&
        f.key >= 0 &&
        f.key < MUSIC_KEYS.length &&
        (f.mode === 0 || f.mode === 1)
    );

    if (valid.length < 2) {
      return undefined;
    }

    const keyCounts: Record<string, number> = {};
    const modeCounts = { major: 0, minor: 0 };
    for (const f of valid) {
      const name = MUSIC_KEYS[f.key as number];
      keyCounts[name] = (keyCounts[name] ?? 0) + 1;
      if (f.mode === 1) {
        modeCounts.major += 1;
      } else {
        modeCounts.minor += 1;
      }
    }

    const keyPercentages = Object.fromEntries(
      Object.entries(keyCounts).map(([name, count]) => [name, round1((count / valid.length) * 100)])
    );
    const [dominantKey, dominantKeyCount] = Object.entries(keyCounts).sort(([, a], [, b]) => b - a)[0];

    const modePercentages = {
      major: round1((modeCounts.major / valid.length) * 100),
      minor: round1((modeCounts.minor / valid.length) * 100),
    };
    const dominantMode: 'major' | 'minor' = modeCounts.major >= modeCounts.minor ? 'major' : 'minor';

    return {
      key_percentages: keyPercentages,
      dominant_key: dominantKey,
      dominant_key_percentage: round1((dominantKeyCount / valid.length) * 100),
      mode_percentages: modePercentages,
      dominant_mode: dominantMode,
    };
  }

  private buildReccoBeatsMetadataSummary(
    audioFeatures: ReccoBeatsAudioFeature[],
    trackMetadata: ReccoBeatsTrackMetadata[]
  ): PlaylistInsights['reccobeats_metadata'] | undefined {
    if (audioFeatures.length === 0 && trackMetadata.length === 0) {
      return undefined;
    }

    const isrcAvailable = audioFeatures.filter(
      (f) => typeof f.isrc === 'string' && f.isrc.length > 0
    ).length;

    const popularityValues = trackMetadata
      .map((m) => m.popularity)
      .filter((p): p is number => typeof p === 'number');

    const summary: NonNullable<PlaylistInsights['reccobeats_metadata']> = {
      isrc_available: isrcAvailable,
      retrieved_at: new Date().toISOString(),
    };

    if (popularityValues.length > 0) {
      summary.popularity_min = Math.min(...popularityValues);
      summary.popularity_max = Math.max(...popularityValues);
    }

    return summary;
  }

  private isReccoBeatsAudioFeaturesResponse(data: unknown): data is ReccoBeatsAudioFeaturesResponse {
    if (!data || typeof data !== 'object') {
      return false;
    }

    const content = (data as { content?: unknown }).content;
    return Array.isArray(content) && content.every((item) => this.isReccoBeatsAudioFeature(item));
  }

  private isReccoBeatsAudioFeature(data: unknown): data is ReccoBeatsAudioFeature {
    if (!data || typeof data !== 'object') {
      return false;
    }

    const record = data as Record<string, unknown>;
    return typeof record.id === 'string'
      && typeof record.href === 'string'
      && typeof record.acousticness === 'number'
      && typeof record.danceability === 'number'
      && typeof record.energy === 'number'
      && typeof record.instrumentalness === 'number'
      && typeof record.liveness === 'number'
      && typeof record.loudness === 'number'
      && typeof record.speechiness === 'number'
      && typeof record.tempo === 'number'
      && typeof record.valence === 'number';
  }

  private isReccoBeatsTrackMetadataResponse(data: unknown): data is ReccoBeatsTrackMetadataResponse {
    if (!data || typeof data !== 'object') {
      return false;
    }

    const content = (data as { content?: unknown }).content;
    return Array.isArray(content) && content.every((item) => this.isReccoBeatsTrackMetadata(item));
  }

  private isReccoBeatsTrackMetadata(data: unknown): data is ReccoBeatsTrackMetadata {
    if (!data || typeof data !== 'object') {
      return false;
    }

    const record = data as Record<string, unknown>;
    if (typeof record.id !== 'string' || typeof record.trackTitle !== 'string') {
      return false;
    }
    if (typeof record.durationMs !== 'number') {
      return false;
    }
    if (!Array.isArray(record.artists)) {
      return false;
    }
    const artistsValid = record.artists.every((artist) => {
      if (!artist || typeof artist !== 'object') return false;
      const a = artist as Record<string, unknown>;
      return typeof a.id === 'string' && typeof a.name === 'string' && typeof a.href === 'string';
    });
    if (!artistsValid) {
      return false;
    }
    if (record.isrc !== undefined && typeof record.isrc !== 'string') {
      return false;
    }
    if (record.popularity !== undefined && typeof record.popularity !== 'number') {
      return false;
    }
    return true;
  }

  private countArtists(tracks: SpotifyTrack[]): Record<string, number> {
    return tracks.reduce((acc: Record<string, number>, track) => {
      track.artists.forEach((artist) => {
        acc[artist.name] = (acc[artist.name] || 0) + 1;
      });
      return acc;
    }, {});
  }

  private generateInsightsFromMetadata(
    tracks: SpotifyTrack[],
    genreDistribution: Record<string, { count: number; percentage: number }>
  ): string[] {
    const insights: string[] = [];
    const total = tracks.length;
    if (total === 0) return insights;

    // Duration-based insight
    const avgDurationMin = tracks.reduce((s, t) => s + (t.duration_ms ?? 0), 0) / total / 60_000;
    if (avgDurationMin > 5) {
      insights.push('This playlist features longer tracks — great for immersive listening.');
    } else if (avgDurationMin < 2.5) {
      insights.push('Short, punchy tracks — this playlist keeps things moving fast.');
    }

    // Genre diversity
    const topGenres = Object.entries(genreDistribution)
      .sort(([, a], [, b]) => b.count - a.count)
      .slice(0, 3)
      .map(([g]) => g);
    if (topGenres.length > 0) {
      insights.push(`Top genres: ${topGenres.join(', ')}.`);
    }
    if (Object.keys(genreDistribution).length > 10) {
      insights.push('This playlist spans a wide variety of genres.');
    }

    return insights;
  }

  private formatDuration(ms: number): string {
    const hours = Math.floor(ms / (1000 * 60 * 60));
    const minutes = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((ms % (1000 * 60)) / 1000);

    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  }
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

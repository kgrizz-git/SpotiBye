import { SpotifyService } from './spotify';
import { CacheService } from './cache';
import { ReccoBeatsTrackCacheService } from './reccobeats-track-cache';
import { logger } from '../utils/logger';
import { ANALYSIS_SCHEMA_VERSION, MUSIC_KEYS } from '../utils/constants';
import type { SpotifyArtistFull, SpotifyTrack, SpotifyPlaylistTrackItem } from '../types/spotify';
import type {
  AnalysisResult,
  AudioFeatureAverages,
  AudioFeatureSummary,
  KeyModeDistribution,
  PlaylistInsights,
  ReccoBeatsAudioFeature,
  ReccoBeatsResolveCounters,
  ReccoBeatsTrackMetadata,
} from '../types/analysis';

export class AnalysisService {
  private accessToken: string;
  private cache?: CacheService;

  constructor(accessToken: string, cache?: CacheService) {
    this.accessToken = accessToken;
    this.cache = cache;
  }

  async analyzePlaylist(
    playlistId: string,
    userId: string,
    jobId: string,
    onProgress?: (progress: number) => Promise<void>,
    options: { forceEnrichment?: boolean } = {}
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
      logger.info('Fetching Spotify artist metadata', { playlistId, artistCount: artistIdSet.size });
      await onProgress?.(50);
      const artistData = await this.fetchSpotifyArtistsForGenres(spotifyService, [...artistIdSet], playlistId, errors);

      await onProgress?.(65);

      // NOTE: Spotify /audio-features was removed in the Feb 2026 API migration.
      // ReccoBeats audio features + track metadata are best-effort enrichment;
      // core insights use Spotify track metadata and artist genres.
      const trackIds = tracks.map((track) => track.id);
      const enrichment = await this.fetchReccoBeatsEnrichment(
        playlistId,
        trackIds,
        errors,
        onProgress,
        options.forceEnrichment === true
      );

      logger.info('Generating insights from metadata', { playlistId });
      await onProgress?.(95);
      const spotifyInsights = await this.generatePlaylistInsights(
        tracks,
        artistData,
        enrichment.audioFeatures,
        enrichment.trackMetadata
      );

      return {
        job_id: jobId,
        playlist_id: playlistId,
        user_id: userId,
        status: 'completed',
        computed_at: new Date().toISOString(),
        ...spotifyInsights,
        unique_track_count: enrichment.uniqueTrackCount,
        audio_features_resolved_count: enrichment.audioFeaturesResolvedCount,
        track_metadata_resolved_count: enrichment.trackMetadataResolvedCount,
        enrichment_resolved_track_count: enrichment.enrichmentResolvedTrackCount,
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
   * Resolves ReccoBeats audio features + track metadata via the global
   * per-track cache (best-effort — failures are recorded in `errors`).
   * Endpoint writes are independent: metadata failure must not discard
   * successful audio-feature cache writes.
   */
  private async fetchReccoBeatsEnrichment(
    playlistId: string,
    trackIds: string[],
    errors: Array<{ source: string; message: string }>,
    onProgress?: (progress: number) => Promise<void>,
    forceEnrichment = false
  ): Promise<{
    audioFeatures: ReccoBeatsAudioFeature[];
    trackMetadata: ReccoBeatsTrackMetadata[];
    uniqueTrackCount: number;
    audioFeaturesResolvedCount: number;
    trackMetadataResolvedCount: number;
    enrichmentResolvedTrackCount: number;
  }> {
    const uniqueTrackIds = [...new Set(trackIds.filter(Boolean))];
    const uniqueTrackCount = uniqueTrackIds.length;

    if (uniqueTrackCount === 0) {
      await onProgress?.(85);
      return {
        audioFeatures: [],
        trackMetadata: [],
        uniqueTrackCount: 0,
        audioFeaturesResolvedCount: 0,
        trackMetadataResolvedCount: 0,
        enrichmentResolvedTrackCount: 0,
      };
    }

    logger.info('Resolving ReccoBeats enrichment via per-track cache', {
      playlistId,
      trackCount: uniqueTrackCount,
      forceEnrichment,
    });

    const trackCache = new ReccoBeatsTrackCacheService(this.cache);
    let lastEmitted = 65;
    let completedGroups = 0;
    // Approximate group count for progress: AF batches + metadata batches.
    const batchCount = Math.ceil(uniqueTrackCount / 30);
    const totalGroups = batchCount * 2;
    const emitEnrichmentProgress = async (): Promise<void> => {
      if (!onProgress || totalGroups === 0) return;
      completedGroups += 1;
      const calculated = 65 + Math.floor((completedGroups / totalGroups) * 20);
      const next = Math.min(85, Math.max(lastEmitted + 1, calculated));
      if (next > lastEmitted) {
        lastEmitted = next;
        await onProgress(next);
      }
    };

    lastEmitted = 75;
    await onProgress?.(75);

    const resolveOpts = {
      force: forceEnrichment,
      onGroupComplete: emitEnrichmentProgress,
    };

    const [audioFeaturesResult, trackMetadataResult] = await Promise.allSettled([
      trackCache.resolveAudioFeatures(uniqueTrackIds, resolveOpts),
      trackCache.resolveTrackMetadata(uniqueTrackIds, resolveOpts),
    ]);

    let audioFeatures: ReccoBeatsAudioFeature[] = [];
    let audioCounters: ReccoBeatsResolveCounters = {
      fetchedCount: 0,
      negativeSkipped: 0,
      unparseableCount: 0,
      resolvedCount: 0,
      resolvedIds: [],
      absentIds: [],
      unresolvedIds: [...uniqueTrackIds],
    };

    if (audioFeaturesResult.status === 'fulfilled') {
      audioFeatures = [...audioFeaturesResult.value.bySpotifyId.values()];
      audioCounters = audioFeaturesResult.value.counters;
    } else {
      const message = errorMessage(audioFeaturesResult.reason);
      logger.warn('Failed to fetch ReccoBeats audio features; continuing with Spotify-only analysis', {
        playlistId,
        trackCount: uniqueTrackCount,
        error: message,
      });
      errors.push({ source: 'reccobeats:audio-features', message });
    }

    let trackMetadata: ReccoBeatsTrackMetadata[] = [];
    let metadataCounters: ReccoBeatsResolveCounters = {
      fetchedCount: 0,
      negativeSkipped: 0,
      unparseableCount: 0,
      resolvedCount: 0,
      resolvedIds: [],
      absentIds: [],
      unresolvedIds: [...uniqueTrackIds],
    };

    if (trackMetadataResult.status === 'fulfilled') {
      trackMetadata = [...trackMetadataResult.value.bySpotifyId.values()];
      metadataCounters = trackMetadataResult.value.counters;
    } else {
      const message = errorMessage(trackMetadataResult.reason);
      logger.warn('Failed to fetch ReccoBeats track metadata; continuing without metadata aggregates', {
        playlistId,
        trackCount: uniqueTrackCount,
        error: message,
      });
      errors.push({ source: 'reccobeats:track-metadata', message });
    }

    this.recordReccoBeatsCoverageWarning(uniqueTrackCount, audioFeatures, errors);

    const audioFeaturesResolvedCount = audioCounters.resolvedCount;
    const trackMetadataResolvedCount = metadataCounters.resolvedCount;
    const enrichmentResolvedTrackCount = Math.min(
      audioFeaturesResolvedCount,
      trackMetadataResolvedCount
    );

    await onProgress?.(85);
    return {
      audioFeatures,
      trackMetadata,
      uniqueTrackCount,
      audioFeaturesResolvedCount,
      trackMetadataResolvedCount,
      enrichmentResolvedTrackCount,
    };
  }

  private async fetchSpotifyArtistsForGenres(
    spotifyService: SpotifyService,
    artistIds: string[],
    playlistId: string,
    errors: Array<{ source: string; message: string }>
  ): Promise<SpotifyArtistFull[]> {
    const uniqueIds = [...new Set(artistIds.filter(Boolean))].slice(0, 40);
    if (uniqueIds.length === 0) {
      return [];
    }

    try {
      return await spotifyService.getArtists(uniqueIds);
    } catch (error) {
      const message = errorMessage(error);
      if (!message.startsWith('HTTP 404:')) {
        logger.warn('Failed to fetch Spotify artist metadata; continuing without genre insights', {
          playlistId,
          artistCount: uniqueIds.length,
          error: message,
        });
        errors.push({ source: 'spotify:artists', message });
        return [];
      }
    }

    const results: SpotifyArtistFull[] = [];
    let failedCount = 0;
    let nextIndex = 0;
    const concurrency = 5;

    const workers = Array.from(
      { length: Math.min(concurrency, uniqueIds.length) },
      async () => {
        while (nextIndex < uniqueIds.length) {
          const currentIndex = nextIndex;
          nextIndex += 1;
          try {
            const artist = await spotifyService.getArtist(uniqueIds[currentIndex]);
            results[currentIndex] = artist;
          } catch (error) {
            failedCount += 1;
            logger.warn('Failed to fetch Spotify artist metadata item; preserving other genre insights', {
              playlistId,
              artistId: uniqueIds[currentIndex],
              error: errorMessage(error),
            });
          }
        }
      }
    );

    await Promise.all(workers);

    const resolvedArtists = results.filter(Boolean);
    if (failedCount > 0) {
      const message =
        `Spotify artist metadata partially available: resolved ${resolvedArtists.length} of ${uniqueIds.length} artists; ` +
        `${failedCount} failed.`;
      errors.push({ source: 'spotify:artists', message });
    }

    return resolvedArtists;
  }

  private recordReccoBeatsCoverageWarning(
    uniqueTrackCount: number,
    audioFeatures: ReccoBeatsAudioFeature[],
    errors: Array<{ source: string; message: string }>
  ): void {
    if (errors.some((error) => error.source === 'reccobeats:audio-features')) {
      return;
    }

    if (uniqueTrackCount === 0) {
      return;
    }

    const coverageRatio = audioFeatures.length / uniqueTrackCount;
    if (coverageRatio === 0 || coverageRatio < 0.5) {
      errors.push({
        source: 'reccobeats:coverage',
        message: `Audio features available for ${audioFeatures.length} of ${uniqueTrackCount} tracks.`,
      });
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

  private countArtists(tracks: SpotifyTrack[]): Record<string, number> {
    return tracks.reduce((acc: Record<string, number>, track) => {
      track.artists.forEach((artist) => {
        if (typeof artist.name !== 'string') {
          return;
        }
        const name = artist.name.trim();
        if (!name) {
          return;
        }
        acc[name] = (acc[name] || 0) + 1;
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

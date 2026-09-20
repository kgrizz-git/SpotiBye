import type {
  ReccoBeatsAudioFeature,
  ReccoBeatsTrackMetadata,
} from '../types/analysis';
import type { SpotifyArtistFull, SpotifyTrack } from '../types/spotify';

/**
 * Fan-out helpers for large-playlist analysis (pure functions — no I/O).
 *
 * A single queue message does a whole playlist in one Worker invocation.
 * Past the subrequest budget that fails live (`Too many subrequests by
 * single Worker invocation`, observed 2026-09-19), so large playlists are
 * split into per-chunk queue messages, each fitting the budget.
 */

/** Fan out when unique artists exceed this (mirrors the old silent cap). */
export const FANOUT_ARTIST_THRESHOLD = 40;
/** Per-invocation subrequest budget target (Cloudflare limit is 50). */
export const FANOUT_SUBREQUEST_BUDGET = 40;
const RECCOBEATS_BATCH_SIZE = 30;
const SPOTIFY_TRACK_PAGE_SIZE = 100;
const SPOTIFY_ARTIST_PAGE_SIZE = 50;
/**
 * Worst-case KV ops per track (positive + absent reads, miss writes).
 * Conservative on purpose — Phase 0 calibrates against measured counts.
 */
const KV_OPS_PER_TRACK_WORST_CASE = 4;

/** Track with its artist IDs, for budget-aware chunking. */
export interface TrackArtistIndex {
  trackId: string;
  artistIds: string[];
}

/**
 * Worst-case subrequest estimate for one invocation handling
 * `trackCount` tracks and `artistCount` artists.
 */
export function estimateSubrequests(trackCount: number, artistCount: number): number {
  if (trackCount <= 0) return 0;
  return (
    Math.ceil(trackCount / SPOTIFY_TRACK_PAGE_SIZE) +
    Math.ceil(artistCount / SPOTIFY_ARTIST_PAGE_SIZE) +
    2 * Math.ceil(trackCount / RECCOBEATS_BATCH_SIZE) +
    KV_OPS_PER_TRACK_WORST_CASE * trackCount
  );
}

export function shouldFanOut(trackCount: number, artistCount: number): boolean {
  return (
    artistCount > FANOUT_ARTIST_THRESHOLD ||
    estimateSubrequests(trackCount, artistCount) > FANOUT_SUBREQUEST_BUDGET
  );
}

/**
 * Greedily pack tracks into chunks so each chunk's worst-case estimate fits
 * `budget` and no chunk holds more than FANOUT_ARTIST_THRESHOLD artists.
 * A single track can exceed the artist cap on its own — it gets a chunk to
 * itself (cannot split a track further).
 */
export function chunkTrackIds(
  tracks: TrackArtistIndex[],
  budget: number = FANOUT_SUBREQUEST_BUDGET
): string[][] {
  const chunks: string[][] = [];
  let current: string[] = [];
  let currentArtists = new Set<string>();
  const flush = (): void => {
    if (current.length > 0) {
      chunks.push(current);
      current = [];
      currentArtists = new Set<string>();
    }
  };
  for (const track of tracks) {
    const nextArtists = new Set<string>([...currentArtists, ...track.artistIds]);
    const trial = [...current, track.trackId];
    if (
      current.length > 0 &&
      (estimateSubrequests(trial.length, nextArtists.size) > budget ||
        nextArtists.size > FANOUT_ARTIST_THRESHOLD)
    ) {
      flush();
      currentArtists = new Set<string>(track.artistIds);
      current = [track.trackId];
    } else {
      current = trial;
      currentArtists = nextArtists;
    }
  }
  flush();
  return chunks;
}

export function chunkResultKey(
  playlistId: string,
  userId: string,
  jobId: string,
  chunkId: string
): string {
  return `analysis:${playlistId}:${userId}:chunks:${jobId}:${chunkId}`;
}

/** KV snapshot of the enumerated track list for finalize-time insights. */
export function fanoutTracksKey(playlistId: string, userId: string, jobId: string): string {
  return `analysis:${playlistId}:${userId}:fandata:${jobId}`;
}

/** KV snapshot of the enumerated job input for finalize-time insights. */
export interface FanoutTracksSnapshot {
  tracks: SpotifyTrack[];
  chunkIds: string[];
  forceEnrichment: boolean;
}

/** One chunk's intermediate result, stored under chunkResultKey(). */
export interface AnalysisChunkPartial {
  chunk_id: string;
  track_ids: string[];
  artistData: SpotifyArtistFull[];
  audioFeatures: ReccoBeatsAudioFeature[];
  trackMetadata: ReccoBeatsTrackMetadata[];
  errors: Array<{ source: string; message: string }>;
  audioFeaturesResolvedCount: number;
  trackMetadataResolvedCount: number;
  enrichmentResolvedTrackCount: number;
  schema_version: string;
}

export interface MergedChunkData {
  trackIds: string[];
  artistData: SpotifyArtistFull[];
  audioFeatures: ReccoBeatsAudioFeature[];
  trackMetadata: ReccoBeatsTrackMetadata[];
  errors: Array<{ source: string; message: string }>;
  audioFeaturesResolvedCount: number;
  trackMetadataResolvedCount: number;
  enrichmentResolvedTrackCount: number;
  schemaVersions: string[];
}

/**
 * Merge chunk partials: concat rows/errors, dedupe artists by ID (first
 * wins), sum resolved counters. Percentages and insight aggregates are
 * recomputed downstream by generatePlaylistInsights — never averaged here.
 */
export function mergePartials(partials: AnalysisChunkPartial[]): MergedChunkData {
  const artistById = new Map<string, SpotifyArtistFull>();
  const merged: MergedChunkData = {
    trackIds: [],
    artistData: [],
    audioFeatures: [],
    trackMetadata: [],
    errors: [],
    audioFeaturesResolvedCount: 0,
    trackMetadataResolvedCount: 0,
    enrichmentResolvedTrackCount: 0,
    schemaVersions: [],
  };
  for (const partial of partials) {
    merged.trackIds.push(...partial.track_ids);
    for (const artist of partial.artistData) {
      if (artist.id && !artistById.has(artist.id)) {
        artistById.set(artist.id, artist);
      }
    }
    merged.audioFeatures.push(...partial.audioFeatures);
    merged.trackMetadata.push(...partial.trackMetadata);
    merged.errors.push(...partial.errors);
    merged.audioFeaturesResolvedCount += partial.audioFeaturesResolvedCount;
    merged.trackMetadataResolvedCount += partial.trackMetadataResolvedCount;
    merged.enrichmentResolvedTrackCount += partial.enrichmentResolvedTrackCount;
    merged.schemaVersions.push(partial.schema_version);
  }
  merged.artistData = [...artistById.values()];
  return merged;
}

/** Assert all partials share one schema version; return the max. */
export function resolveMergedSchemaVersion(versions: string[]): string {
  const unique = [...new Set(versions)];
  if (unique.length > 1) {
    throw new Error(`Chunk schema versions differ: ${unique.join(', ')}`);
  }
  return unique[0] ?? 'unknown';
}

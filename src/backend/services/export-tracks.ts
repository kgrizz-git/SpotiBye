/**
 * Export track assembly — playlist metadata, duration totals, and per-track rows.
 *
 * When `include_audio_features` is true, enrichment columns are populated from
 * the global per-track ReccoBeats cache (`ReccoBeatsTrackCacheService`) with
 * on-demand miss-fill — analysis does not need to run first.
 */
import type { ExportTrack, ExportData } from './export-types';
import type { SpotifyPlaylist, SpotifyTrack, SpotifyPlaylistTrackItem } from '../types/spotify';
import type { ReccoBeatsAudioFeature } from '../types/analysis';
import { formatDuration } from './export-format-helpers';
import { keyName, modeName } from '../utils/music-helpers';
import { CacheService } from './cache';
import { ReccoBeatsTrackCacheService } from './reccobeats-track-cache';
import { logger } from '../utils/logger';

/** Numeric ReccoBeats audio-feature fields used by export columns (no time_signature). */
export interface ReccoBeatsExportFeatures {
  tempo?: number;
  key?: number;
  mode?: number;
  danceability?: number;
  energy?: number;
  valence?: number;
  acousticness?: number;
  instrumentalness?: number;
  liveness?: number;
  speechiness?: number;
  loudness?: number;
}

export function toExportFeatures(row: ReccoBeatsAudioFeature): ReccoBeatsExportFeatures {
  return {
    tempo: row.tempo,
    key: row.key,
    mode: row.mode,
    danceability: row.danceability,
    energy: row.energy,
    valence: row.valence,
    acousticness: row.acousticness,
    instrumentalness: row.instrumentalness,
    liveness: row.liveness,
    speechiness: row.speechiness,
    loudness: row.loudness,
  };
}

export function buildPlaylistMetadata(playlist: SpotifyPlaylist | undefined, fallbackTrackCount: number): ExportData['playlist'] {
  return {
    id: playlist?.id || '',
    name: playlist?.name || 'Unknown Playlist',
    description: playlist?.description || '',
    total_tracks: playlist?.items?.total ?? playlist?.tracks?.total ?? fallbackTrackCount,
    owner: playlist?.owner?.display_name || 'Unknown',
    followers: playlist?.followers?.total || 0,
    url: playlist?.external_urls?.spotify || '',
    cover_image_url: Array.isArray(playlist?.images) && playlist.images.length > 0 ? playlist.images[0]?.url : undefined,
  };
}

export function calculateTotalDurationMs(items: SpotifyPlaylistTrackItem[]): number {
  return items
    .filter((item) => item.track && typeof item.track.duration_ms === 'number')
    .reduce((acc, item) => acc + (item.track!.duration_ms || 0), 0);
}

export function mapTrackForExport(
  track: SpotifyTrack,
  audioFeatures: ReccoBeatsExportFeatures | null | undefined,
): ExportTrack {
  const key = keyName(audioFeatures?.key);
  const mode = modeName(audioFeatures?.mode);
  const keyValue = key ? `${key}${mode ? ` ${mode}` : ''}` : 'N/A';

  return {
    Artist: track.artists.map((artist) => artist.name).join(', '),
    Album: track.album?.name || '',
    Track: track.name,
    Duration: formatDuration(track.duration_ms),
    'Spotify URL': track.external_urls?.spotify || '',
    Tempo: typeof audioFeatures?.tempo === 'number' ? Number(audioFeatures.tempo.toFixed(2)) : 'N/A',
    Key: keyValue,
    Danceability: typeof audioFeatures?.danceability === 'number' ? Number(audioFeatures.danceability.toFixed(3)) : 'N/A',
    Energy: typeof audioFeatures?.energy === 'number' ? Number(audioFeatures.energy.toFixed(3)) : 'N/A',
    Valence: typeof audioFeatures?.valence === 'number' ? Number(audioFeatures.valence.toFixed(3)) : 'N/A',
    Acousticness: typeof audioFeatures?.acousticness === 'number' ? Number(audioFeatures.acousticness.toFixed(3)) : 'N/A',
    Instrumentalness: typeof audioFeatures?.instrumentalness === 'number' ? Number(audioFeatures.instrumentalness.toFixed(3)) : 'N/A',
    Liveness: typeof audioFeatures?.liveness === 'number' ? Number(audioFeatures.liveness.toFixed(3)) : 'N/A',
    Speechiness: typeof audioFeatures?.speechiness === 'number' ? Number(audioFeatures.speechiness.toFixed(3)) : 'N/A',
    Loudness: typeof audioFeatures?.loudness === 'number' ? Number(audioFeatures.loudness.toFixed(1)) : 'N/A',
    // ReccoBeats does not expose time_signature — permanent N/A for export.
    'Time Signature': 'N/A',
  };
}

export async function loadAudioFeaturesMap(
  trackIds: string[],
  includeAudioFeatures: boolean,
  cache?: CacheService,
): Promise<Map<string, ReccoBeatsExportFeatures>> {
  const audioFeaturesMap = new Map<string, ReccoBeatsExportFeatures>();

  if (!includeAudioFeatures || trackIds.length === 0) {
    return audioFeaturesMap;
  }

  if (!cache) {
    throw new Error('CacheService is required to resolve ReccoBeats enrichment for export');
  }

  const uniqueIds = [...new Set(trackIds.filter(Boolean))];
  const trackCache = new ReccoBeatsTrackCacheService(cache);

  try {
    const result = await trackCache.resolveAudioFeatures(uniqueIds);
    for (const [spotifyId, row] of result.bySpotifyId) {
      audioFeaturesMap.set(spotifyId, toExportFeatures(row));
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    logger.warn('ReccoBeats audio-features resolve failed for export; unresolved columns remain N/A', {
      trackCount: uniqueIds.length,
      error: message,
    });
  }

  return audioFeaturesMap;
}

export async function buildExportTracks(
  allTracks: SpotifyPlaylistTrackItem[],
  includeAudioFeatures: boolean,
  cache?: CacheService,
): Promise<ExportTrack[]> {
  const trackIds = allTracks
    .filter((item) => item.track && item.track.id)
    .map((item) => item.track!.id);

  const audioFeaturesMap = await loadAudioFeaturesMap(trackIds, includeAudioFeatures, cache);

  return allTracks
    .filter((item) => item.track)
    .map((item) => mapTrackForExport(item.track!, audioFeaturesMap.get(item.track!.id) ?? null));
}

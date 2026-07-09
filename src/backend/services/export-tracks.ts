import type { ExportTrack, ExportData } from './export-types';
import type { SpotifyPlaylist, SpotifyTrack, SpotifyPlaylistTrackItem, SpotifyAudioFeatures } from '../types/spotify';
import { formatDuration } from './export-format-helpers';
import { SpotifyService } from './spotify';
import { keyName, modeName } from '../utils/music-helpers';

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

export function mapTrackForExport(track: SpotifyTrack, audioFeatures: SpotifyAudioFeatures | null | undefined): ExportTrack {
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
    'Time Signature': typeof audioFeatures?.time_signature === 'number' ? audioFeatures.time_signature : 'N/A',
  };
}

export async function loadAudioFeaturesMap(
  trackIds: string[],
  includeAudioFeatures: boolean,
  spotifyService: SpotifyService,
): Promise<Map<string, SpotifyAudioFeatures>> {
  const audioFeaturesMap = new Map<string, SpotifyAudioFeatures>();
  let audioFeaturesUnavailable = false;

  if (!includeAudioFeatures || trackIds.length === 0) {
    return audioFeaturesMap;
  }

  for (let i = 0; i < trackIds.length; i += 100) {
    if (audioFeaturesUnavailable) {
      break;
    }
    const batch = trackIds.slice(i, i + 100);
    try {
      const audioFeatures = await spotifyService.getMultipleAudioFeatures(batch);
      audioFeatures.forEach((feature) => {
        if (feature) {
          audioFeaturesMap.set(feature.id, feature);
        }
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (/HTTP\s+(401|403)/i.test(message)) {
        audioFeaturesUnavailable = true;
        console.warn('Audio-features API unavailable for this token; skipping remaining batches', {
          batchStart: i,
          batchSize: batch.length,
          error: message,
        });
        continue;
      }
      console.warn('Audio-features batch failed; continuing without those features', {
        batchStart: i,
        batchSize: batch.length,
        error: message,
      });
    }
  }

  return audioFeaturesMap;
}

export async function buildExportTracks(
  allTracks: SpotifyPlaylistTrackItem[],
  includeAudioFeatures: boolean,
  spotifyService: SpotifyService,
): Promise<ExportTrack[]> {
  const trackIds = allTracks
    .filter((item) => item.track && item.track.id)
    .map((item) => item.track!.id);

  const audioFeaturesMap = await loadAudioFeaturesMap(trackIds, includeAudioFeatures, spotifyService);

  return allTracks
    .filter((item) => item.track)
    .map((item) => mapTrackForExport(item.track!, audioFeaturesMap.get(item.track!.id) ?? null));
}

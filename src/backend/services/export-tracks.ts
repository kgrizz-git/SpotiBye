import type { ExportTrack, ExportData } from './export-types';
import { formatDuration } from './export-format-helpers';
import { SpotifyService } from './spotify';

export function buildPlaylistMetadata(playlist: any, fallbackTrackCount: number): ExportData['playlist'] {
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

export function calculateTotalDurationMs(items: any[]): number {
  return items
    .filter((item: any) => item.track && typeof item.track.duration_ms === 'number')
    .reduce((acc: number, item: any) => acc + (item.track.duration_ms || 0), 0);
}

export function mapTrackForExport(track: any, audioFeatures: any): ExportTrack {
  const keyMap = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const modeMap: Record<number, string> = { 0: 'minor', 1: 'major' };
  const keyName = typeof audioFeatures?.key === 'number' && audioFeatures.key >= 0 && audioFeatures.key < keyMap.length
    ? keyMap[audioFeatures.key]
    : null;
  const modeName = typeof audioFeatures?.mode === 'number' ? modeMap[audioFeatures.mode] : null;
  const keyValue = keyName ? `${keyName}${modeName ? ` ${modeName}` : ''}` : 'N/A';

  return {
    Artist: track.artists.map((artist: any) => artist.name).join(', '),
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
): Promise<Map<string, any>> {
  const audioFeaturesMap = new Map<string, any>();
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
  allTracks: any[],
  includeAudioFeatures: boolean,
  spotifyService: SpotifyService,
): Promise<ExportTrack[]> {
  const trackIds = allTracks
    .filter((item: any) => item.track && item.track.id)
    .map((item: any) => item.track.id);

  const audioFeaturesMap = await loadAudioFeaturesMap(trackIds, includeAudioFeatures, spotifyService);

  return allTracks
    .filter((item: any) => item.track)
    .map((item: any) => mapTrackForExport(item.track, audioFeaturesMap.get(item.track.id)));
}

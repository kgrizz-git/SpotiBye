import type { ExportData, ResumableExportAssemblyState, ExportCellValue } from './export-types';
import { formatDuration } from './export-format-helpers';

export function generateCombinedJson(exportDataList: ExportData[]): ArrayBuffer {
  const payload = {
    generated_at: new Date().toISOString(),
    playlist_count: exportDataList.length,
    playlists: exportDataList.map((exportData) => ({
      name: exportData.playlist.name,
      owner: exportData.playlist.owner,
      followers: exportData.playlist.followers,
      description: exportData.playlist.description || '',
      url: exportData.playlist.url || '',
      cover_image_url: exportData.playlist.cover_image_url,
      total_tracks: exportData.playlist.total_tracks,
      total_duration: formatDuration(exportData.total_duration_ms),
      tracks: exportData.tracks,
    })),
  };
  return new TextEncoder().encode(JSON.stringify(payload, null, 2)).buffer as ArrayBuffer;
}

export function generateCombinedJsonFromAssembly(assemblyState: ResumableExportAssemblyState): ArrayBuffer {
  const payload = {
    generated_at: new Date().toISOString(),
    playlist_count: assemblyState.worksheets.length,
    playlists: assemblyState.worksheets.map((worksheet) => ({
      name: worksheet.playlist_name,
      owner: worksheet.playlist_owner,
      followers: worksheet.playlist_followers,
      description: worksheet.playlist_description || '',
      url: worksheet.playlist_url || '',
      cover_image_url: worksheet.playlist_cover_image_url,
      total_tracks: worksheet.rows.length,
      total_duration: worksheet.total_duration,
      tracks: worksheet.rows.map((row) => {
        const track: Record<string, ExportCellValue> = {};
        for (let i = 0; i < worksheet.headers.length; i += 1) {
          track[worksheet.headers[i]] = row[i] ?? '';
        }
        return track;
      }),
    })),
  };
  return new TextEncoder().encode(JSON.stringify(payload, null, 2)).buffer as ArrayBuffer;
}

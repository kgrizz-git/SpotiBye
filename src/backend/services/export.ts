import { SpotifyService } from './spotify';
import * as XLSX from 'xlsx';

interface ExportTrack {
  Artist: string;
  Album: string;
  Track: string;
  Duration: string;
  'Spotify URL': string;
  Tempo: number | string;
  Key: string;
  Danceability: number | string;
  Energy: number | string;
  Valence: number | string;
  Acousticness: number | string;
  Instrumentalness: number | string;
  Liveness: number | string;
  Speechiness: number | string;
  Loudness: number | string;
  'Time Signature': number | string;
}

export interface ExportData {
  playlist: {
    id: string;
    name: string;
    description: string;
    total_tracks: number;
    owner: string;
    followers: number;
    url: string;
    created_at?: string;
  };
  tracks: ExportTrack[];
  total_duration_ms: number;
  generated_at: string;
}

export class ExportService {
  private accessToken: string;
  
  constructor(accessToken: string) {
    this.accessToken = accessToken;
  }
  
  async generatePlaylistExport(playlistId: string): Promise<ExportData> {
    const spotifyService = new SpotifyService(this.accessToken);
    
    // Get playlist details
    const playlist = await spotifyService.getPlaylist(playlistId);
    
    // Get all tracks (handle pagination)
    const allTracks = [];
    let offset = 0;
    const limit = 100;
    
    while (true) {
      const tracksData = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
      allTracks.push(...tracksData.items);
      
      if (tracksData.items.length < limit) break;
      offset += limit;
    }
    
    // Get audio features for all tracks
    const trackIds = allTracks
      .filter((item: any) => item.track && item.track.id)
      .map((item: any) => item.track.id);
    
    const audioFeaturesMap = new Map();
    if (trackIds.length > 0) {
      // Process in batches of 100 (Spotify API limit)
      for (let i = 0; i < trackIds.length; i += 100) {
        const batch = trackIds.slice(i, i + 100);
        try {
          const audioFeatures = await spotifyService.getMultipleAudioFeatures(batch);
          audioFeatures.forEach(feature => {
            if (feature) {
              audioFeaturesMap.set(feature.id, feature);
            }
          });
        } catch (error) {
          // Export should still succeed if audio-features API fails for a batch.
          console.warn('Audio-features batch failed; continuing without those features', {
            batchStart: i,
            batchSize: batch.length,
            error: error instanceof Error ? error.message : String(error),
          });
        }
      }
    }
    
    // Transform data for export
    const exportTracks: ExportTrack[] = allTracks
      .filter((item: any) => item.track)
      .map((item: any) => {
        const track = item.track;
        const audioFeatures = audioFeaturesMap.get(track.id);
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
          Duration: this.formatDuration(track.duration_ms),
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
      });

    const totalDurationMs = allTracks
      .filter((item: any) => item.track && typeof item.track.duration_ms === 'number')
      .reduce((acc: number, item: any) => acc + (item.track.duration_ms || 0), 0);
    
    return {
      playlist: {
        id: playlist.id,
        name: playlist.name,
        description: playlist.description || '',
        total_tracks: playlist.items?.total ?? playlist.tracks?.total ?? exportTracks.length,
        owner: playlist.owner?.display_name || 'Unknown',
        followers: playlist.followers?.total || 0,
        url: playlist.external_urls?.spotify || ''
      },
      tracks: exportTracks,
      total_duration_ms: totalDurationMs,
      generated_at: new Date().toISOString()
    };
  }
  
  async generateCsvFile(exportData: ExportData): Promise<ArrayBuffer> {
    const headers = this.getTrackHeaders();
    
    // Create CSV content
    let csvContent = headers.join(',') + '\n';
    
    // Add playlist info as first row
    csvContent += `"Playlist: ${exportData.playlist.name}",,,,"Total Tracks: ${exportData.playlist.total_tracks}",,,,"Owner: ${exportData.playlist.owner}",,,,,,,\n`;
    csvContent += '\n'; // Empty row
    
    // Add track data
    for (const track of exportData.tracks) {
      const row = headers.map((header) => this.escapeCsvValue(String((track as any)[header] ?? '')));
      
      csvContent += row.join(',') + '\n';
    }
    
    // Convert to ArrayBuffer
    const encoder = new TextEncoder();
    return encoder.encode(csvContent).buffer as ArrayBuffer;
  }

  async generateExcelFile(exportData: ExportData): Promise<ArrayBuffer> {
    return this.generateCombinedExcelFile([exportData]);
  }

  async generateCombinedExcelFile(exportDataList: ExportData[]): Promise<ArrayBuffer> {
    const workbook = XLSX.utils.book_new();
    const summaryRows: Array<Array<string | number>> = [
      ['Playlist Name', 'Owner', 'Track Count', 'Duration']
    ];

    for (const exportData of exportDataList) {
      summaryRows.push([
        exportData.playlist.name,
        exportData.playlist.owner,
        exportData.tracks.length,
        this.formatDuration(exportData.total_duration_ms),
      ]);
    }

    const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows);
    summarySheet['!cols'] = [{ wch: 29 }, { wch: 24 }, { wch: 16 }, { wch: 19 }];
    XLSX.utils.book_append_sheet(workbook, summarySheet, 'Playlists');

    const headers = this.getTrackHeaders();

    for (const exportData of exportDataList) {
      const sheetName = this.sanitizeSheetName(`${exportData.playlist.name} - ${exportData.playlist.owner}`);

      const rows: Array<Array<string | number>> = [
        [exportData.playlist.name],
        [`Created by: ${exportData.playlist.owner}`],
        [`Followers: ${exportData.playlist.followers}`],
        [`Tracks exported: ${exportData.tracks.length}`],
        [`Total duration: ${this.formatDuration(exportData.total_duration_ms)}`],
        [`Playlist URL: ${exportData.playlist.url || 'N/A'}`],
        [`Description: ${exportData.playlist.description || 'N/A'}`],
        [],
        [],
        [],
        headers,
      ];

      for (const track of exportData.tracks) {
        rows.push(headers.map((header) => (track as any)[header] ?? ''));
      }

      const sheet = XLSX.utils.aoa_to_sheet(rows);
      sheet['!cols'] = [
        { wch: 30 },
        { wch: 40 },
        { wch: 40 },
        { wch: 15 },
        { wch: 60 },
        { wch: 12 },
        { wch: 14 },
        { wch: 12 },
        { wch: 12 },
        { wch: 12 },
        { wch: 12 },
        { wch: 16 },
        { wch: 12 },
        { wch: 12 },
        { wch: 12 },
        { wch: 14 },
      ];

      const startRow = 12;
      const endRow = rows.length;
      sheet['!autofilter'] = { ref: `A11:P${Math.max(endRow, 11)}` };

      for (let rowIndex = startRow; rowIndex <= endRow; rowIndex += 1) {
        const cellRef = `E${rowIndex}`;
        const cellValue = sheet[cellRef]?.v;
        if (typeof cellValue === 'string' && cellValue.startsWith('http')) {
          sheet[cellRef] = {
            t: 's',
            v: cellValue,
            l: { Target: cellValue },
          };
        }
      }

      XLSX.utils.book_append_sheet(workbook, sheet, sheetName);
    }

    return XLSX.write(workbook, { bookType: 'xlsx', type: 'array' }) as ArrayBuffer;
  }
  
  private formatDuration(ms: number): string {
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    if (hours > 0) {
      return `${hours}:${remainingMinutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    return `${remainingMinutes}:${seconds.toString().padStart(2, '0')}`;
  }

  private sanitizeSheetName(name: string): string {
    const cleaned = name.replace(/[\\/*?:\[\]]/g, ' ').trim();
    return (cleaned || 'Playlist').slice(0, 31);
  }

  private getTrackHeaders(): string[] {
    return [
      'Artist',
      'Album',
      'Track',
      'Duration',
      'Spotify URL',
      'Tempo',
      'Key',
      'Danceability',
      'Energy',
      'Valence',
      'Acousticness',
      'Instrumentalness',
      'Liveness',
      'Speechiness',
      'Loudness',
      'Time Signature',
    ];
  }
  
  private escapeCsvValue(value: string): string {
    if (value.includes(',') || value.includes('"') || value.includes('\n')) {
      return `"${value.replace(/"/g, '""')}"`;
    }
    return value;
  }
  
  async generateAdvancedExcelFile(exportData: ExportData): Promise<ArrayBuffer> {
    // Keep advanced export aligned with the primary XLSX output.
    return this.generateExcelFile(exportData);
  }
}

import { SpotifyService } from './spotify';
import ExcelJS from 'exceljs';

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
    cover_image_url?: string;
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
        url: playlist.external_urls?.spotify || '',
        cover_image_url: Array.isArray(playlist.images) && playlist.images.length > 0 ? playlist.images[0]?.url : undefined,
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
    const workbook = new ExcelJS.Workbook();
    const summarySheet = workbook.addWorksheet('Playlists');
    summarySheet.columns = [
      { header: 'Playlist Name', key: 'name', width: 29 },
      { header: 'Owner', key: 'owner', width: 24 },
      { header: 'Track Count', key: 'track_count', width: 16 },
      { header: 'Duration', key: 'duration', width: 19 },
    ];

    const summaryHeader = summarySheet.getRow(1);
    summaryHeader.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 13 };
    summaryHeader.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF4F81BD' },
    };

    for (const exportData of exportDataList) {
      summarySheet.addRow({
        name: exportData.playlist.name,
        owner: exportData.playlist.owner,
        track_count: exportData.tracks.length,
        duration: this.formatDuration(exportData.total_duration_ms),
      });
    }

    const headers = this.getTrackHeaders();

    for (const exportData of exportDataList) {
      const sheetName = this.sanitizeSheetName(`${exportData.playlist.name} - ${exportData.playlist.owner}`);

      const sheet = workbook.addWorksheet(sheetName);
      sheet.columns = [
        { key: 'A', width: 30 },
        { key: 'B', width: 40 },
        { key: 'C', width: 40 },
        { key: 'D', width: 15 },
        { key: 'E', width: 60 },
        { key: 'F', width: 12 },
        { key: 'G', width: 14 },
        { key: 'H', width: 12 },
        { key: 'I', width: 12 },
        { key: 'J', width: 12 },
        { key: 'K', width: 12 },
        { key: 'L', width: 16 },
        { key: 'M', width: 12 },
        { key: 'N', width: 12 },
        { key: 'O', width: 12 },
        { key: 'P', width: 14 },
      ];

      sheet.getCell('A1').value = exportData.playlist.name;
      sheet.getCell('A1').font = { bold: true, size: 16 };
      sheet.getCell('A2').value = `Created by: ${exportData.playlist.owner}`;
      sheet.getCell('A3').value = `Followers: ${exportData.playlist.followers}`;
      sheet.getCell('A4').value = `Tracks exported: ${exportData.tracks.length}`;
      sheet.getCell('A5').value = `Total duration: ${this.formatDuration(exportData.total_duration_ms)}`;
      sheet.getCell('A6').value = `Playlist URL: ${exportData.playlist.url || 'N/A'}`;
      sheet.getCell('A7').value = `Description: ${exportData.playlist.description || 'N/A'}`;

      if (exportData.playlist.url) {
        sheet.getCell('A6').value = {
          text: `Playlist URL: ${exportData.playlist.url}`,
          hyperlink: exportData.playlist.url,
        };
      }

      // Try to embed a cover image like legacy desktop export. Failure should never block export.
      await this.tryAddCoverImage(workbook, sheet, exportData.playlist.cover_image_url);

      sheet.getRow(11).values = headers;
      const headerRow = sheet.getRow(11);
      headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
      headerRow.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FF4F81BD' },
      };

      let rowNumber = 12;
      for (const track of exportData.tracks) {
        const rowValues = headers.map((header) => (track as any)[header] ?? '');
        sheet.getRow(rowNumber).values = rowValues;
        const urlValue = (track as any)['Spotify URL'];
        if (typeof urlValue === 'string' && urlValue.startsWith('http')) {
          sheet.getCell(`E${rowNumber}`).value = { text: urlValue, hyperlink: urlValue };
          sheet.getCell(`E${rowNumber}`).font = { color: { argb: 'FF0563C1' }, underline: true };
        }
        rowNumber += 1;
      }

      if (rowNumber > 12) {
        sheet.autoFilter = {
          from: { row: 11, column: 1 },
          to: { row: rowNumber - 1, column: headers.length },
        };

        sheet.addTable({
          name: `tbl_${sheetName.replace(/[^A-Za-z0-9_]/g, '').slice(0, 20)}_${Math.floor(Math.random() * 1000)}`,
          ref: 'A11',
          headerRow: true,
          style: {
            theme: 'TableStyleMedium9',
            showRowStripes: true,
          },
          columns: headers.map((header) => ({ name: header })),
          rows: exportData.tracks.map((track) => headers.map((header) => (track as any)[header] ?? '')),
        });
      }

      for (let r = 1; r <= rowNumber; r += 1) {
        const row = sheet.getRow(r);
        row.alignment = { vertical: 'middle', horizontal: 'left', wrapText: r > 7 };
      }
    }

    const buffer = await workbook.xlsx.writeBuffer();
    return buffer as ArrayBuffer;
  }

  private async tryAddCoverImage(workbook: ExcelJS.Workbook, sheet: ExcelJS.Worksheet, imageUrl?: string): Promise<void> {
    if (!imageUrl) {
      return;
    }

    try {
      const response = await fetch(imageUrl);
      if (!response.ok) {
        console.warn('[export] cover image fetch failed', { imageUrl, status: response.status });
        return;
      }
      const bytes = await response.arrayBuffer();
      const contentType = response.headers.get('content-type') || '';
      const extension = contentType.includes('jpeg') || contentType.includes('jpg') ? 'jpeg' : 'png';
      const mimeType = extension === 'jpeg' ? 'image/jpeg' : 'image/png';
      const base64 = this.arrayBufferToBase64(bytes);
      const imageId = workbook.addImage({
        base64: `data:${mimeType};base64,${base64}`,
        extension,
      });
      sheet.addImage(imageId, {
        tl: { col: 1.1, row: 0.1 },
        ext: { width: 120, height: 120 },
      });
    } catch (error) {
      // Ignore image failures to keep export resilient, but log for diagnosis.
      console.warn('[export] cover image embedding failed', {
        imageUrl,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private arrayBufferToBase64(bytes: ArrayBuffer): string {
    if (typeof Buffer !== 'undefined') {
      return Buffer.from(bytes).toString('base64');
    }

    let binary = '';
    const chunkSize = 0x8000;
    const byteArray = new Uint8Array(bytes);
    for (let i = 0; i < byteArray.length; i += chunkSize) {
      const chunk = byteArray.subarray(i, i + chunkSize);
      binary += String.fromCharCode(...chunk);
    }
    return btoa(binary);
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

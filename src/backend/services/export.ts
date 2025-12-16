import { SpotifyService } from './spotify';
import type { SpotifyTrack, SpotifyAudioFeatures } from '../types/spotify';

interface ExportTrack {
  id: string;
  name: string;
  artists: string;
  album: string;
  duration: string;
  duration_ms: number;
  popularity: number;
  explicit: boolean;
  release_date: string;
  uri: string;
  added_at?: string;
  audio_features?: {
    acousticness: number;
    danceability: number;
    energy: number;
    instrumentalness: number;
    liveness: number;
    loudness: number;
    speechiness: number;
    valence: number;
    tempo: number;
    key: number;
    mode: number;
    time_signature: number;
  };
}

interface ExportData {
  playlist: {
    id: string;
    name: string;
    description: string;
    total_tracks: number;
    owner: string;
    created_at?: string;
  };
  tracks: ExportTrack[];
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
        const audioFeatures = await spotifyService.getMultipleAudioFeatures(batch);
        audioFeatures.forEach(feature => {
          if (feature) {
            audioFeaturesMap.set(feature.id, feature);
          }
        });
      }
    }
    
    // Transform data for export
    const exportTracks: ExportTrack[] = allTracks
      .filter((item: any) => item.track)
      .map((item: any) => {
        const track = item.track;
        const audioFeatures = audioFeaturesMap.get(track.id);
        
        return {
          id: track.id,
          name: track.name,
          artists: track.artists.map((artist: any) => artist.name).join(', '),
          album: track.album.name,
          duration: this.formatDuration(track.duration_ms),
          duration_ms: track.duration_ms,
          popularity: track.popularity,
          explicit: track.explicit,
          release_date: track.album.release_date,
          uri: track.uri,
          added_at: item.added_at,
          audio_features: audioFeatures ? {
            acousticness: audioFeatures.acousticness,
            danceability: audioFeatures.danceability,
            energy: audioFeatures.energy,
            instrumentalness: audioFeatures.instrumentalness,
            liveness: audioFeatures.liveness,
            loudness: audioFeatures.loudness,
            speechiness: audioFeatures.speechiness,
            valence: audioFeatures.valence,
            tempo: audioFeatures.tempo,
            key: audioFeatures.key,
            mode: audioFeatures.mode,
            time_signature: audioFeatures.time_signature
          } : undefined
        };
      });
    
    return {
      playlist: {
        id: playlist.id,
        name: playlist.name,
        description: playlist.description || '',
        total_tracks: playlist.tracks.total,
        owner: playlist.owner.display_name
      },
      tracks: exportTracks,
      generated_at: new Date().toISOString()
    };
  }
  
  async generateExcelFile(exportData: ExportData): Promise<ArrayBuffer> {
    // Create a simple CSV-like Excel file (in production, you'd use a proper Excel library)
    // For Cloudflare Workers, we'll create a simple format that can be opened in Excel
    
    const headers = [
      'Track ID',
      'Track Name',
      'Artists',
      'Album',
      'Duration',
      'Popularity',
      'Explicit',
      'Release Date',
      'Spotify URI',
      'Added At',
      'Acousticness',
      'Danceability',
      'Energy',
      'Instrumentalness',
      'Liveness',
      'Loudness',
      'Speechiness',
      'Valence',
      'Tempo',
      'Key',
      'Mode',
      'Time Signature'
    ];
    
    // Create CSV content (Excel can open CSV files)
    let csvContent = headers.join(',') + '\n';
    
    // Add playlist info as first row
    csvContent += `"Playlist: ${exportData.playlist.name}",,,,"Total Tracks: ${exportData.playlist.total_tracks}",,,,"Owner: ${exportData.playlist.owner}",,,,,,,\n`;
    csvContent += '\n'; // Empty row
    
    // Add track data
    for (const track of exportData.tracks) {
      const row = [
        this.escapeCsvValue(track.id),
        this.escapeCsvValue(track.name),
        this.escapeCsvValue(track.artists),
        this.escapeCsvValue(track.album),
        this.escapeCsvValue(track.duration),
        track.popularity,
        track.explicit,
        this.escapeCsvValue(track.release_date),
        this.escapeCsvValue(track.uri),
        this.escapeCsvValue(track.added_at || ''),
        track.audio_features?.acousticness || '',
        track.audio_features?.danceability || '',
        track.audio_features?.energy || '',
        track.audio_features?.instrumentalness || '',
        track.audio_features?.liveness || '',
        track.audio_features?.loudness || '',
        track.audio_features?.speechiness || '',
        track.audio_features?.valence || '',
        track.audio_features?.tempo || '',
        track.audio_features?.key || '',
        track.audio_features?.mode || '',
        track.audio_features?.time_signature || ''
      ];
      
      csvContent += row.join(',') + '\n';
    }
    
    // Convert to ArrayBuffer
    const encoder = new TextEncoder();
    return encoder.encode(csvContent).buffer as ArrayBuffer;
  }
  
  private formatDuration(ms: number): string {
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
  
  private escapeCsvValue(value: string): string {
    if (value.includes(',') || value.includes('"') || value.includes('\n')) {
      return `"${value.replace(/"/g, '""')}"`;
    }
    return value;
  }
  
  async generateAdvancedExcelFile(exportData: ExportData): Promise<ArrayBuffer> {
    // This would be a more sophisticated Excel generator
    // For now, we'll return the CSV format
    return this.generateExcelFile(exportData);
  }
}

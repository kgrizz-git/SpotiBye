import { describe, it, expect } from 'vitest';
import { ExportService } from '../services/export';
import type { ExportData, ResumableExportAssemblyState } from '../services/export';

function decode(buffer: ArrayBuffer): any {
  return JSON.parse(new TextDecoder().decode(buffer));
}

const sampleExportData: ExportData = {
  playlist: {
    id: 'pl1',
    name: 'Road Trip',
    description: 'Songs for the highway',
    total_tracks: 2,
    owner: 'alice',
    followers: 42,
    url: 'https://open.spotify.com/playlist/pl1',
    cover_image_url: 'https://img/pl1.jpg',
  },
  tracks: [
    {
      Artist: 'Artist A',
      Album: 'Album A',
      Track: 'Track A',
      Duration: '3:21',
      'Spotify URL': 'https://open.spotify.com/track/a',
      Tempo: 120,
      Key: 'C',
      Danceability: 0.8,
      Energy: 0.9,
      Valence: 0.5,
      Acousticness: 0.1,
      Instrumentalness: 0,
      Liveness: 0.2,
      Speechiness: 0.05,
      Loudness: -5,
      'Time Signature': 4,
    },
  ],
  total_duration_ms: 201000,
  generated_at: new Date().toISOString(),
};

describe('ExportService JSON serialization', () => {
  it('generateCombinedJson produces nested per-playlist objects', () => {
    const service = new ExportService('token');
    const payload = decode(service.generateCombinedJson([sampleExportData]));

    expect(payload.playlist_count).toBe(1);
    expect(Array.isArray(payload.playlists)).toBe(true);

    const pl = payload.playlists[0];
    expect(pl.name).toBe('Road Trip');
    expect(pl.owner).toBe('alice');
    expect(pl.followers).toBe(42);
    expect(pl.url).toBe('https://open.spotify.com/playlist/pl1');
    expect(pl.total_tracks).toBe(2);
    expect(pl.tracks).toHaveLength(1);
    expect(pl.tracks[0].Artist).toBe('Artist A');
    expect(pl.tracks[0].Tempo).toBe(120);
  });

  it('generateCombinedJsonFromAssembly reconstructs tracks from worksheet rows', () => {
    const service = new ExportService('token');
    const assembly: ResumableExportAssemblyState = {
      summary_headers: ['Playlist Name', 'Owner', 'Track Count', 'Duration'],
      summary_rows: [],
      csv_chunks: [],
      next_assemble_index: 1,
      worksheets: [
        {
          sheet_name: 'Road Trip - alice',
          playlist_name: 'Road Trip',
          playlist_owner: 'alice',
          playlist_followers: 42,
          playlist_cover_image_url: 'https://img/pl1.jpg',
          playlist_description: 'Songs for the highway',
          playlist_url: 'https://open.spotify.com/playlist/pl1',
          total_duration: '3:21',
          headers: ['Artist', 'Track', 'Tempo'],
          rows: [
            ['Artist A', 'Track A', 120],
            ['Artist B', 'Track B', 90],
          ],
        },
      ],
    };

    const payload = decode(service.generateCombinedJsonFromAssembly(assembly));

    expect(payload.playlist_count).toBe(1);
    const pl = payload.playlists[0];
    expect(pl.name).toBe('Road Trip');
    expect(pl.total_tracks).toBe(2);
    expect(pl.tracks).toEqual([
      { Artist: 'Artist A', Track: 'Track A', Tempo: 120 },
      { Artist: 'Artist B', Track: 'Track B', Tempo: 90 },
    ]);
  });
});

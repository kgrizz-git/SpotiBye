/**
 * Shared ExportTrack / ExportData fixtures for export-format tests.
 */
import type { ExportData, ExportTrack } from '../../services/export-types';

export function makeExportTrack(overrides: Partial<ExportTrack> = {}): ExportTrack {
  return {
    Artist: 'Artist A',
    Album: 'Album A',
    Track: 'Track A',
    Duration: '3:21',
    'Spotify URL': 'https://open.spotify.com/track/a',
    Tempo: 120,
    Key: 'C major',
    Danceability: 0.8,
    Energy: 0.9,
    Valence: 0.5,
    Acousticness: 0.1,
    Instrumentalness: 0,
    Liveness: 0.2,
    Speechiness: 0.05,
    Loudness: -5,
    'Time Signature': 'N/A',
    ISRC: 'USUG12103683',
    ...overrides,
  };
}

export function makeExportData(overrides: Partial<ExportData> = {}): ExportData {
  return {
    playlist: {
      id: 'pl1',
      name: 'Road Trip',
      description: 'Songs for the highway',
      total_tracks: 1,
      owner: 'alice',
      followers: 42,
      url: 'https://open.spotify.com/playlist/pl1',
      cover_image_url: 'https://img/pl1.jpg',
    },
    tracks: [makeExportTrack()],
    total_duration_ms: 201000,
    generated_at: '2026-10-25T00:00:00Z',
    ...overrides,
  };
}

import { describe, it, expect } from 'vitest';
import { mapTrackForExport, calculateTotalDurationMs } from '../services/export-tracks';
import type { SpotifyAudioFeatures, SpotifyPlaylistTrackItem } from '../types/spotify';

function makeTrack(overrides: Partial<Parameters<typeof mapTrackForExport>[0]> = {}) {
  return {
    id: 't1',
    name: 'Test Track',
    artists: [
      { id: 'a1', name: 'Artist A', external_urls: { spotify: '' }, uri: '' },
      { id: 'a2', name: 'Artist B', external_urls: { spotify: '' }, uri: '' },
    ],
    album: { id: 'al1', name: 'Test Album', artists: [], images: [], release_date: '2020-01-01', total_tracks: 10, external_urls: { spotify: '' }, uri: '' },
    duration_ms: 201000,
    explicit: false,
    external_urls: { spotify: 'https://open.spotify.com/track/t1' },
    uri: 'spotify:track:t1',
    preview_url: null,
    ...overrides,
  };
}

const fullAudioFeatures: SpotifyAudioFeatures = {
  id: 'af1',
  tempo: 120.5,
  key: 0,   // C
  mode: 1,  // major
  danceability: 0.8,
  energy: 0.9,
  valence: 0.5,
  acousticness: 0.1,
  instrumentalness: 0.0,
  liveness: 0.2,
  speechiness: 0.05,
  loudness: -5.0,
  time_signature: 4,
};

describe('mapTrackForExport', () => {
  it('maps a track with full audio features', () => {
    const result = mapTrackForExport(makeTrack(), fullAudioFeatures);
    expect(result.Artist).toBe('Artist A, Artist B');
    expect(result.Album).toBe('Test Album');
    expect(result.Track).toBe('Test Track');
    expect(result['Spotify URL']).toBe('https://open.spotify.com/track/t1');
    expect(result.Tempo).toBe(120.5);
    expect(result.Key).toBe('C major');
    expect(result.Danceability).toBe(0.8);
    expect(result.Energy).toBe(0.9);
    expect(result['Time Signature']).toBe(4);
  });

  it('uses N/A for all audio feature fields when audioFeatures is null', () => {
    const result = mapTrackForExport(makeTrack(), null);
    expect(result.Tempo).toBe('N/A');
    expect(result.Key).toBe('N/A');
    expect(result.Danceability).toBe('N/A');
    expect(result.Energy).toBe('N/A');
    expect(result['Time Signature']).toBe('N/A');
  });

  it('uses N/A for missing audio feature fields (partial features)', () => {
    const partial = { ...fullAudioFeatures, key: 0, mode: 0, danceability: undefined } as unknown as SpotifyAudioFeatures;
    const result = mapTrackForExport(makeTrack(), partial);
    expect(result.Danceability).toBe('N/A');
  });

  it('formats key without mode when mode is not a known number', () => {
    const features = { ...fullAudioFeatures, mode: 99 };
    const result = mapTrackForExport(makeTrack(), features);
    // mode 99 is not in modeMap, so modeName is null, key has no mode suffix
    expect(result.Key).toBe('C');
  });

  it('uses N/A for key when key is out of range', () => {
    const features = { ...fullAudioFeatures, key: 12 };
    const result = mapTrackForExport(makeTrack(), features);
    expect(result.Key).toBe('N/A');
  });

  it('formats duration from track.duration_ms', () => {
    const result = mapTrackForExport(makeTrack({ duration_ms: 201000 }), null);
    expect(result.Duration).toBe('3:21');
  });
});

const makeItem = (durationMs: number | undefined): SpotifyPlaylistTrackItem => ({
  added_by: null,
  track: durationMs !== undefined
    ? {
        id: 't1', name: 'T', artists: [], album: { id: 'a', name: 'A', artists: [], images: [], release_date: '', total_tracks: 1, external_urls: { spotify: '' }, uri: '' },
        duration_ms: durationMs, explicit: false, external_urls: { spotify: '' }, uri: '', preview_url: null,
      }
    : undefined,
});

describe('calculateTotalDurationMs', () => {
  it('sums durations from valid items', () => {
    const items = [makeItem(100), makeItem(200)];
    expect(calculateTotalDurationMs(items)).toBe(300);
  });

  it('filters out items without a track', () => {
    const items = [makeItem(100), makeItem(undefined)];
    expect(calculateTotalDurationMs(items)).toBe(100);
  });

  it('returns 0 for empty array', () => {
    expect(calculateTotalDurationMs([])).toBe(0);
  });
});

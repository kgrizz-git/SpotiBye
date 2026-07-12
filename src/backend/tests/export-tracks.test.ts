import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  mapTrackForExport,
  calculateTotalDurationMs,
  loadAudioFeaturesMap,
  buildExportTracks,
  toExportFeatures,
  type ReccoBeatsExportFeatures,
} from '../services/export-tracks';
import type { SpotifyPlaylistTrackItem } from '../types/spotify';
import { CacheService } from '../services/cache';
import { audioFeaturesCacheKey } from '../services/reccobeats-track-cache';
import { kvNamespace } from './helpers/kv';

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

const fullAudioFeatures: ReccoBeatsExportFeatures = {
  tempo: 120.5,
  key: 0,
  mode: 1,
  danceability: 0.8,
  energy: 0.9,
  valence: 0.5,
  acousticness: 0.1,
  instrumentalness: 0.0,
  liveness: 0.2,
  speechiness: 0.05,
  loudness: -5.0,
};

const afRow = (spotifyId: string) => ({
  id: `recco-${spotifyId}`,
  href: `https://open.spotify.com/track/${spotifyId}`,
  acousticness: 0.1,
  danceability: 0.8,
  energy: 0.9,
  instrumentalness: 0.0,
  liveness: 0.2,
  loudness: -5.0,
  speechiness: 0.05,
  tempo: 120.5,
  valence: 0.5,
  key: 0,
  mode: 1,
});

describe('mapTrackForExport', () => {
  it('maps a track with full ReccoBeats export features', () => {
    const result = mapTrackForExport(makeTrack(), fullAudioFeatures);
    expect(result.Artist).toBe('Artist A, Artist B');
    expect(result.Album).toBe('Test Album');
    expect(result.Track).toBe('Test Track');
    expect(result['Spotify URL']).toBe('https://open.spotify.com/track/t1');
    expect(result.Tempo).toBe(120.5);
    expect(result.Key).toBe('C major');
    expect(result.Danceability).toBe(0.8);
    expect(result.Energy).toBe(0.9);
  });

  it('always sets Time Signature to N/A (ReccoBeats has no time_signature)', () => {
    const result = mapTrackForExport(makeTrack(), fullAudioFeatures);
    expect(result['Time Signature']).toBe('N/A');
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
    const partial = { ...fullAudioFeatures, danceability: undefined };
    const result = mapTrackForExport(makeTrack(), partial);
    expect(result.Danceability).toBe('N/A');
  });

  it('formats key without mode when mode is not a known number', () => {
    const features = { ...fullAudioFeatures, mode: 99 };
    const result = mapTrackForExport(makeTrack(), features);
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

describe('toExportFeatures', () => {
  it('maps ReccoBeats row fields without time_signature', () => {
    const row = afRow('track1');
    const mapped = toExportFeatures(row);
    expect(mapped.tempo).toBe(120.5);
    expect(mapped.danceability).toBe(0.8);
    expect(mapped).not.toHaveProperty('time_signature');
  });
});

describe('loadAudioFeaturesMap', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('returns empty map when enrichment disabled', async () => {
    const cache = new CacheService(kvNamespace());
    const result = await loadAudioFeaturesMap(['t1'], false, cache);
    expect(result.size).toBe(0);
  });

  it('miss-fills via ReccoBeats when cache is cold', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ content: [afRow('track1')] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const cache = new CacheService(kvNamespace());
    const result = await loadAudioFeaturesMap(['track1'], true, cache);

    expect(fetchMock).toHaveBeenCalled();
    expect(result.get('track1')?.danceability).toBe(0.8);
  });

  it('reuses warm global cache without HTTP', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const cache = new CacheService(
      kvNamespace({
        [audioFeaturesCacheKey('track1')]: afRow('track1'),
      }),
    );
    const result = await loadAudioFeaturesMap(['track1'], true, cache);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.get('track1')?.tempo).toBe(120.5);
  });
});

describe('buildExportTracks', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const makeItem = (id: string): SpotifyPlaylistTrackItem => ({
    added_by: null,
    track: makeTrack({ id }),
  });

  it('populates numeric enrichment from per-track cache without prior analysis', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ content: [afRow('shared-track')] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const cache = new CacheService(kvNamespace());
    const tracks = await buildExportTracks([makeItem('shared-track')], true, cache);

    expect(tracks).toHaveLength(1);
    expect(tracks[0].Danceability).toBe(0.8);
    expect(tracks[0].Energy).toBe(0.9);
    expect(tracks[0]['Time Signature']).toBe('N/A');
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

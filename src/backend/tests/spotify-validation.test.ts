import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { SpotifyService } from '../services/spotify';
import { parsePlaylistItems } from '../types/spotify-api';

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

const audioFeaturesResponse = (id: string) => ({
  id,
  acousticness: 0.1,
  danceability: 0.5,
  energy: 0.6,
  instrumentalness: 0.0,
  liveness: 0.1,
  loudness: -10,
  speechiness: 0.05,
  valence: 0.5,
  tempo: 120,
  mode: 1,
  key: 0,
  time_signature: 4,
});

describe('parsePlaylistItems', () => {
  it('drops items missing a string id and logs a warning', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const items = [
      { id: 'good', name: 'Valid' },
      { name: 'Missing id' },
      { id: 'missing-name' },
      null,
      { id: 'good2', name: 'Also valid' },
    ];

    const result = parsePlaylistItems(items, 'test');

    expect(result).toHaveLength(2);
    expect(result.map((p) => p.id)).toEqual(['good', 'good2']);
    expect(warn).toHaveBeenCalled();
  });

  it('returns an empty array when given a non-array', () => {
    const result = parsePlaylistItems(null, 'test');
    expect(result).toEqual([]);
  });

  it('returns an empty array when all items are malformed (does not throw)', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const result = parsePlaylistItems([null, {}, { name: 'no id' }], 'test');
    expect(result).toEqual([]);
    expect(warn).toHaveBeenCalled();
  });

  it('returns the full array when all items are valid', () => {
    const items = [
      { id: '1', name: 'A' },
      { id: '2', name: 'B' },
    ];
    expect(parsePlaylistItems(items, 'test')).toHaveLength(2);
  });
});

describe('SpotifyService typed wrappers (BM-6)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('getAudioFeatures throws when the response is missing a string id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ id: 123, danceability: 0.5 })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');

    await expect(service.getAudioFeatures('track-1')).rejects.toThrow(
      /Invalid audio features shape/
    );
  });

  it('getAudioFeatures returns the parsed object on a valid response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(audioFeaturesResponse('track-1'))
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');
    const features = await service.getAudioFeatures('track-1');

    expect(features.id).toBe('track-1');
    expect(features.tempo).toBe(120);
  });

  it('getArtist throws when the response is missing a string id or name', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ id: 'artist-1', name: 42 })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');

    await expect(service.getArtist('artist-1')).rejects.toThrow(
      /Invalid artist shape/
    );
  });

  it('getArtist returns the parsed object on a valid response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: 'artist-1',
        name: 'Artist',
        genres: ['pop'],
        popularity: 50,
        external_urls: { spotify: 'https://open.spotify.com/artist/artist-1' },
        uri: 'spotify:artist:artist-1',
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');
    const artist = await service.getArtist('artist-1');

    expect(artist.id).toBe('artist-1');
    expect(artist.name).toBe('Artist');
  });

  it('getMultipleAudioFeatures throws when the response is not an array', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ audio_features: 'not-an-array' })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');

    await expect(
      service.getMultipleAudioFeatures(['track-1'])
    ).rejects.toThrow(/Invalid audio_features list/);
  });

  it('getMultipleAudioFeatures preserves null entries in the array', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        audio_features: [audioFeaturesResponse('track-1'), null],
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new SpotifyService('access-token');
    const features = await service.getMultipleAudioFeatures(['track-1', 'track-2']);

    expect(features).toHaveLength(2);
    expect(features[0]?.id).toBe('track-1');
    expect(features[1]).toBeNull();
  });
});

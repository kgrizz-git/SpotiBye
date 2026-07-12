/**
 * Unit tests for ReccoBeats href parsing and content→Map mapping.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  isReccoBeatsAudioFeature,
  isReccoBeatsTrackMetadata,
  mapReccoBeatsContentBySpotifyId,
  parseSpotifyTrackIdFromHref,
} from '../utils/reccobeats-helpers';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('parseSpotifyTrackIdFromHref', () => {
  it('parses open.spotify.com/track/{id}', () => {
    expect(parseSpotifyTrackIdFromHref('https://open.spotify.com/track/01K4zKU104LyJ8gMb7227B'))
      .toBe('01K4zKU104LyJ8gMb7227B');
  });

  it('strips query and hash', () => {
    expect(
      parseSpotifyTrackIdFromHref(
        'https://open.spotify.com/track/01K4zKU104LyJ8gMb7227B?si=abc#section'
      )
    ).toBe('01K4zKU104LyJ8gMb7227B');
  });

  it('accepts spotify:track:{id} defensively', () => {
    expect(parseSpotifyTrackIdFromHref('spotify:track/01K4zKU104LyJ8gMb7227B')).toBeNull();
    expect(parseSpotifyTrackIdFromHref('spotify:track:01K4zKU104LyJ8gMb7227B'))
      .toBe('01K4zKU104LyJ8gMb7227B');
  });

  it('returns null for missing or unparseable href', () => {
    expect(parseSpotifyTrackIdFromHref(undefined)).toBeNull();
    expect(parseSpotifyTrackIdFromHref('')).toBeNull();
    expect(parseSpotifyTrackIdFromHref('https://open.spotify.com/album/xyz')).toBeNull();
  });
});

describe('mapReccoBeatsContentBySpotifyId', () => {
  const baseAf = {
    id: 'recco-uuid',
    acousticness: 0.1,
    danceability: 0.2,
    energy: 0.3,
    instrumentalness: 0.4,
    liveness: 0.5,
    loudness: -5,
    speechiness: 0.6,
    tempo: 120,
    valence: 0.7,
  };

  it('maps known + missing IDs via href and skips href-less rows without failing the batch', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    const { bySpotifyId, unparseableCount } = mapReccoBeatsContentBySpotifyId(
      [
        { ...baseAf, id: 'r1', href: 'https://open.spotify.com/track/track1' },
        { ...baseAf, id: 'r-bad' }, // no href
        { ...baseAf, id: 'r2', href: 'https://open.spotify.com/track/track2' },
        { not: 'a feature' },
      ],
      isReccoBeatsAudioFeature,
      'audio-features'
    );

    expect([...bySpotifyId.keys()].sort()).toEqual(['track1', 'track2']);
    expect(unparseableCount).toBe(2);
  });

  it('accepts optional href on metadata rows and optional boundary fields', () => {
    const row = {
      id: 'm1',
      href: 'https://open.spotify.com/track/track1',
      trackTitle: 'T',
      artists: [{ id: 'a1', name: 'A', href: 'https://open.spotify.com/artist/a1' }],
      durationMs: 1000,
      ean: 'e',
      upc: 'u',
      availableCountries: ['US'],
    };
    expect(isReccoBeatsTrackMetadata(row)).toBe(true);
    expect(isReccoBeatsTrackMetadata({ ...row, href: undefined })).toBe(true);
  });
});

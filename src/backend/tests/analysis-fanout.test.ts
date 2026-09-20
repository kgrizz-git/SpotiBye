import { describe, it, expect } from 'vitest';
import {
  FANOUT_ARTIST_THRESHOLD,
  FANOUT_SUBREQUEST_BUDGET,
  chunkResultKey,
  chunkTrackIds,
  estimateSubrequests,
  fanoutTracksKey,
  mergePartials,
  resolveMergedSchemaVersion,
  shouldFanOut,
  type AnalysisChunkPartial,
  type TrackArtistIndex,
} from '../services/analysis-fanout';

function index(trackId: string, artistIds: string[]): TrackArtistIndex {
  return { trackId, artistIds };
}

function partial(chunkId: string, overrides: Partial<AnalysisChunkPartial> = {}): AnalysisChunkPartial {
  return {
    chunk_id: chunkId,
    track_ids: [],
    artistData: [],
    audioFeatures: [],
    trackMetadata: [],
    errors: [],
    audioFeaturesResolvedCount: 0,
    trackMetadataResolvedCount: 0,
    enrichmentResolvedTrackCount: 0,
    schema_version: '1.1',
    ...overrides,
  };
}

describe('estimateSubrequests', () => {
  it('returns 0 for empty input', () => {
    expect(estimateSubrequests(0, 0)).toBe(0);
  });

  it('keeps a tiny playlist under budget', () => {
    expect(estimateSubrequests(5, 3)).toBeLessThanOrEqual(FANOUT_SUBREQUEST_BUDGET);
  });

  it('exceeds budget for NPR-scale playlists', () => {
    expect(estimateSubrequests(100, 40)).toBeGreaterThan(FANOUT_SUBREQUEST_BUDGET);
  });

  it('exceeds budget even for 20 cold tracks (worst-case KV accounting)', () => {
    // This is the live failure mode: worst-case KV reads/writes alone
    // exceed the per-invocation budget, so mid-size playlists fan out too.
    expect(estimateSubrequests(20, 10)).toBeGreaterThan(FANOUT_SUBREQUEST_BUDGET);
  });
});

describe('shouldFanOut', () => {
  it('keeps tiny playlists on the single-message path', () => {
    expect(shouldFanOut(5, 3)).toBe(false);
  });

  it('fans out past the artist threshold even for few tracks', () => {
    expect(shouldFanOut(10, FANOUT_ARTIST_THRESHOLD + 1)).toBe(true);
  });

  it('fans out many tracks with few artists', () => {
    expect(shouldFanOut(200, 5)).toBe(true);
  });
});

describe('chunkTrackIds', () => {
  it('returns no chunks for no tracks', () => {
    expect(chunkTrackIds([])).toEqual([]);
  });

  it('covers every track exactly once within budget and artist cap', () => {
    const tracks = Array.from({ length: 60 }, (_, i) =>
      index(`t${i}`, [`a${Math.floor(i / 3)}`])
    );
    const chunks = chunkTrackIds(tracks);
    const flat = chunks.flat().sort();
    expect(flat).toEqual(tracks.map((t) => t.trackId).sort());
    expect(new Set(flat).size).toBe(tracks.length);
    for (const chunk of chunks) {
      const artists = new Set(
        chunk.flatMap((id) => tracks.find((t) => t.trackId === id)?.artistIds ?? [])
      );
      expect(artists.size).toBeLessThanOrEqual(FANOUT_ARTIST_THRESHOLD);
      expect(estimateSubrequests(chunk.length, artists.size)).toBeLessThanOrEqual(
        FANOUT_SUBREQUEST_BUDGET
      );
    }
  });

  it('splits when a chunk would exceed the artist cap', () => {
    const tracks = Array.from({ length: 45 }, (_, i) => index(`t${i}`, [`a${i}`]));
    const chunks = chunkTrackIds(tracks);
    expect(chunks.length).toBeGreaterThan(1);
    for (const chunk of chunks) {
      const artists = new Set(
        chunk.flatMap((id) => tracks.find((t) => t.trackId === id)?.artistIds ?? [])
      );
      expect(artists.size).toBeLessThanOrEqual(FANOUT_ARTIST_THRESHOLD);
    }
  });

  it('gives an over-cap single track a chunk to itself', () => {
    const tracks = [index('t0', Array.from({ length: 50 }, (_, i) => `a${i}`))];
    expect(chunkTrackIds(tracks)).toEqual([['t0']]);
  });
});

describe('mergePartials', () => {
  it('concats rows and errors, dedupes artists, sums counters', () => {
    const merged = mergePartials([
      partial('c0', {
        track_ids: ['t1'],
        artistData: [{ id: 'a1' } as never, { id: 'a2' } as never],
        audioFeaturesResolvedCount: 1,
        errors: [{ source: 's', message: 'm' }],
        schema_version: '1.1',
      }),
      partial('c1', {
        track_ids: ['t2'],
        artistData: [{ id: 'a2' } as never, { id: 'a3' } as never],
        audioFeaturesResolvedCount: 2,
        schema_version: '1.1',
      }),
    ]);
    expect(merged.trackIds).toEqual(['t1', 't2']);
    expect(merged.artistData.map((a) => a.id).sort()).toEqual(['a1', 'a2', 'a3']);
    expect(merged.audioFeaturesResolvedCount).toBe(3);
    expect(merged.errors).toHaveLength(1);
    expect(merged.schemaVersions).toEqual(['1.1', '1.1']);
  });
});

describe('resolveMergedSchemaVersion', () => {
  it('returns the uniform version', () => {
    expect(resolveMergedSchemaVersion(['1.1', '1.1'])).toBe('1.1');
  });

  it('throws on mixed versions', () => {
    expect(() => resolveMergedSchemaVersion(['1.0', '1.1'])).toThrow(/differ/);
  });

  it('returns unknown for no partials', () => {
    expect(resolveMergedSchemaVersion([])).toBe('unknown');
  });
});

describe('fan-out key builders', () => {
  it('namespaces chunk results by playlist, user, job, and chunk', () => {
    expect(chunkResultKey('p', 'u', 'j', 'c0')).toBe('analysis:p:u:chunks:j:c0');
  });

  it('namespaces the track snapshot by playlist, user, and job', () => {
    expect(fanoutTracksKey('p', 'u', 'j')).toBe('analysis:p:u:fandata:j');
  });
});

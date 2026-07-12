/**
 * Tests for global per-track ReccoBeats cache resolution.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CacheService } from '../services/cache';
import {
  ReccoBeatsTrackCacheService,
  absentAudioFeaturesCacheKey,
  audioFeaturesCacheKey,
  clearReccoBeatsTrackCacheInFlightForTests,
} from '../services/reccobeats-track-cache';
import { kvNamespace } from './helpers/kv';

const afRow = (spotifyId: string) => ({
  id: `recco-${spotifyId}`,
  href: `https://open.spotify.com/track/${spotifyId}`,
  acousticness: 0.1,
  danceability: 0.2,
  energy: 0.3,
  instrumentalness: 0.4,
  liveness: 0.5,
  loudness: -5,
  speechiness: 0.6,
  tempo: 120,
  valence: 0.7,
});

beforeEach(() => {
  clearReccoBeatsTrackCacheInFlightForTests();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  clearReccoBeatsTrackCacheInFlightForTests();
});

describe('ReccoBeatsTrackCacheService', () => {
  it('cache hit skips HTTP and skips absent get', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const cacheKv = kvNamespace({
      [audioFeaturesCacheKey('track1')]: afRow('track1'),
    });
    const getSpy = cacheKv.get as ReturnType<typeof vi.fn>;
    const cache = new CacheService(cacheKv);
    const service = new ReccoBeatsTrackCacheService(cache);

    const result = await service.resolveAudioFeatures(['track1']);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.bySpotifyId.has('track1')).toBe(true);
    expect(result.counters.negativeSkipped).toBe(0);
    // Two-stage: only positive key read on warm hit.
    expect(getSpy.mock.calls.map((c) => c[0])).toEqual([audioFeaturesCacheKey('track1')]);
  });

  it('writes per-endpoint absent for omitted IDs and reuses across resolve calls', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ content: [afRow('track1')] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const cacheKv = kvNamespace();
    const cache = new CacheService(cacheKv);
    const service = new ReccoBeatsTrackCacheService(cache);

    const first = await service.resolveAudioFeatures(['track1', 'missing1']);
    expect(first.bySpotifyId.has('track1')).toBe(true);
    expect(first.counters.absentIds).toContain('missing1');
    expect(first.counters.resolvedIds.sort()).toEqual(['missing1', 'track1']);

    clearReccoBeatsTrackCacheInFlightForTests();
    const second = await service.resolveAudioFeatures(['track1', 'missing1']);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(second.counters.negativeSkipped).toBe(1);
    expect(second.bySpotifyId.has('track1')).toBe(true);
  });

  it('force clears positive and absent keys before refetch', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ content: [afRow('track1')] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const cacheKv = kvNamespace({
      [audioFeaturesCacheKey('track1')]: afRow('track1'),
      [absentAudioFeaturesCacheKey('missing1')]: {
        absent: true,
        cached_at: '2026-07-01T00:00:00.000Z',
      },
    });
    const cache = new CacheService(cacheKv);
    const service = new ReccoBeatsTrackCacheService(cache);

    await service.resolveAudioFeatures(['track1', 'missing1'], { force: true });

    expect(cacheKv.delete).toHaveBeenCalledWith(audioFeaturesCacheKey('track1'));
    expect(cacheKv.delete).toHaveBeenCalledWith(absentAudioFeaturesCacheKey('missing1'));
    expect(fetchMock).toHaveBeenCalled();
  });

  it('one malformed content row does not fail the batch', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          content: [
            afRow('track1'),
            { id: 'bad', href: 'https://open.spotify.com/track/track2' }, // missing AF numbers
          ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );
    vi.stubGlobal('fetch', fetchMock);

    const cache = new CacheService(kvNamespace());
    const service = new ReccoBeatsTrackCacheService(cache);
    const result = await service.resolveAudioFeatures(['track1', 'track2']);

    expect(result.bySpotifyId.has('track1')).toBe(true);
    // Malformed row → unparseable; with unparseable > 0, track2 is not absent-poisoned.
    expect(result.counters.unparseableCount).toBeGreaterThan(0);
    expect(result.counters.absentIds).not.toContain('track2');
    expect(result.counters.unresolvedIds).toContain('track2');
  });

  it('coalesces concurrent force resolves for the same ID set', async () => {
    let resolveFetch!: (value: Response) => void;
    let fetchStarted!: () => void;
    const fetchStartedPromise = new Promise<void>((resolve) => {
      fetchStarted = resolve;
    });

    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
          fetchStarted();
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    const cache = new CacheService(kvNamespace());
    const service = new ReccoBeatsTrackCacheService(cache);

    const p1 = service.resolveAudioFeatures(['track1'], { force: true });
    const p2 = service.resolveAudioFeatures(['track1'], { force: true });

    await fetchStartedPromise;
    resolveFetch(
      new Response(JSON.stringify({ content: [afRow('track1')] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const [r1, r2] = await Promise.all([p1, p2]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(r1.bySpotifyId.has('track1')).toBe(true);
    expect(r2.bySpotifyId.has('track1')).toBe(true);
  });

  it('respects batch size of 30', async () => {
    const ids = Array.from({ length: 31 }, (_, i) => `t${i}`);
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      const batchIds = url.searchParams.getAll('ids');
      expect(batchIds.length).toBeLessThanOrEqual(30);
      return new Response(
        JSON.stringify({
          content: batchIds.map((id) => afRow(id)),
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    const cache = new CacheService(kvNamespace());
    const service = new ReccoBeatsTrackCacheService(cache);
    const result = await service.resolveAudioFeatures(ids);

    expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(result.bySpotifyId.size).toBe(31);
  });
});

describe('CacheService.clearPrefixPaginated', () => {
  it('pages through list cursors until complete', async () => {
    const deleted: string[] = [];
    const kv = {
      get: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(async (key: string) => {
        deleted.push(key);
      }),
      list: vi.fn(async (opts: { prefix: string; cursor?: string }) => {
        if (!opts.cursor) {
          return {
            keys: [{ name: `${opts.prefix}a` }],
            list_complete: false,
            cursor: 'page2',
          };
        }
        return {
          keys: [{ name: `${opts.prefix}b` }],
          list_complete: true,
        };
      }),
    } as unknown as KVNamespace;

    const cache = new CacheService(kv);
    await cache.clearPrefixPaginated('global:reccobeats:');

    expect(deleted).toEqual(['global:reccobeats:a', 'global:reccobeats:b']);
    expect(kv.list).toHaveBeenCalledTimes(2);
  });
});

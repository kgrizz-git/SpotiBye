/**
 * Validates that the live analysis response actually produced by
 * `AnalysisJobService.process` matches `docs/openapi.yaml`'s documented
 * `AnalysisResultsResponse` — a lighter-weight complement to
 * `analysis.test.ts` / `api-coverage.test.ts`, not a replacement.
 *
 * Rigor level (intentionally the lighter, less-fragile check): assert the
 * spec's example key-paths exist on the live response (example ⊆ response),
 * plus assert `AnalysisResult`'s `required` field names are all present.
 * Does not attempt full JSON-Schema `$ref` resolution/type validation.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { load } from 'js-yaml';
import { AnalysisJobService } from '../services/analysis-job';
import { SpotifyService } from '../services/spotify';
import { kvNamespace, envWithKv } from './helpers/kv';
import type { AnalysisQueueMessage } from '../types/analysis-queue';
import type { SpotifyTrack } from '../types/spotify';

interface OpenApiDocument {
  paths: Record<string, unknown>;
  components: {
    schemas: Record<string, { required?: string[]; properties?: Record<string, unknown> }>;
  };
}

function loadOpenApiSpec(): OpenApiDocument {
  const specPath = resolve(__dirname, '../docs/openapi.yaml');
  return load(readFileSync(specPath, 'utf8')) as OpenApiDocument;
}

/**
 * `additionalProperties`-style dynamic maps in the schema (keyed by
 * data-dependent values like genre name or pitch class, not a fixed field
 * set) — checked for object-ness only, not recursed into by key name, since
 * the example's specific keys ("Pop", "C", …) won't match a differently
 * seeded live fixture.
 */
const DYNAMIC_MAP_FIELDS = new Set(['genre_distribution', 'key_percentages']);

/** Recursively asserts every key in `example` also exists on `actual` (presence-only, not type/value checked). */
function assertExampleKeysExist(example: unknown, actual: unknown, path: string): void {
  if (Array.isArray(example)) {
    expect(Array.isArray(actual), `expected array at ${path}`).toBe(true);
    return;
  }
  if (example !== null && typeof example === 'object') {
    expect(actual !== null && typeof actual === 'object', `expected object at ${path}`).toBe(true);
    const fieldName = path.split('.').at(-1);
    if (fieldName && DYNAMIC_MAP_FIELDS.has(fieldName)) {
      return;
    }
    for (const [key, value] of Object.entries(example as Record<string, unknown>)) {
      const nextPath = `${path}.${key}`;
      expect(actual, `missing key at ${nextPath}`).toHaveProperty(key);
      assertExampleKeysExist(value, (actual as Record<string, unknown>)[key], nextPath);
    }
  }
}

const track = (id: string): SpotifyTrack => ({
  id,
  name: `Track ${id}`,
  artists: [
    {
      id: `artist-${id}`,
      name: `Artist ${id}`,
      external_urls: { spotify: `https://open.spotify.com/artist/artist-${id}` },
      uri: `spotify:artist:artist-${id}`,
    },
  ],
  album: {
    id: `album-${id}`,
    name: `Album ${id}`,
    artists: [],
    images: [],
    release_date: '2026-01-01',
    total_tracks: 1,
    external_urls: { spotify: `https://open.spotify.com/album/${id}` },
    uri: `spotify:album:${id}`,
  },
  duration_ms: 200000,
  explicit: false,
  popularity: 50,
  external_urls: { spotify: `https://open.spotify.com/track/${id}` },
  uri: `spotify:track:${id}`,
  preview_url: null,
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('openapi.yaml AnalysisResultsResponse reconciliation', () => {
  it('the live analysis result contains every key-path from the spec example, and every required field', async () => {
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 2,
      rawCount: 2,
      items: [
        { added_by: null, track: track('track1') },
        { added_by: null, track: track('track2') },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([]);

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/v1/track') {
        return new Response(
          JSON.stringify({
            content: [
              {
                id: 'm1', trackTitle: 'Track 1',
                artists: [{ id: 'a1', name: 'Artist 1', href: 'https://open.spotify.com/artist/artist-track1' }],
                durationMs: 200000, isrc: 'ISRC1', popularity: 55,
              },
              {
                id: 'm2', trackTitle: 'Track 2',
                artists: [{ id: 'a2', name: 'Artist 2', href: 'https://open.spotify.com/artist/artist-track2' }],
                durationMs: 200000, popularity: 75,
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }
      return new Response(
        JSON.stringify({
          content: [
            {
              id: 'r1', href: 'https://open.spotify.com/track/track1',
              acousticness: 0.1, danceability: 0.2, energy: 0.3, instrumentalness: 0.1,
              liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.4,
              key: 0, mode: 1, isrc: 'ISRC1',
            },
            {
              id: 'r2', href: 'https://open.spotify.com/track/track2',
              acousticness: 0.2, danceability: 0.3, energy: 0.4, instrumentalness: 0.2,
              liveness: 0.2, loudness: -6, speechiness: 0.2, tempo: 110, valence: 0.5,
              key: 0, mode: 1,
            },
          ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    const statusKey = 'analysis:playlist1:user1:status';
    const resultsKey = 'analysis:playlist1:user1:results';
    const cacheKv = kvNamespace({
      [statusKey]: {
        job_id: 'job1',
        playlist_id: 'playlist1',
        user_id: 'user1',
        status: 'queued',
        progress: 0,
      },
    });
    const sessionsKv = kvNamespace({
      session1: {
        user_id: 'user1',
        access_token: 'token',
        refresh_token: 'refresh',
        expires_at: Date.now() + 3_600_000,
      },
    });

    const message: AnalysisQueueMessage = {
      job_id: 'job1',
      playlist_id: 'playlist1',
      user_id: 'user1',
      session_id: 'session1',
      enqueued_at: new Date().toISOString(),
      attempt: 0,
    };

    const service = new AnalysisJobService(envWithKv(cacheKv, sessionsKv));
    await service.process(message);

    const resultsRaw = await cacheKv.get(resultsKey);
    const liveResult = JSON.parse(resultsRaw as string) as Record<string, unknown>;

    const spec = loadOpenApiSpec();
    const resultsPath = spec.paths['/analysis/playlist/{id}/results'] as {
      get: { responses: { '200': { content: { 'application/json': { examples: { success: { value: { data: unknown } } } } } } } };
    };
    const exampleData = resultsPath.get.responses['200'].content['application/json'].examples.success.value.data;

    assertExampleKeysExist(exampleData, liveResult, 'data');

    const analysisResultSchema = spec.components.schemas.AnalysisResult;
    expect(analysisResultSchema.required).toBeDefined();
    for (const field of analysisResultSchema.required ?? []) {
      expect(liveResult, `AnalysisResult.required field "${field}" missing from live response`).toHaveProperty(field);
    }
  });
});

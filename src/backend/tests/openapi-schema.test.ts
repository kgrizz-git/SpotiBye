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
import { runAnalysisPipeline } from './helpers/analysis-job';
import { createSpotifyTrack, defaultReccoBeatsTrackMetadata } from './helpers/spotify';

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

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('openapi.yaml AnalysisResultsResponse reconciliation', () => {
  it('the live analysis result contains every key-path from the spec example, and every required field', async () => {
    const statusKey = 'analysis:playlist1:user1:status';
    const { resultsRaw } = await runAnalysisPipeline({
      tracks: [
        createSpotifyTrack({ id: 'track1' }),
        createSpotifyTrack({ id: 'track2' }),
      ],
      artists: [],
      trackMetadata: defaultReccoBeatsTrackMetadata(),
      cacheSeed: {
        [statusKey]: {
          job_id: 'job1',
          playlist_id: 'playlist1',
          user_id: 'user1',
          status: 'queued',
          progress: 0,
        },
      },
    });

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

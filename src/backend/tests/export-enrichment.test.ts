/**
 * B4 export enrichment: format/enrichment cache keys and stale plain vs enriched separation.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { exportRoutes } from '../routes/export';
import type { Env } from '../types/env';
import { createTestEnv } from './helpers/env';
import {
  buildSingleExportKey,
  buildSingleExportLatestKey,
} from '../routes/export/helpers/cache-keys';

const mockExportData = {
  playlist: {
    id: 'playlist1',
    name: 'Test Playlist',
    description: '',
    total_tracks: 1,
    owner: 'Test User',
    followers: 0,
    url: '',
  },
  tracks: [
    {
      Artist: 'A',
      Album: 'Al',
      Track: 'T',
      Duration: '3:00',
      'Spotify URL': '',
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
    },
  ],
  total_duration_ms: 180000,
  generated_at: new Date().toISOString(),
};

vi.mock('../services/export', () => ({
  ExportService: class {
    constructor(_token: string, _cache?: unknown) {}

    async generatePlaylistExport() {
      return mockExportData;
    }
  },
  ResumableExportConflictError: class extends Error {},
}));

vi.mock('../middleware/auth', () => ({
  authMiddleware: vi.fn().mockImplementation((c, next) => {
    c.set('user', {
      id: 'test-user-id',
      email: 'test@example.com',
      name: 'Test User',
    });
    c.set('access_token', 'test-access-token');
    return next();
  }),
}));

describe('export enrichment cache keys (B4)', () => {
  it('distinguishes enriched vs plain and format in cache keys', () => {
    expect(buildSingleExportKey('pl1', 'u1', { format: 'xlsx', includeEnrichment: true }))
      .toBe('export:pl1:u1:xlsx:enriched');
    expect(buildSingleExportKey('pl1', 'u1', { format: 'csv', includeEnrichment: false }))
      .toBe('export:pl1:u1:csv:plain');
  });
});

describe('POST /export/playlist/:id enriched cache', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;
  let cacheStore: Map<string, string>;

  beforeEach(() => {
    cacheStore = new Map<string, string>();
    app = new Hono<{ Bindings: Env }>();
    app.route('/export', exportRoutes);

    mockEnv = {
      ...createTestEnv(),
      CACHE_KV: {
        get: vi.fn().mockImplementation(async (key: string) => cacheStore.get(key) ?? null),
        put: vi.fn().mockImplementation(async (key: string, value: string) => {
          cacheStore.set(key, value);
        }),
        getWithMetadata: vi.fn().mockResolvedValue({ value: null, metadata: null }),
        delete: vi.fn().mockImplementation(async (key: string) => {
          cacheStore.delete(key);
        }),
        list: vi.fn().mockResolvedValue({ keys: [], list_complete: true, cursor: undefined }),
      } as any,
      SESSIONS_KV: {
        get: vi.fn().mockResolvedValue(JSON.stringify({
          user_id: 'test-user-id',
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token',
          expires_at: Date.now() + 3600000,
        })),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined),
      } as any,
    };
  });

  it('stores enriched export under format-specific key and latest pointer', async () => {
    const response = await app.request(
      new Request('http://localhost/export/playlist/playlist1', {
        method: 'POST',
        headers: {
          Authorization: 'Bearer test-jwt-token',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ format: 'xlsx', include_audio_features: true }),
      }),
      undefined,
      mockEnv,
    );

    expect(response.status).toBe(200);

    const enrichedKey = buildSingleExportKey('playlist1', 'test-user-id', {
      format: 'xlsx',
      includeEnrichment: true,
    });
    const status = JSON.parse(cacheStore.get(enrichedKey) || '{}');
    expect(status.status).toBe('completed');
    expect(status.include_audio_features).toBe(true);

    const latest = JSON.parse(
      cacheStore.get(buildSingleExportLatestKey('playlist1', 'test-user-id')) || '{}',
    );
    expect(latest.includeEnrichment).toBe(true);
  });

  it('does not short-circuit to stale plain export when requesting enriched export', async () => {
    const plainKey = buildSingleExportKey('playlist1', 'test-user-id', {
      format: 'xlsx',
      includeEnrichment: false,
    });
    cacheStore.set(
      plainKey,
      JSON.stringify({
        status: 'completed',
        playlist_id: 'playlist1',
        include_audio_features: false,
        file_format: 'xlsx',
      }),
    );

    const response = await app.request(
      new Request('http://localhost/export/playlist/playlist1', {
        method: 'POST',
        headers: {
          Authorization: 'Bearer test-jwt-token',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ format: 'xlsx', include_audio_features: true }),
      }),
      undefined,
      mockEnv,
    );

    expect(response.status).toBe(200);

    const enrichedKey = buildSingleExportKey('playlist1', 'test-user-id', {
      format: 'xlsx',
      includeEnrichment: true,
    });
    const enrichedStatus = JSON.parse(cacheStore.get(enrichedKey) || '{}');
    expect(enrichedStatus.include_audio_features).toBe(true);

    const plainStatus = JSON.parse(cacheStore.get(plainKey) || '{}');
    expect(plainStatus.include_audio_features).toBe(false);
  });
});

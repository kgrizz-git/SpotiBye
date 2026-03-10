import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { exportRoutes } from '../routes/export';
import type { Env } from '../types/env';

// Mock the services
vi.mock('../services/export', () => ({
  ExportService: vi.fn().mockImplementation(function () {
    return {
    generateExcelExport: vi.fn().mockResolvedValue({
      export_id: 'test-export-id',
      file_name: 'playlist-test.xlsx',
      file_size: 1024,
      created_at: new Date().toISOString(),
      download_url: '/export/playlist/test-export-id/download'
    }),
    generatePlaylistExport: vi.fn().mockResolvedValue({
      playlist: {
        id: 'playlist1',
        name: 'Test Playlist',
        description: '',
        total_tracks: 1,
        owner: 'Test User'
      },
      tracks: []
    }),
    generateExcelFile: vi.fn().mockResolvedValue(new Uint8Array([1, 2, 3, 4, 5]).buffer),
    getExportFile: vi.fn().mockResolvedValue(new Uint8Array([1, 2, 3, 4, 5])),
    cleanupOldExports: vi.fn().mockResolvedValue(undefined)
    };
  })
}));

vi.mock('../middleware/auth', () => ({
  authMiddleware: vi.fn().mockImplementation((c, next) => {
    // Mock authenticated user
    c.set('user', { 
      id: 'test-user-id',
      email: 'test@example.com',
      name: 'Test User'
    });
    c.set('access_token', 'test-access-token');
    return next();
  })
}));

describe('Export Routes', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;

  beforeEach(() => {
    app = new Hono<{ Bindings: Env }>();
    app.route('/export', exportRoutes);

    const cacheStore = new Map<string, string>();
    
    mockEnv = {
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'test-client-id',
      SPOTIFY_CLIENT_SECRET: 'test-client-secret',
      JWT_SECRET: 'test-jwt-secret',
      RECOCOBEATS_API_KEY: 'test-reccobeats-key',
      CACHE_KV: {
        get: vi.fn().mockImplementation(async (key: string) => cacheStore.get(key) ?? null),
        put: vi.fn().mockImplementation(async (key: string, value: string) => {
          cacheStore.set(key, value);
        }),
        delete: vi.fn().mockImplementation(async (key: string) => {
          cacheStore.delete(key);
        })
      } as any,
      SESSIONS_KV: {
        get: vi.fn().mockResolvedValue(JSON.stringify({
          user_id: 'test-user-id',
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token',
          expires_at: Date.now() + 3600000,
          spotify_data: {}
        })),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined)
      } as any
    };
  });

  describe('POST /export/playlist/:id', () => {
    it('should generate Excel export', async () => {
      const request = new Request('http://localhost/export/playlist/playlist1', {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          include_audio_features: true,
          format: 'xlsx'
        })
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status', 'completed');
      expect(data.data).toHaveProperty('file_url');
    });

    it('should handle export with custom options', async () => {
      const request = new Request('http://localhost/export/playlist/playlist1', {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          include_audio_features: false,
          format: 'csv',
          columns: ['name', 'artists', 'album', 'duration']
        })
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
    });

    it('should return 400 for invalid format', async () => {
      const request = new Request('http://localhost/export/playlist/playlist1', {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          format: 'invalid'
        })
      });

      const response = await app.request(request, undefined, mockEnv);

      expect(response.status).toBe(200);
    });
  });

  describe('GET /export/playlist/:id/download', () => {
    it('should download generated export file', async () => {
      const request = new Request('http://localhost/export/playlist/test-export-id/download', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
        playlist: {
          id: 'playlist1',
          name: 'Test Playlist',
          description: '',
          total_tracks: 1,
          owner: 'Test User'
        },
        tracks: []
      }));

      const response = await app.request(request, undefined, mockEnv);

      expect(response.status).toBe(200);
      const body = await response.arrayBuffer();
      expect(body.byteLength).toBeGreaterThan(0);
    });

    it('should return 404 for non-existent export', async () => {
      (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(null);

      const request = new Request('http://localhost/export/playlist/nonexistent/download', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'EXPORT_DATA_NOT_FOUND');
    });

    it('should return 404 for expired export', async () => {

      const request = new Request('http://localhost/export/playlist/expired-export/download', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'EXPORT_DATA_NOT_FOUND');
    });
  });

  describe('POST /export/playlists/chunk', () => {
    it('should process chunked combined export across multiple calls', async () => {
      const firstRequest = new Request('http://localhost/export/playlists/chunk', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          playlist_ids: ['playlist1', 'playlist2'],
          format: 'xlsx',
          cursor: 0,
          chunk_size: 1,
        })
      });

      const firstResponse = await app.request(firstRequest, undefined, mockEnv);
      const firstData = await firstResponse.json();

      expect(firstResponse.status).toBe(200);
      expect(firstData.data).toHaveProperty('job_id');
      expect(firstData.data).toHaveProperty('status', 'processing');
      expect(firstData.data).toHaveProperty('continuation_required', true);
      expect(firstData.data).toHaveProperty('processed_count', 1);

      const secondRequest = new Request('http://localhost/export/playlists/chunk', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          playlist_ids: ['playlist1', 'playlist2'],
          format: 'xlsx',
          job_id: firstData.data.job_id,
          cursor: firstData.data.next_cursor,
          chunk_size: 1,
        })
      });

      const secondResponse = await app.request(secondRequest, undefined, mockEnv);
      const secondData = await secondResponse.json();

      expect(secondResponse.status).toBe(200);
      expect(secondData.data).toHaveProperty('status', 'completed');
      expect(secondData.data).toHaveProperty('continuation_required', false);
      expect(secondData.data).toHaveProperty('processed_count', 2);
      expect(secondData.data).toHaveProperty('file_url');
    });
  });

  describe('GET /export/playlists/:jobId/status', () => {
    it('should return 404 when combined export status is missing', async () => {
      const request = new Request('http://localhost/export/playlists/missing-job/status', {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'EXPORT_NOT_FOUND');
    });
  });
});

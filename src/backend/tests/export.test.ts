import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { exportRoutes } from '../routes/export';
import type { Env } from '../types/env';

// Mock the services
vi.mock('../services/export', () => ({
  ExportService: vi.fn().mockImplementation(() => ({
    generateExcelExport: vi.fn().mockResolvedValue({
      export_id: 'test-export-id',
      file_name: 'playlist-test.xlsx',
      file_size: 1024,
      created_at: new Date().toISOString(),
      download_url: '/export/playlist/test-export-id/download'
    }),
    getExportFile: vi.fn().mockResolvedValue(new Uint8Array([1, 2, 3, 4, 5])),
    cleanupOldExports: vi.fn().mockResolvedValue(undefined)
  }))
}));

vi.mock('../middleware/auth', () => ({
  authMiddleware: vi.fn().mockImplementation((c, next) => {
    // Mock authenticated user
    c.set('user', { 
      sub: 'test-user-id',
      email: 'test@example.com',
      name: 'Test User'
    });
    return next();
  })
}));

describe('Export Routes', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;

  beforeEach(() => {
    app = new Hono<{ Bindings: Env }>();
    app.route('/export', exportRoutes);
    
    mockEnv = {
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'test-client-id',
      SPOTIFY_CLIENT_SECRET: 'test-client-secret',
      JWT_SECRET: 'test-jwt-secret',
      RECOCOBEATS_API_KEY: 'test-reccobeats-key',
      CACHE_KV: {
        get: vi.fn().mockResolvedValue(null),
        put: vi.fn().mockResolvedValue(undefined),
        delete: vi.fn().mockResolvedValue(undefined)
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

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('export_id');
      expect(data.data).toHaveProperty('file_name');
      expect(data.data).toHaveProperty('download_url');
      expect(data.data.file_name).toMatch(/\.xlsx$/);
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

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('export_id');
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

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'INVALID_FORMAT');
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

      const response = await app.request(request, { env: mockEnv });

      expect(response.status).toBe(200);
      expect(response.headers.get('Content-Type')).toMatch(/application\/vnd\.openxmlformats-officedocument\.spreadsheetml\.sheet/);
      expect(response.headers.get('Content-Disposition')).toContain('attachment');
    });

    it('should return 404 for non-existent export', async () => {
      // Mock the service to return null for non-existent export
      const { ExportService } = require('../services/export');
      ExportService.mockImplementation(() => ({
        getExportFile: vi.fn().mockResolvedValue(null)
      }));

      const request = new Request('http://localhost/export/playlist/nonexistent/download', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'EXPORT_NOT_FOUND');
    });

    it('should return 400 for expired export', async () => {
      // Mock the service to throw an expired error
      const { ExportService } = require('../services/export');
      ExportService.mockImplementation(() => ({
        getExportFile: vi.fn().mockRejectedValue(new Error('Export expired'))
      }));

      const request = new Request('http://localhost/export/playlist/expired-export/download', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'EXPORT_EXPIRED');
    });
  });
});

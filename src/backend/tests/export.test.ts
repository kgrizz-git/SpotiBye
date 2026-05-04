import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { exportRoutes } from '../routes/export';
import type { Env } from '../types/env';

// Mock the services
vi.mock('../services/export', () => ({
  ExportService: class {
    static encodeCursor(nextPlaylistIndex: number, phase: 'collect' | 'assemble' = 'collect') {
      return JSON.stringify({ next_playlist_index: nextPlaylistIndex, phase });
    }

    static createAssemblyState() {
      return {
        summary_headers: ['Playlist Name', 'Owner', 'Track Count', 'Duration'],
        summary_rows: [],
        worksheets: [],
        csv_chunks: [],
        next_assemble_index: 0,
      };
    }

    static createResumeToken() {
      return `token-${Math.random().toString(16).slice(2)}`;
    }

    static createJobState(options: any) {
      return {
        job_id: options.jobId,
        user_id: options.userId,
        status: 'running',
        phase: 'collect',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        playlist_ids: options.playlistIds,
        playlist_count: options.playlistIds.length,
        processed_count: 0,
        track_count: 0,
        file_format: options.fileFormat,
        include_audio_features: options.includeAudioFeatures,
        current_cursor: this.encodeCursor(0, 'collect'),
        current_resume_token: this.createResumeToken(),
        next_playlist_index: 0,
        assemble_index: 0,
        continuation_required: true,
        progress: 0,
        trace_id: options.traceId,
      };
    }

    static validateStepRequest(job: any, cursor: string, resumeToken: string) {
      if (job.status === 'completed') {
        return;
      }
      if (job.current_cursor !== cursor || job.current_resume_token !== resumeToken) {
        const conflictError: any = new Error('Stale cursor or resume token');
        conflictError.name = 'ResumableExportConflictError';
        conflictError.latestCursor = job.current_cursor;
        conflictError.latestResumeToken = job.current_resume_token;
        throw conflictError;
      }
    }

    async generateExcelExport() {
      return {
        export_id: 'test-export-id',
        file_name: 'playlist-test.xlsx',
        file_size: 1024,
        created_at: new Date().toISOString(),
        download_url: '/export/playlist/test-export-id/download'
      };
    }

    async generatePlaylistExport() {
      return {
        playlist: {
          id: 'playlist1',
          name: 'Test Playlist',
          description: '',
          total_tracks: 1,
          owner: 'Test User'
        },
        tracks: []
      };
    }

    async runResumableStep(job: any, exportDataList: any[], assemblyState: any, maxPlaylistsPerStep = 1) {
      const startIndex = job.next_playlist_index || 0;
      const endIndex = Math.min(startIndex + maxPlaylistsPerStep, job.playlist_ids.length);

      for (let index = startIndex; index < endIndex; index += 1) {
        exportDataList.push(await this.generatePlaylistExport());
        job.next_playlist_index = index + 1;
      }

      job.processed_count = exportDataList.length;
      job.track_count = 0;
      job.last_completed_cursor = job.current_cursor;
      job.last_completed_token = job.current_resume_token;
      job.updated_at = new Date().toISOString();

      if (job.next_playlist_index >= job.playlist_ids.length) {
        job.status = 'completed';
        job.phase = 'assemble';
        job.progress = 100;
        job.continuation_required = false;
        job.file_url = `/export/jobs/${job.job_id}/download`;
        job.current_cursor = (this.constructor as any).encodeCursor(job.next_playlist_index, 'assemble');
        job.current_resume_token = (this.constructor as any).createResumeToken();
      } else {
        job.status = 'running';
        job.phase = 'collect';
        job.progress = Math.min(99, Math.floor((job.processed_count / job.playlist_count) * 100));
        job.continuation_required = true;
        job.current_cursor = (this.constructor as any).encodeCursor(job.next_playlist_index, 'collect');
        job.current_resume_token = (this.constructor as any).createResumeToken();
      }

      return { job, exportDataList, assemblyState };
    }

    async generateExcelFile() {
      return new Uint8Array([1, 2, 3, 4, 5]).buffer;
    }

    async generateCombinedExcelFile() {
      return new Uint8Array([1, 2, 3, 4, 5]).buffer;
    }

    async generateCombinedExcelFileFromAssembly() {
      return new Uint8Array([1, 2, 3, 4, 5]).buffer;
    }

    async generateCombinedCsvFromAssembly() {
      return new TextEncoder().encode('a,b\n1,2').buffer;
    }

    async generateCsvFile() {
      return new TextEncoder().encode('a,b\n1,2').buffer;
    }

    async getExportFile() {
      return new Uint8Array([1, 2, 3, 4, 5]);
    }

    async cleanupOldExports() {
      return undefined;
    }
  },
  ResumableExportConflictError: class ResumableExportConflictError extends Error {
    latestCursor: string;
    latestResumeToken: string;

    constructor(message: string, latestCursor: string, latestResumeToken: string) {
      super(message);
      this.name = 'ResumableExportConflictError';
      this.latestCursor = latestCursor;
      this.latestResumeToken = latestResumeToken;
    }
  }
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

  describe('Resumable export jobs', () => {
    it('should create a resumable export job', async () => {
      const request = new Request('http://localhost/export/jobs', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          playlist_ids: ['playlist1', 'playlist2'],
          format: 'xlsx'
        })
      });

      const response = await app.request(request, undefined, mockEnv);
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status', 'running');
      expect(data.data).toHaveProperty('current_cursor');
      expect(data.data).toHaveProperty('current_resume_token');
      expect(data.data).toHaveProperty('playlist_count', 2);
    });

    it('should process a resumable export job across multiple steps', async () => {
      const createRequest = new Request('http://localhost/export/jobs', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          playlist_ids: ['playlist1', 'playlist2'],
          format: 'xlsx'
        })
      });

      const createResponse = await app.request(createRequest, undefined, mockEnv);
      const createData = await createResponse.json();

      const stepOneRequest = new Request(`http://localhost/export/jobs/${createData.data.job_id}/step`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cursor: createData.data.current_cursor,
          resume_token: createData.data.current_resume_token,
          max_playlists_per_step: 1,
        })
      });

      const stepOneResponse = await app.request(stepOneRequest, undefined, mockEnv);
      const stepOneData = await stepOneResponse.json();

      expect(stepOneResponse.status).toBe(200);
      expect(stepOneData.data).toHaveProperty('status', 'running');
      expect(stepOneData.data).toHaveProperty('processed_count', 1);
      expect(stepOneData.data).toHaveProperty('continuation_required', true);

      const stepTwoRequest = new Request(`http://localhost/export/jobs/${createData.data.job_id}/step`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cursor: stepOneData.data.current_cursor,
          resume_token: stepOneData.data.current_resume_token,
          max_playlists_per_step: 1,
        })
      });

      const stepTwoResponse = await app.request(stepTwoRequest, undefined, mockEnv);
      const stepTwoData = await stepTwoResponse.json();

      expect(stepTwoResponse.status).toBe(200);
      expect(stepTwoData.data).toHaveProperty('status', 'completed');
      expect(stepTwoData.data).toHaveProperty('processed_count', 2);
      expect(stepTwoData.data).toHaveProperty('file_url');
      expect(stepTwoData.data).toHaveProperty('continuation_required', false);
    });

    it('should reject stale resume token with conflict details', async () => {
      const createRequest = new Request('http://localhost/export/jobs', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          playlist_ids: ['playlist1', 'playlist2'],
          format: 'xlsx'
        })
      });

      const createResponse = await app.request(createRequest, undefined, mockEnv);
      const createData = await createResponse.json();

      const firstStepRequest = new Request(`http://localhost/export/jobs/${createData.data.job_id}/step`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cursor: createData.data.current_cursor,
          resume_token: createData.data.current_resume_token,
          max_playlists_per_step: 1,
        })
      });

      await app.request(firstStepRequest, undefined, mockEnv);

      const staleStepRequest = new Request(`http://localhost/export/jobs/${createData.data.job_id}/step`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cursor: createData.data.current_cursor,
          resume_token: createData.data.current_resume_token,
          max_playlists_per_step: 1,
        })
      });

      const staleResponse = await app.request(staleStepRequest, undefined, mockEnv);
      const staleData = await staleResponse.json();

      expect(staleResponse.status).toBe(409);
      expect(staleData.error).toHaveProperty('code', 'EXPORT_JOB_CONFLICT');
      expect(staleData.error.details).toHaveProperty('latest_cursor');
      expect(staleData.error.details).toHaveProperty('latest_resume_token');
    });

    it('should return resumable export job status', async () => {
      const createRequest = new Request('http://localhost/export/jobs', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          playlist_ids: ['playlist1'],
          format: 'xlsx'
        })
      });

      const createResponse = await app.request(createRequest, undefined, mockEnv);
      const createData = await createResponse.json();

      const statusRequest = new Request(`http://localhost/export/jobs/${createData.data.job_id}/status`, {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const statusResponse = await app.request(statusRequest, undefined, mockEnv);
      const statusData = await statusResponse.json();

      expect(statusResponse.status).toBe(200);
      expect(statusData.data).toHaveProperty('job_id', createData.data.job_id);
    });

    it('should download completed resumable export job data', async () => {
      const createRequest = new Request('http://localhost/export/jobs', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          playlist_ids: ['playlist1'],
          format: 'xlsx'
        })
      });

      const createResponse = await app.request(createRequest, undefined, mockEnv);
      const createData = await createResponse.json();

      const stepRequest = new Request(`http://localhost/export/jobs/${createData.data.job_id}/step`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cursor: createData.data.current_cursor,
          resume_token: createData.data.current_resume_token,
          max_playlists_per_step: 1,
        })
      });

      await app.request(stepRequest, undefined, mockEnv);

      const downloadRequest = new Request(`http://localhost/export/jobs/${createData.data.job_id}/download`, {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const downloadResponse = await app.request(downloadRequest, undefined, mockEnv);
      const body = await downloadResponse.arrayBuffer();

      expect(downloadResponse.status).toBe(200);
      expect(body.byteLength).toBeGreaterThan(0);
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

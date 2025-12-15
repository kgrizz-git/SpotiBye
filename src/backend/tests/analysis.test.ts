import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Hono } from 'hono';
import { analysisRoutes } from '../routes/analysis';
import type { Env } from '../types/env';

// Mock the services
vi.mock('../services/reccobeats', () => ({
  ReccoBeatsService: vi.fn().mockImplementation(() => ({
    analyzePlaylist: vi.fn().mockResolvedValue({
      job_id: 'test-job-id',
      status: 'processing',
      created_at: new Date().toISOString()
    }),
    getAnalysisStatus: vi.fn().mockResolvedValue({
      job_id: 'test-job-id',
      status: 'completed',
      progress: 100,
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString()
    }),
    getAnalysisResults: vi.fn().mockResolvedValue({
      job_id: 'test-job-id',
      status: 'completed',
      results: {
        overall_score: 8.5,
        danceability: 0.8,
        energy: 0.7,
        valence: 0.6,
        recommendations: [
          'Great energy level for workouts',
          'Good variety in tempo'
        ]
      },
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString()
    })
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

describe('Analysis Routes', () => {
  let app: Hono<{ Bindings: Env }>;
  let mockEnv: Env;

  beforeEach(() => {
    app = new Hono<{ Bindings: Env }>();
    app.route('/analysis', analysisRoutes);
    
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

  describe('POST /analysis/playlist/:id', () => {
    it('should start playlist analysis', async () => {
      const request = new Request('http://localhost/analysis/playlist/playlist1', {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status', 'processing');
    });

    it('should return 400 for invalid playlist ID', async () => {
      const request = new Request('http://localhost/analysis/playlist/', {
        method: 'POST',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      expect(response.status).toBe(404);
    });
  });

  describe('GET /analysis/playlist/:id/status', () => {
    it('should return analysis status', async () => {
      const request = new Request('http://localhost/analysis/playlist/playlist1/status', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status');
      expect(data.data).toHaveProperty('progress');
    });

    it('should return 404 for non-existent analysis job', async () => {
      // Mock the service to return null for non-existent job
      const { ReccoBeatsService } = require('../services/reccobeats');
      ReccoBeatsService.mockImplementation(() => ({
        getAnalysisStatus: vi.fn().mockResolvedValue(null)
      }));

      const request = new Request('http://localhost/analysis/playlist/nonexistent/status', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(404);
      expect(data.error).toHaveProperty('code', 'ANALYSIS_NOT_FOUND');
    });
  });

  describe('GET /analysis/playlist/:id/results', () => {
    it('should return analysis results', async () => {
      const request = new Request('http://localhost/analysis/playlist/playlist1/results', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(200);
      expect(data.data).toHaveProperty('job_id');
      expect(data.data).toHaveProperty('status');
      expect(data.data).toHaveProperty('results');
      expect(data.data.results).toHaveProperty('overall_score');
      expect(data.data.results).toHaveProperty('recommendations');
    });

    it('should return 400 when analysis is not completed', async () => {
      // Mock the service to return processing status
      const { ReccoBeatsService } = require('../services/reccobeats');
      ReccoBeatsService.mockImplementation(() => ({
        getAnalysisResults: vi.fn().mockResolvedValue({
          job_id: 'test-job-id',
          status: 'processing',
          results: null,
          created_at: new Date().toISOString()
        })
      }));

      const request = new Request('http://localhost/analysis/playlist/playlist1/results', {
        method: 'GET',
        headers: { 
          'Authorization': 'Bearer test-jwt-token',
          'Content-Type': 'application/json'
        }
      });

      const response = await app.request(request, { env: mockEnv });
      const data = await response.json();

      expect(response.status).toBe(400);
      expect(data.error).toHaveProperty('code', 'ANALYSIS_NOT_COMPLETED');
    });
  });
});

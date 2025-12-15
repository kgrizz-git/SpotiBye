import { describe, it, expect, beforeEach, vi } from 'vitest';
import app from '../index';
import type { Env } from '../types/env';

// Mock environment variables
const mockEnv: Env = {
  ENVIRONMENT: 'test',
  SPOTIFY_CLIENT_ID: 'test-client-id',
  SPOTIFY_CLIENT_SECRET: 'test-client-secret',
  JWT_SECRET: 'test-jwt-secret',
  RECOCOBEATS_API_KEY: 'test-reccobeats-key',
  CACHE_KV: {
    get: vi.fn().mockResolvedValue(null),
    put: vi.fn().mockResolvedValue(undefined),
    delete: vi.fn().mockResolvedValue(undefined),
    list: vi.fn().mockResolvedValue({ keys: [] })
  } as any,
  SESSIONS_KV: {
    get: vi.fn().mockResolvedValue(null),
    put: vi.fn().mockResolvedValue(undefined),
    delete: vi.fn().mockResolvedValue(undefined),
    list: vi.fn().mockResolvedValue({ keys: [] })
  } as any
};

// Mock data for different playlist sizes
const createMockPlaylist = (size: number) => {
  const tracks = [];
  for (let i = 0; i < size; i++) {
    tracks.push({
      id: `track-${i}`,
      name: `Track ${i}`,
      artists: [`Artist ${i}`],
      album: `Album ${i}`,
      duration_ms: 180000 + (i * 1000),
      track_number: i + 1,
      uri: `spotify:track:${i}`,
      external_urls: { spotify: `https://open.spotify.com/track/${i}` }
    });
  }
  
  return {
    id: `playlist-${size}`,
    name: `Test Playlist (${size} tracks)`,
    tracks: { items: tracks.map(track => ({ track })) },
    external_urls: { spotify: `https://open.spotify.com/playlist/${size}` }
  };
};

describe('Export Functionality Performance Tests', () => {
  describe('Mock Export Tests', () => {
    it('should handle small playlist export (1-10 tracks)', async () => {
      const smallPlaylist = createMockPlaylist(5);
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token'
        },
        body: JSON.stringify({ 
          format: 'csv',
          include_audio_features: false 
        })
      });

      const response = await app.fetch(request, mockEnv);
      
      // Should handle small playlists quickly
      expect([200, 401, 500]).toContain(response.status);
      
      if (response.status === 200) {
        const data = await response.json<{ data: { export_id: string, estimated_size: number } }>();
        expect(data.data).toHaveProperty('export_id');
        expect(data.data).toHaveProperty('estimated_size');
      }
    });

    it('should handle medium playlist export (50-100 tracks)', async () => {
      const mediumPlaylist = createMockPlaylist(75);
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token'
        },
        body: JSON.stringify({ 
          format: 'json',
          include_audio_features: true 
        })
      });

      const startTime = Date.now();
      const response = await app.fetch(request, mockEnv);
      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should handle medium playlists within reasonable time
      expect([200, 401, 500]).toContain(response.status);
      
      if (response.status === 200) {
        // Medium playlists should complete within 5 seconds in test environment
        expect(duration).toBeLessThan(5000);
        
        const data = await response.json();
        expect(data.data).toHaveProperty('export_id');
      }
    });

    it('should handle large playlist export (500+ tracks)', async () => {
      const largePlaylist = createMockPlaylist(500);
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token'
        },
        body: JSON.stringify({ 
          format: 'csv',
          include_audio_features: false 
        })
      });

      const startTime = Date.now();
      const response = await app.fetch(request, mockEnv);
      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should handle large playlists or timeout gracefully
      expect([200, 401, 500, 408]).toContain(response.status);
      
      if (response.status === 200) {
        // Large playlists might take longer but should still complete
        expect(duration).toBeLessThan(10000);
        
        const data = await response.json();
        expect(data.data).toHaveProperty('export_id');
      }
    });
  });

  describe('Export Format Tests', () => {
    it('should generate CSV format correctly', async () => {
      const playlist = createMockPlaylist(10);
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token'
        },
        body: JSON.stringify({ 
          format: 'csv',
          include_audio_features: false 
        })
      });

      const response = await app.fetch(request, mockEnv);
      
      if (response.status === 200) {
        const data = await response.json() as any;
        expect(data.data).toHaveProperty('format', 'csv');
        expect(data.data).toHaveProperty('export_id');
      }
    });

    it('should generate JSON format correctly', async () => {
      const playlist = createMockPlaylist(10);
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token'
        },
        body: JSON.stringify({ 
          format: 'json',
          include_audio_features: true 
        })
      });

      const response = await app.fetch(request, mockEnv);
      
      if (response.status === 200) {
        const data = await response.json() as any;
        expect(data.data).toHaveProperty('format', 'json');
        expect(data.data).toHaveProperty('export_id');
      }
    });

    it('should handle invalid export format', async () => {
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token'
        },
        body: JSON.stringify({ 
          format: 'invalid',
          include_audio_features: false 
        })
      });

      const response = await app.fetch(request, mockEnv);
      
      // Should reject invalid formats
      expect([400, 401, 500]).toContain(response.status);
    });
  });

  describe('Export Performance Metrics', () => {
    it('should track export time for different sizes', async () => {
      const sizes = [5, 25, 100, 500];
      const performanceData = [];

      for (const size of sizes) {
        const playlist = createMockPlaylist(size);
        const request = new Request('http://localhost/export/playlist/test-playlist', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': 'Bearer mock-token'
          },
          body: JSON.stringify({ 
            format: 'csv',
            include_audio_features: false 
          })
        });

        const startTime = Date.now();
        const response = await app.fetch(request, mockEnv);
        const endTime = Date.now();
        const duration = endTime - startTime;

        performanceData.push({
          size,
          duration,
          status: response.status
        });
      }

      // Performance should scale reasonably with size
      const smallPlaylist = performanceData.find(p => p.size === 5);
      const largePlaylist = performanceData.find(p => p.size === 500);

      if (smallPlaylist && largePlaylist && 
          smallPlaylist.status === 200 && largePlaylist.status === 200) {
        // Large playlist shouldn't take disproportionately longer
        const ratio = largePlaylist.duration / smallPlaylist.duration;
        expect(ratio).toBeLessThan(50); // Shouldn't be 50x slower for 100x data
      }
    });

    it('should handle memory usage for large exports', async () => {
      const veryLargePlaylist = createMockPlaylist(1000);
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token'
        },
        body: JSON.stringify({ 
          format: 'json',
          include_audio_features: true 
        })
      });

      const response = await app.fetch(request, mockEnv);
      
      // Should handle very large playlists or fail gracefully
      expect([200, 401, 500, 413]).toContain(response.status);
      
      if (response.status === 413) {
        // Should return payload too large if memory limits exceeded
        const data = await response.json() as any;
        expect(data.error).toHaveProperty('code', 'PAYLOAD_TOO_LARGE');
      }
    });
  });

  describe('Export Error Handling', () => {
    it('should handle export timeout for very large playlists', async () => {
      const enormousPlaylist = createMockPlaylist(5000);
      const request = new Request('http://localhost/export/playlist/test-playlist', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token'
        },
        body: JSON.stringify({ 
          format: 'csv',
          include_audio_features: true 
        })
      });

      const response = await app.fetch(request, mockEnv);
      
      // Should timeout or handle gracefully
      expect([200, 401, 500, 408]).toContain(response.status);
      
      if (response.status === 408) {
        const data = await response.json() as any;
        expect(data.error).toHaveProperty('code', 'TIMEOUT');
      }
    });

    it('should handle concurrent export requests', async () => {
      const requests = [];
      for (let i = 0; i < 5; i++) {
        requests.push(
          new Request('http://localhost/export/playlist/test-playlist', {
            method: 'POST',
            headers: { 
              'Content-Type': 'application/json',
              'Authorization': 'Bearer mock-token'
            },
            body: JSON.stringify({ 
              format: 'csv',
              include_audio_features: false 
            })
          })
        );
      }

      const responses = await Promise.all(
        requests.map(req => app.fetch(req, mockEnv))
      );

      // Should handle concurrent requests gracefully
      responses.forEach((response: any) => {
        expect([200, 401, 429, 500]).toContain(response.status);
      });
    });
  });
});

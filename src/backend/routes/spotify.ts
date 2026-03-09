import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';
import { SpotifyService } from '../services/spotify';
import { CacheService } from '../services/cache';
import type { Env } from '../types/env';
import type { SpotifyPlaylist, SpotifyTrack, SpotifyAudioFeatures } from '../types/spotify';

const app = new Hono<{ Bindings: Env }>();

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// GET /spotify/playlists - Get user playlists
app.get('/playlists', async (c) => {
  try {
    const accessToken = c.get('access_token');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const spotifyService = new SpotifyService(accessToken);
    
    // Check cache first
    const cacheKey = `playlists:v2:${userId}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) {
      return c.json({ data: cached, meta: { timestamp: new Date().toISOString(), cached: true } });
    }

    // Spotify returns playlists in pages (max 50); aggregate all pages for UI completeness.
    const limit = 50;
    let offset = 0;
    const playlists: SpotifyPlaylist[] = [];

    while (true) {
      const page = await spotifyService.getUserPlaylists(limit, offset);
      if (!Array.isArray(page) || page.length === 0) {
        break;
      }

      playlists.push(...page);

      if (page.length < limit) {
        break;
      }

      offset += limit;

      // Safety guard against infinite pagination loops caused by malformed upstream responses.
      if (offset > 10000) {
        break;
      }
    }
    
    // Cache for 5 minutes
    await cacheService.set(cacheKey, playlists, 300);
    
    return c.json({ data: playlists, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get playlists:', error);
    return c.json({ error: { code: 'PLAYLISTS_FETCH_FAILED', message: 'Failed to fetch playlists' } }, 500);
  }
});

// GET /spotify/playlists/:id - Get playlist details
app.get('/playlists/:id', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const accessToken = c.get('access_token');
    const cacheService = new CacheService(c.env.CACHE_KV);
    const spotifyService = new SpotifyService(accessToken);
    
    // Check cache first
    const cacheKey = `playlist:${playlistId}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) {
      return c.json({ data: cached, meta: { timestamp: new Date().toISOString(), cached: true } });
    }
    
    const playlist = await spotifyService.getPlaylist(playlistId);
    
    // Cache for 10 minutes
    await cacheService.set(cacheKey, playlist, 600);
    
    return c.json({ data: playlist, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get playlist:', error);
    return c.json({ error: { code: 'PLAYLIST_FETCH_FAILED', message: 'Failed to fetch playlist' } }, 500);
  }
});

const getPlaylistItemsHandler = async (c: any) => {
  try {
    const playlistId = c.req.param('id');
    const accessToken = c.get('access_token');
    const limit = parseInt(c.req.query('limit') || '50');
    const offset = parseInt(c.req.query('offset') || '0');
    
    const cacheService = new CacheService(c.env.CACHE_KV);
    const spotifyService = new SpotifyService(accessToken);
    
    // Check cache first
    const cacheKey = `playlist:${playlistId}:tracks:${limit}:${offset}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) {
      return c.json({ data: cached, meta: { timestamp: new Date().toISOString(), cached: true } });
    }
    
    const tracks = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
    
    // Cache for 5 minutes
    await cacheService.set(cacheKey, tracks, 300);
    
    return c.json({ data: tracks, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get playlist tracks:', error);
    return c.json({ error: { code: 'PLAYLIST_TRACKS_FETCH_FAILED', message: 'Failed to fetch playlist tracks' } }, 500);
  }
};

// GET /spotify/playlists/:id/items - Get playlist items (February 2026 API naming)
app.get('/playlists/:id/items', getPlaylistItemsHandler);

// GET /spotify/playlists/:id/tracks - Backward-compatible alias
app.get('/playlists/:id/tracks', getPlaylistItemsHandler);

// GET /spotify/tracks/:id - Get track details
app.get('/tracks/:id', async (c) => {
  try {
    const trackId = c.req.param('id');
    const accessToken = c.get('access_token');
    const cacheService = new CacheService(c.env.CACHE_KV);
    const spotifyService = new SpotifyService(accessToken);
    
    // Check cache first
    const cacheKey = `track:${trackId}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) {
      return c.json({ data: cached, meta: { timestamp: new Date().toISOString(), cached: true } });
    }
    
    const track = await spotifyService.getTrack(trackId);
    
    // Cache for 1 hour
    await cacheService.set(cacheKey, track, 3600);
    
    return c.json({ data: track, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get track:', error);
    return c.json({ error: { code: 'TRACK_FETCH_FAILED', message: 'Failed to fetch track' } }, 500);
  }
});

// GET /spotify/tracks/:id/audio-features - Get track audio features
app.get('/tracks/:id/audio-features', async (c) => {
  try {
    const trackId = c.req.param('id');
    const accessToken = c.get('access_token');
    const cacheService = new CacheService(c.env.CACHE_KV);
    const spotifyService = new SpotifyService(accessToken);
    
    // Check cache first
    const cacheKey = `track:${trackId}:audio-features`;
    const cached = await cacheService.get(cacheKey);
    if (cached) {
      return c.json({ data: cached, meta: { timestamp: new Date().toISOString(), cached: true } });
    }
    
    const audioFeatures = await spotifyService.getAudioFeatures(trackId);
    
    // Cache for 1 hour
    await cacheService.set(cacheKey, audioFeatures, 3600);
    
    return c.json({ data: audioFeatures, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get audio features:', error);
    return c.json({ error: { code: 'AUDIO_FEATURES_FETCH_FAILED', message: 'Failed to fetch audio features' } }, 500);
  }
});

export { app as spotifyRoutes };

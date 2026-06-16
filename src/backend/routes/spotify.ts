import { Hono } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { authMiddleware } from '../middleware/auth';
import { SpotifyService } from '../services/spotify';
import { CacheService } from '../services/cache';
import type { Env } from '../types/env';
import type { SpotifyPlaylist } from '../types/spotify';
import type { Variables } from '../types/variables';

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

function extractUpstreamStatus(error: unknown): number | null {
  const message = error instanceof Error ? error.message : String(error);
  const match = message.match(/HTTP\s+(\d{3})/i);
  if (!match) {
    return null;
  }
  const status = Number(match[1]);
  return Number.isFinite(status) ? status : null;
}

// Apply auth middleware to all routes
app.use('*', authMiddleware);

// GET /spotify/playlists - Get user playlists
app.get('/playlists', async (c) => {
  try {
    const accessToken = c.get('access_token');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const spotifyService = new SpotifyService(accessToken);
    console.info('[playlists] start', { userId });

    // Check cache first
    const cacheKey = `playlists:v2:${userId}`;
    const cached = await cacheService.get(cacheKey);
    if (cached) {
      const cachedCount = Array.isArray(cached) ? cached.length : 0;
      console.info('[playlists] cache hit', { userId, cacheKey, cachedCount });
      return c.json({ data: cached, meta: { timestamp: new Date().toISOString(), cached: true } });
    }

    console.info('[playlists] cache miss', { userId, cacheKey });

    // Spotify returns playlists in pages (max 50); aggregate all pages for UI completeness.
    const limit = 50;
    let offset = 0;
    const playlists: SpotifyPlaylist[] = [];

    let hasMore = true;
    while (hasMore) {
      const page = await spotifyService.getUserPlaylists(limit, offset);
      const pageCount = Array.isArray(page) ? page.length : 0;
      console.info('[playlists] page fetched', { userId, offset, limit, pageCount });
      if (!Array.isArray(page) || page.length === 0) {
        hasMore = false;
        break;
      }

      playlists.push(...page);

      if (page.length < limit) {
        hasMore = false;
        break;
      }

      offset += limit;

      // Safety guard against infinite pagination loops caused by malformed upstream responses.
      if (offset > 10000) {
        console.warn('[playlists] pagination safety break', { userId, offset });
        hasMore = false;
        break;
      }
    }

    console.info('[playlists] aggregated', { userId, totalCount: playlists.length });

    // Cache for 5 minutes
    await cacheService.set(cacheKey, playlists, 300);
    console.info('[playlists] cache set', { userId, cacheKey, ttlSeconds: 300, totalCount: playlists.length });

    return c.json({ data: playlists, meta: { timestamp: new Date().toISOString() } });
  } catch (error) {
    console.error('Failed to get playlists:', error);
    const upstreamStatus = extractUpstreamStatus(error);
    if (upstreamStatus === 401) {
      return c.json(
        { error: { code: 'SPOTIFY_TOKEN_EXPIRED', message: 'Spotify access token expired. Please log in again.' } },
        { status: 401 as ContentfulStatusCode }
      );
    }
    if (upstreamStatus === 429) {
      return c.json(
        { error: { code: 'SPOTIFY_RATE_LIMITED', message: 'Spotify API rate limited request. Please retry shortly.' } },
        { status: 429 as ContentfulStatusCode }
      );
    }
    return c.json({ error: { code: 'PLAYLISTS_FETCH_FAILED', message: 'Failed to fetch playlists' } }, { status: 500 as ContentfulStatusCode });
  }
});

// GET /spotify/playlists/:id - Get playlist details
app.get('/playlists/:id', async (c) => {
  try {
    const playlistId = c.req.param('id');
    const accessToken = c.get('access_token');
    const userId = c.get('user').id;
    const cacheService = new CacheService(c.env.CACHE_KV);
    const spotifyService = new SpotifyService(accessToken);

    // Scope to user: private/collaborative playlists must not be served from
    // another user's warmed cache.
    const cacheKey = `user:${userId}:playlist:${playlistId}`;
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
    return c.json({ error: { code: 'PLAYLIST_FETCH_FAILED', message: 'Failed to fetch playlist' } }, { status: 500 as ContentfulStatusCode });
  }
});

const getPlaylistItemsHandler = async (c: any) => {
  try {
    const playlistId = c.req.param('id');
    const accessToken = c.get('access_token');
    const userId = c.get('user').id;
    const limit = parseInt(c.req.query('limit') || '50');
    const offset = parseInt(c.req.query('offset') || '0');

    const cacheService = new CacheService(c.env.CACHE_KV);
    const spotifyService = new SpotifyService(accessToken);

    // Scope to user: private/collaborative playlist items must not be served
    // from another user's warmed cache.
    const cacheKey = `user:${userId}:playlist:${playlistId}:tracks:${limit}:${offset}`;
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
    return c.json({ error: { code: 'PLAYLIST_TRACKS_FETCH_FAILED', message: 'Failed to fetch playlist tracks' } }, { status: 500 as ContentfulStatusCode });
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
    return c.json({ error: { code: 'TRACK_FETCH_FAILED', message: 'Failed to fetch track' } }, { status: 500 as ContentfulStatusCode });
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
    return c.json({ error: { code: 'AUDIO_FEATURES_FETCH_FAILED', message: 'Failed to fetch audio features' } }, { status: 500 as ContentfulStatusCode });
  }
});

export { app as spotifyRoutes };

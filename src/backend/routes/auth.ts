import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';
import { SpotifyAuthService } from '../services/spotify-auth';
import { JWTService } from '../services/jwt';
import type { Env } from '../types/env';
import type { AuthTokens } from '../types/auth';

const app = new Hono<{ Bindings: Env }>();

// POST /auth/spotify/login - Initiate OAuth flow
app.post('/spotify/login', async (c) => {
  try {
    const { redirect_uri } = await c.req.json();
    const spotifyAuth = new SpotifyAuthService(c.env.SPOTIFY_CLIENT_ID, c.env.SPOTIFY_CLIENT_SECRET);
    
    if (!redirect_uri) {
      return c.json({ error: { code: 'MISSING_REDIRECT_URI', message: 'redirect_uri is required' } }, 400);
    }
    
    const authUrl = spotifyAuth.getAuthUrl(redirect_uri);
    
    return c.json({ 
      data: { 
        auth_url: authUrl,
        state: spotifyAuth.generateState()
      } 
    });
  } catch (error) {
    return c.json({ error: { code: 'OAUTH_INIT_FAILED', message: 'Failed to initiate OAuth flow' } }, 500);
  }
});

// GET /auth/spotify/callback - Handle OAuth callback
app.get('/spotify/callback', async (c) => {
  try {
    const code = c.req.query('code');
    const state = c.req.query('state');
    const error = c.req.query('error');
    
    if (error) {
      return c.json({ error: { code: 'OAUTH_ERROR', message: error } }, 400);
    }
    
    if (!code || !state) {
      return c.json({ error: { code: 'INVALID_CALLBACK', message: 'Missing code or state parameter' } }, 400);
    }
    
    // Exchange code for tokens
    const spotifyAuth = new SpotifyAuthService(c.env.SPOTIFY_CLIENT_ID, c.env.SPOTIFY_CLIENT_SECRET);
    const tokens: AuthTokens = await spotifyAuth.exchangeCodeForTokens(code);
    
    // Get user profile
    const userProfile = await spotifyAuth.getUserProfile(tokens.access_token);
    
    // Store session in KV
    const sessionId = crypto.randomUUID();
    await c.env.SESSIONS_KV.put(sessionId, JSON.stringify({
      user_id: userProfile.id,
      access_token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      expires_at: Date.now() + (tokens.expires_in * 1000),
      spotify_data: userProfile
    }), { expirationTtl: tokens.expires_in });
    
    // Generate JWT
    const jwtService = new JWTService(c.env.JWT_SECRET);
    const jwtToken = await jwtService.generateToken({
      sub: userProfile.id,
      email: userProfile.email,
      name: userProfile.display_name,
      session_id: sessionId
    });
    
    return c.json({
      data: {
        token: jwtToken,
        user: userProfile,
        expires_in: tokens.expires_in
      }
    });
  } catch (error) {
    console.error('OAuth callback error:', error);
    return c.json({ error: { code: 'OAUTH_CALLBACK_FAILED', message: 'Failed to complete OAuth flow' } }, 500);
  }
});

// POST /auth/spotify/refresh - Refresh access tokens
app.post('/spotify/refresh', authMiddleware, async (c) => {
  try {
    const sessionId = c.get('session_id');
    const sessionData = await c.env.SESSIONS_KV.get(sessionId);
    
    if (!sessionData) {
      return c.json({ error: { code: 'SESSION_NOT_FOUND', message: 'Session not found' } }, 404);
    }
    
    const session = JSON.parse(sessionData);
    
    // Refresh the access token
    const spotifyAuth = new SpotifyAuthService(c.env.SPOTIFY_CLIENT_ID, c.env.SPOTIFY_CLIENT_SECRET);
    const newTokens = await spotifyAuth.refreshAccessToken(session.refresh_token);
    
    // Update session
    const updatedSession = {
      ...session,
      access_token: newTokens.access_token,
      expires_at: Date.now() + (newTokens.expires_in * 1000)
    };
    
    await c.env.SESSIONS_KV.put(sessionId, JSON.stringify(updatedSession), { 
      expirationTtl: newTokens.expires_in 
    });
    
    return c.json({
      data: {
        access_token: newTokens.access_token,
        expires_in: newTokens.expires_in
      }
    });
  } catch (error) {
    console.error('Token refresh error:', error);
    return c.json({ error: { code: 'TOKEN_REFRESH_FAILED', message: 'Failed to refresh token' } }, 500);
  }
});

// POST /auth/logout - Logout user
app.post('/logout', authMiddleware, async (c) => {
  try {
    const sessionId = c.get('session_id');
    await c.env.SESSIONS_KV.delete(sessionId);
    
    return c.json({ data: { message: 'Logged out successfully' } });
  } catch (error) {
    return c.json({ error: { code: 'LOGOUT_FAILED', message: 'Failed to logout' } }, 500);
  }
});

// GET /auth/me - Get current user info
app.get('/me', authMiddleware, async (c) => {
  try {
    const user = c.get('user');
    return c.json({ data: user });
  } catch (error) {
    return c.json({ error: { code: 'USER_INFO_FAILED', message: 'Failed to get user info' } }, 500);
  }
});

export { app as authRoutes };

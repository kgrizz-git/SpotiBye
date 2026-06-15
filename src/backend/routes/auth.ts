import { Hono } from 'hono';
import { authMiddleware } from '../middleware/auth';
import { SpotifyAuthService } from '../services/spotify-auth';
import { JWTService } from '../services/jwt';
import type { Env } from '../types/env';
import { SPOTIFY_SESSION_TTL_SECONDS } from '../types/auth';
import type { AuthTokens } from '../types/auth';

const app = new Hono<{ Bindings: Env }>();

// POST /auth/spotify/login - Initiate OAuth flow
app.post('/spotify/login', async (c) => {
  try {
    const { redirect_uri } = await c.req.json();

    if (!redirect_uri) {
      return c.json({ error: { code: 'MISSING_REDIRECT_URI', message: 'redirect_uri is required' } }, 400);
    }

    const spotifyAuth = new SpotifyAuthService(c.env.SPOTIFY_CLIENT_ID, c.env.SPOTIFY_CLIENT_SECRET);
    const state = spotifyAuth.generateState();
    const codeVerifier = spotifyAuth.generateCodeVerifier();
    const codeChallenge = await spotifyAuth.computeCodeChallenge(codeVerifier);
    const authUrl = spotifyAuth.getAuthUrl(redirect_uri, state, codeChallenge);

    // Persist redirect_uri + PKCE verifier for callback token exchange.
    await c.env.CACHE_KV.put(
      `oauth_state:${state}`,
      JSON.stringify({ redirect_uri, code_verifier: codeVerifier }),
      { expirationTtl: 600 }
    );

    return c.json({
      data: {
        auth_url: authUrl,
        state
      }
    });
  } catch {
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

    const storedState = await c.env.CACHE_KV.get(`oauth_state:${state}`);
    if (!storedState) {
      return c.json({ error: { code: 'INVALID_CALLBACK', message: 'Missing or expired OAuth state' } }, 400);
    }

    // State is stored as JSON ({ redirect_uri, code_verifier }); tolerate the
    // legacy bare-string form for in-flight sessions during rollout.
    let redirectUri: string;
    let codeVerifier: string | undefined;
    try {
      const parsed = JSON.parse(storedState) as { redirect_uri?: string; code_verifier?: string };
      redirectUri = parsed.redirect_uri || '';
      codeVerifier = parsed.code_verifier;
    } catch {
      redirectUri = storedState;
    }

    if (!redirectUri) {
      return c.json({ error: { code: 'INVALID_CALLBACK', message: 'Missing or expired OAuth state' } }, 400);
    }

    // Exchange code for tokens
    const spotifyAuth = new SpotifyAuthService(c.env.SPOTIFY_CLIENT_ID, c.env.SPOTIFY_CLIENT_SECRET);
    const tokens: AuthTokens = await spotifyAuth.exchangeCodeForTokens(code, redirectUri, codeVerifier);

    // One-time state usage.
    await c.env.CACHE_KV.delete(`oauth_state:${state}`);

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
    }), { expirationTtl: SPOTIFY_SESSION_TTL_SECONDS });

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
        expires_in: SPOTIFY_SESSION_TTL_SECONDS,
        spotify_access_expires_in: tokens.expires_in,
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
      refresh_token: (newTokens as any).refresh_token || session.refresh_token,
      expires_at: Date.now() + (newTokens.expires_in * 1000)
    };

    await c.env.SESSIONS_KV.put(sessionId, JSON.stringify(updatedSession), {
      expirationTtl: SPOTIFY_SESSION_TTL_SECONDS
    });

    const user = c.get('user');
    const jwtService = new JWTService(c.env.JWT_SECRET);
    const jwtToken = await jwtService.generateToken({
      sub: user.id,
      email: user.email,
      name: user.name,
      session_id: sessionId,
    });

    return c.json({
      data: {
        token: jwtToken,
        access_token: jwtToken,
        expires_in: SPOTIFY_SESSION_TTL_SECONDS,
        spotify_access_expires_in: newTokens.expires_in,
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
  } catch {
    return c.json({ error: { code: 'LOGOUT_FAILED', message: 'Failed to logout' } }, 500);
  }
});

// GET /auth/me - Get current user info
app.get('/me', authMiddleware, async (c) => {
  try {
    const user = c.get('user');
    return c.json({ data: user });
  } catch {
    return c.json({ error: { code: 'USER_INFO_FAILED', message: 'Failed to get user info' } }, 500);
  }
});

export { app as authRoutes };

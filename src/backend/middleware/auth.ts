import { Context, Next } from 'hono';
import { HTTPException } from 'hono/http-exception';
import { JWTService } from '../services/jwt';
import { SpotifyAuthService } from '../services/spotify-auth';
import type { Env } from '../types/env';
import { SPOTIFY_SESSION_TTL_SECONDS } from '../types/auth';
import type { JWTPayload } from '../types/auth';
import type { Variables } from '../types/variables';

export const authMiddleware = async (c: Context<{ Bindings: Env; Variables: Variables }>, next: Next) => {
  const authHeader = c.req.header('Authorization');
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw new HTTPException(401, { message: 'Missing or invalid authorization header' });
  }
  
  const token = authHeader.substring(7);
  const jwtService = new JWTService(c.env.JWT_SECRET);
  
  try {
    const payload = await jwtService.verifyToken(token) as JWTPayload;
    
    // Get session data
    const sessionData = await c.env.SESSIONS_KV.get(payload.session_id);
    if (!sessionData) {
      throw new HTTPException(401, { message: 'Session expired or invalid' });
    }
    
    let session = JSON.parse(sessionData);

    // Refresh the Spotify access token transparently when it expires.
    if (Date.now() > session.expires_at) {
      if (!session.refresh_token) {
        throw new HTTPException(401, { message: 'Token expired' });
      }

      try {
        const spotifyAuth = new SpotifyAuthService(c.env.SPOTIFY_CLIENT_ID, c.env.SPOTIFY_CLIENT_SECRET);
        const refreshed = await spotifyAuth.refreshAccessToken(session.refresh_token);
        session = {
          ...session,
          access_token: refreshed.access_token,
          refresh_token: (refreshed as any).refresh_token || session.refresh_token,
          expires_at: Date.now() + (refreshed.expires_in * 1000),
        };

        await c.env.SESSIONS_KV.put(payload.session_id, JSON.stringify(session), {
          expirationTtl: SPOTIFY_SESSION_TTL_SECONDS,
        });
      } catch (refreshError) {
        console.error('Failed to refresh Spotify access token:', refreshError);
        throw new HTTPException(401, { message: 'Token expired' });
      }
    }
    
    // Add user and session info to context
    c.set('user', {
      id: payload.sub,
      email: payload.email,
      name: payload.name,
      session_id: payload.session_id
    });
    c.set('session_id', payload.session_id);
    c.set('access_token', session.access_token);
    
    await next();
  } catch (error) {
    if (error instanceof HTTPException) {
      throw error;
    }
    throw new HTTPException(401, { message: 'Invalid token' });
  }
};

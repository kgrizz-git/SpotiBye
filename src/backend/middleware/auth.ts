import { Context, Next } from 'hono';
import { HTTPException } from 'hono/http-exception';
import { JWTService } from '../services/jwt';
import { SpotifyAuthService } from '../services/spotify-auth';
import type { Env } from '../types/env';
import { SPOTIFY_SESSION_TTL_SECONDS } from '../types/auth';
import type { Variables } from '../types/variables';
import type { AuthTokenResponse } from '../types/spotify-api';

export interface SessionData {
  user_id: string;
  access_token: string;
  refresh_token?: string;
  expires_at: number;
}

export function safeParseSession(raw: string | null, logContext = 'unknown'): SessionData | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      typeof parsed.user_id === 'string' &&
      typeof parsed.access_token === 'string' &&
      typeof parsed.expires_at === 'number'
    ) {
      return parsed as SessionData;
    }
    console.error(`Session schema validation failed for session ${logContext.substring(0, 8)}`);
    return null;
  } catch (err) {
    console.error(`Session JSON parse failed for session ${logContext.substring(0, 8)}:`, err);
    return null;
  }
}

const refreshPromises = new Map<string, Promise<AuthTokenResponse>>();

export const authMiddleware = async (c: Context<{ Bindings: Env; Variables: Variables }>, next: Next) => {
  const authHeader = c.req.header('Authorization');

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw new HTTPException(401, { message: 'Missing or invalid authorization header' });
  }

  const token = authHeader.substring(7);
  const jwtService = new JWTService(c.env.JWT_SECRET);

  try {
    const payload = await jwtService.verifyToken(token);

    // Get session data
    const sessionData = await c.env.SESSIONS_KV.get(payload.session_id);
    let session = safeParseSession(sessionData, payload.session_id);
    if (!session) {
      throw new HTTPException(401, { message: 'Session expired or invalid' });
    }

    // Refresh the Spotify access token transparently when it expires.
    if (Date.now() > session.expires_at) {
      if (!session.refresh_token) {
        throw new HTTPException(401, { message: 'Token expired' });
      }

      try {
        let refreshPromise = refreshPromises.get(payload.session_id);
        if (!refreshPromise) {
          const spotifyAuth = new SpotifyAuthService(c.env.SPOTIFY_CLIENT_ID, c.env.SPOTIFY_CLIENT_SECRET);
          refreshPromise = spotifyAuth.refreshAccessToken(session.refresh_token);
          refreshPromises.set(payload.session_id, refreshPromise);
        }

        const refreshed = await refreshPromise;
        session = {
          ...session,
          access_token: refreshed.access_token,
          refresh_token: refreshed.refresh_token || session.refresh_token,
          expires_at: Date.now() + (refreshed.expires_in * 1000),
        };

        await c.env.SESSIONS_KV.put(payload.session_id, JSON.stringify(session), {
          expirationTtl: SPOTIFY_SESSION_TTL_SECONDS,
        });
      } catch (refreshError) {
        console.error('Failed to refresh Spotify access token:', refreshError);
        throw new HTTPException(401, { message: 'Token expired' });
      } finally {
        refreshPromises.delete(payload.session_id);
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

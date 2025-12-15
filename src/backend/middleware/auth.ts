import { Context, Next } from 'hono';
import { HTTPException } from 'hono/http-exception';
import { JWTService } from '../services/jwt';
import type { Env } from '../types/env';
import type { JWTPayload } from '../types/auth';

const jwtService = new JWTService();

export const authMiddleware = async (c: Context<{ Bindings: Env }>, next: Next) => {
  const authHeader = c.req.header('Authorization');
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw new HTTPException(401, { message: 'Missing or invalid authorization header' });
  }
  
  const token = authHeader.substring(7);
  
  try {
    const payload = jwtService.verifyToken(token) as JWTPayload;
    
    // Get session data
    const sessionData = await c.env.SESSIONS_KV.get(payload.session_id);
    if (!sessionData) {
      throw new HTTPException(401, { message: 'Session expired or invalid' });
    }
    
    const session = JSON.parse(sessionData);
    
    // Check if token is still valid
    if (Date.now() > session.expires_at) {
      throw new HTTPException(401, { message: 'Token expired' });
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

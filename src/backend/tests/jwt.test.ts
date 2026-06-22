import { describe, it, expect, beforeEach } from 'vitest';
import { JWTService } from '../services/jwt';

describe('JWTService', () => {
  let jwt: JWTService;
  const SECRET = 'test-jwt-secret-for-testing-only';

  beforeEach(() => {
    jwt = new JWTService(SECRET);
  });

  describe('verifyToken expiration handling', () => {
    it('accepts a freshly-issued token', async () => {
      const token = await jwt.generateToken({
        sub: 'user-1',
        email: 'user@example.com',
        name: 'Test User',
        session_id: 'test-session',
      });

      const payload = await jwt.verifyToken(token);

      expect(payload.sub).toBe('user-1');
      expect(payload.exp).toBeGreaterThan(Math.floor(Date.now() / 1000));
    });

    it('rejects a token with exp = 0 (forged bypass case)', async () => {
      // Build a token whose payload has `exp: 0`. We hand-roll this because
      // generateToken() always sets a future exp. The previous
      // `if (decodedPayload.exp && ...)` truthy check accepted this case
      // because 0 is falsy; the explicit-undefined check rejects it.
      const header = { alg: 'HS256', typ: 'JWT' };
      const fullPayload = {
        sub: 'user-1',
        email: 'user@example.com',
        name: 'Test User',
        iat: Math.floor(Date.now() / 1000),
        exp: 0,
      };

      const base64UrlEncode = (data: string): string => {
        const bytes = new TextEncoder().encode(data);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary)
          .replace(/\+/g, '-')
          .replace(/\//g, '_')
          .replace(/=/g, '');
      };

      const encodedHeader = base64UrlEncode(JSON.stringify(header));
      const encodedPayload = base64UrlEncode(JSON.stringify(fullPayload));

      const encoder = new TextEncoder();
      const keyData = encoder.encode(SECRET);
      const messageData = encoder.encode(`${encodedHeader}.${encodedPayload}`);

      const key = await crypto.subtle.importKey(
        'raw',
        keyData,
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['sign']
      );
      const sigBytes = new Uint8Array(
        await crypto.subtle.sign('HMAC', key, messageData)
      );
      let binary = '';
      for (let i = 0; i < sigBytes.length; i++) {
        binary += String.fromCharCode(sigBytes[i]);
      }
      const signature = btoa(binary)
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=/g, '');

      const forgedToken = `${encodedHeader}.${encodedPayload}.${signature}`;

      await expect(jwt.verifyToken(forgedToken)).rejects.toThrow('Token expired');
    });

    it('rejects a token with an expired exp', async () => {
      const header = { alg: 'HS256', typ: 'JWT' };
      const now = Math.floor(Date.now() / 1000);
      const fullPayload = {
        sub: 'user-1',
        email: 'user@example.com',
        name: 'Test User',
        iat: now - 7200,
        exp: now - 3600,
      };

      const base64UrlEncode = (data: string): string => {
        const bytes = new TextEncoder().encode(data);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        return btoa(binary)
          .replace(/\+/g, '-')
          .replace(/\//g, '_')
          .replace(/=/g, '');
      };

      const encodedHeader = base64UrlEncode(JSON.stringify(header));
      const encodedPayload = base64UrlEncode(JSON.stringify(fullPayload));

      const encoder = new TextEncoder();
      const keyData = encoder.encode(SECRET);
      const messageData = encoder.encode(`${encodedHeader}.${encodedPayload}`);

      const key = await crypto.subtle.importKey(
        'raw',
        keyData,
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['sign']
      );
      const sigBytes = new Uint8Array(
        await crypto.subtle.sign('HMAC', key, messageData)
      );
      let binary = '';
      for (let i = 0; i < sigBytes.length; i++) {
        binary += String.fromCharCode(sigBytes[i]);
      }
      const signature = btoa(binary)
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=/g, '');

      const expiredToken = `${encodedHeader}.${encodedPayload}.${signature}`;

      await expect(jwt.verifyToken(expiredToken)).rejects.toThrow('Token expired');
    });

    it('throws if JWT_SECRET is missing', () => {
      expect(() => new JWTService('')).toThrow('JWT_SECRET is required');
    });
  });
});

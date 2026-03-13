import { APP_JWT_TTL_SECONDS } from '../types/auth';
import type { JWTPayload } from '../types/auth';

export class JWTService {
  private secret: string;
  
  constructor(secret?: string) {
    this.secret = secret || 'default-secret';
  }
  
  async generateToken(payload: Omit<JWTPayload, 'iat' | 'exp'>): Promise<string> {
    const header = { alg: 'HS256', typ: 'JWT' };
    const now = Math.floor(Date.now() / 1000);
    const fullPayload = {
      ...payload,
      iat: now,
      exp: now + APP_JWT_TTL_SECONDS
    };
    
    const encodedHeader = this.base64UrlEncode(JSON.stringify(header));
    const encodedPayload = this.base64UrlEncode(JSON.stringify(fullPayload));
    
    const signature = await this.sign(`${encodedHeader}.${encodedPayload}`, this.secret);
    
    return `${encodedHeader}.${encodedPayload}.${signature}`;
  }
  
  async verifyToken(token: string): Promise<JWTPayload> {
    const parts = token.split('.');
    if (parts.length !== 3) {
      throw new Error('Invalid token format');
    }
    
    const [header, payload, signature] = parts;
    
    // Verify signature
    const expectedSignature = await this.sign(`${header}.${payload}`, this.secret);
    if (signature !== expectedSignature) {
      throw new Error('Invalid signature');
    }
    
    // Decode payload
    const decodedPayload = JSON.parse(this.base64UrlDecode(payload));
    
    // Check expiration
    const now = Math.floor(Date.now() / 1000);
    if (decodedPayload.exp && decodedPayload.exp < now) {
      throw new Error('Token expired');
    }
    
    return decodedPayload;
  }
  
  private async sign(data: string, secret: string): Promise<string> {
    // Simple HMAC-SHA256 implementation for Workers
    const encoder = new TextEncoder();
    const keyData = encoder.encode(secret);
    const messageData = encoder.encode(data);
    
    const key = await crypto.subtle.importKey(
      'raw',
      keyData,
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    
    const signature = await crypto.subtle.sign('HMAC', key, messageData);
    return this.base64UrlEncode(new Uint8Array(signature));
  }
  
  private base64UrlEncode(data: string | Uint8Array): string {
    if (typeof data === 'string') {
      data = new TextEncoder().encode(data);
    }
    return btoa(String.fromCharCode(...data))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');
  }
  
  private base64UrlDecode(data: string): string {
    data += '='.repeat((4 - data.length % 4) % 4);
    data = data.replace(/\-/g, '+').replace(/_/g, '/');
    return atob(data);
  }
}

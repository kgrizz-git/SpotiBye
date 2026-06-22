import type { AuthTokens } from '../types/auth';
import type { SpotifyUser } from '../types/spotify';
import type { AuthTokenResponse } from '../types/spotify-api';

export class SpotifyAuthService {
  private clientId: string;
  private clientSecret: string;
  private redirectUri: string = '';

  constructor(clientId?: string, clientSecret?: string) {
    if (!clientId) {
      throw new Error('Spotify clientId and clientSecret are required');
    }
    if (!clientSecret) {
      throw new Error('Spotify clientId and clientSecret are required');
    }
    this.clientId = clientId;
    this.clientSecret = clientSecret;
  }

  getAuthUrl(redirectUri: string, state?: string, codeChallenge?: string): string {
    const scopes = [
      'user-read-private',
      'user-read-email',
      'playlist-read-private',
      'playlist-read-collaborative'
    ].join(' ');

    const params = new URLSearchParams({
      response_type: 'code',
      client_id: this.clientId,
      scope: scopes,
      redirect_uri: redirectUri,
      state: state || this.generateState()
    });

    // PKCE: bind the authorization request to a verifier held server-side.
    if (codeChallenge) {
      params.set('code_challenge_method', 'S256');
      params.set('code_challenge', codeChallenge);
    }

    return `https://accounts.spotify.com/authorize?${params.toString()}`;
  }

  generateState(): string {
    return crypto.randomUUID();
  }

  /**
   * Generate a high-entropy PKCE code_verifier (RFC 7636): 43-128 chars from the
   * unreserved set. We emit 43 base64url chars (32 random bytes).
   */
  generateCodeVerifier(): string {
    const bytes = new Uint8Array(32);
    crypto.getRandomValues(bytes);
    return SpotifyAuthService.base64UrlEncode(bytes.buffer);
  }

  /** Derive the S256 code_challenge for a verifier: base64url(SHA-256(verifier)). */
  async computeCodeChallenge(codeVerifier: string): Promise<string> {
    const data = new TextEncoder().encode(codeVerifier);
    const digest = await crypto.subtle.digest('SHA-256', data);
    return SpotifyAuthService.base64UrlEncode(digest);
  }

  private static base64UrlEncode(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.length; i += 1) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  async exchangeCodeForTokens(code: string, redirectUri?: string, codeVerifier?: string): Promise<AuthTokens> {
    const callbackUri = redirectUri || this.redirectUri;

    if (!callbackUri) {
      throw new Error('Missing redirect URI for token exchange');
    }

    const body = new URLSearchParams({
      grant_type: 'authorization_code',
      code: code,
      redirect_uri: callbackUri
    });
    if (codeVerifier) {
      body.set('code_verifier', codeVerifier);
    }

    const response = await fetch('https://accounts.spotify.com/api/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': `Basic ${this.getBasicAuth()}`
      },
      body
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to exchange code for tokens: ${error}`);
    }

    return await response.json();
  }

  async refreshAccessToken(refreshToken: string): Promise<AuthTokenResponse> {
    const response = await fetch('https://accounts.spotify.com/api/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': `Basic ${this.getBasicAuth()}`
      },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: refreshToken
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to refresh token: ${error}`);
    }

    return await response.json();
  }

  async getUserProfile(accessToken: string): Promise<SpotifyUser> {
    const response = await fetch('https://api.spotify.com/v1/me', {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to get user profile: ${error}`);
    }

    return await response.json();
  }

  private getBasicAuth(): string {
    const credentials = `${this.clientId}:${this.clientSecret}`;
    return btoa(credentials);
  }
}

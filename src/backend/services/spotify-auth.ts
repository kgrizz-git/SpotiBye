import type { AuthTokens } from '../types/auth';
import type { SpotifyUser } from '../types/spotify';

export class SpotifyAuthService {
  private clientId: string;
  private clientSecret: string;
  private redirectUri: string;
  
  constructor(clientId?: string, clientSecret?: string) {
    this.clientId = clientId || process.env.SPOTIFY_CLIENT_ID || '';
    this.clientSecret = clientSecret || process.env.SPOTIFY_CLIENT_SECRET || '';
  }
  
  getAuthUrl(redirectUri: string, state?: string): string {
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
    
    return `https://accounts.spotify.com/authorize?${params.toString()}`;
  }
  
  generateState(): string {
    return crypto.randomUUID();
  }
  
  async exchangeCodeForTokens(code: string): Promise<AuthTokens> {
    const response = await fetch('https://accounts.spotify.com/api/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': `Basic ${this.getBasicAuth()}`
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code: code,
        redirect_uri: this.redirectUri
      })
    });
    
    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Failed to exchange code for tokens: ${error}`);
    }
    
    return await response.json();
  }
  
  async refreshAccessToken(refreshToken: string): Promise<Omit<AuthTokens, 'refresh_token'>> {
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

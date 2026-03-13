export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
  scope: string;
}

export const SPOTIFY_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30;
export const APP_JWT_TTL_SECONDS = SPOTIFY_SESSION_TTL_SECONDS;

export interface JWTPayload {
  sub: string;
  email?: string;
  name: string;
  session_id: string;
  iat: number;
  exp: number;
}

export interface SessionData {
  user_id: string;
  access_token: string;
  refresh_token: string;
  expires_at: number;
  spotify_data: any;
}

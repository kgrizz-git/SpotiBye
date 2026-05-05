export interface Env {
  // Environment variables
  ENVIRONMENT: string;

  // Spotify credentials
  SPOTIFY_CLIENT_ID: string;
  SPOTIFY_CLIENT_SECRET: string;

  // JWT secret
  JWT_SECRET: string;

  // KV namespaces
  CACHE_KV: KVNamespace;
  SESSIONS_KV: KVNamespace;

  // Test/mock keys
  RECOCOBEATS_API_KEY?: string;
}

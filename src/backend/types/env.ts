import type { AnalysisQueueMessage } from './analysis-queue';

export interface Env {
  // Environment variables
  ENVIRONMENT: string;
  // Deployment metadata injected by deploy scripts and GitHub Actions.
  RELEASE_SHA?: string;
  RELEASE_VERSION?: string;
  DEPLOYED_AT?: string;

  // Spotify credentials
  SPOTIFY_CLIENT_ID: string;
  SPOTIFY_CLIENT_SECRET: string;

  // JWT secret
  JWT_SECRET: string;

  // Comma-separated allowlist of OAuth `redirect_uri` values that the
  // `/auth/spotify/login` endpoint will accept. Empty/missing rejects all
  // (fail-closed). Format: "https://app.example.com,http://localhost:3000".
  ALLOWED_REDIRECT_URIS: string;

  // Optional override for cached analysis-results TTL (seconds). Falls back
  // to `ANALYSIS_RESULTS_TTL_SECONDS` in utils/constants.ts when unset.
  ANALYSIS_RESULTS_TTL_SECONDS?: string;

  // KV namespaces
  CACHE_KV: KVNamespace;
  SESSIONS_KV: KVNamespace;

  // Durable Object namespaces
  ANALYSIS_STATUS: DurableObjectNamespace;

  // Queue bindings
  ANALYSIS_QUEUE: Queue<AnalysisQueueMessage>;
}

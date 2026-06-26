# Analysis Queue Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Move backend playlist analysis from best-effort `executionCtx.waitUntil(...)` work to Cloudflare Queues so large playlists can retry and complete without request lifetime coupling.

**Architecture:** Keep the existing Hono HTTP API and queue consumer in the same Worker module by exporting both `fetch` and `queue` from `src/backend/index.ts`. The POST route writes a queued status, sends a small queue message containing stable identifiers, and the consumer refreshes or loads the Spotify access token from `SESSIONS_KV` before running `AnalysisService`.

**Tech Stack:** Cloudflare Workers, Cloudflare Queues, TypeScript, Hono, Vitest, Spotify OAuth refresh tokens, KV-backed status/result storage.

---

## Design Decisions

- Use one Worker module: `src/backend/index.ts` exports `fetch` and `queue`. This keeps deployment simple and lets the queue consumer share `Env`, `CacheService`, and analysis code.
- Add one queue binding named `ANALYSIS_QUEUE`. It is both the producer binding used by the POST route and the consumer queue for this Worker.
- Do not enqueue Spotify access tokens. Queue messages can sit before processing; access tokens can expire. Enqueue `session_id` and refresh/load the token in the consumer.
- Use KV compare-by-current-job semantics for idempotency. A duplicate delivery for an old `job_id` exits without overwriting a newer job, and a duplicate delivery after completion acknowledges successfully.
- Status transitions are visible to clients: `queued -> processing -> completed`; permanent failures write `failed`, while retryable failures write `retrying` and rethrow so Cloudflare Queues retries the message.
- Preserve result shape and keys:
  - `analysis:{playlistId}:{userId}:status`
  - `analysis:{playlistId}:{userId}:results`

Cloudflare references checked on 2026-06-19:

- `https://developers.cloudflare.com/queues/configuration/configure-queues/`
- `https://developers.cloudflare.com/queues/configuration/javascript-apis/`
- `https://developers.cloudflare.com/queues/configuration/dead-letter-queues/`
- `https://developers.cloudflare.com/queues/configuration/batching-retries/`

## File Structure

- Create `src/backend/types/analysis-queue.ts`: queue message, status, and result-facing helper types.
- Create `src/backend/services/analysis-job.ts`: shared job runner used by the queue consumer; owns token lookup/refresh, status writes, result writes, and idempotency checks.
- Modify `src/backend/types/env.ts`: add `ANALYSIS_QUEUE: Queue<AnalysisQueueMessage>`.
- Modify `src/backend/routes/analysis.ts`: enqueue messages instead of starting the full analysis in `waitUntil`.
- Modify `src/backend/index.ts`: export the queue consumer in the same Worker module as `fetch`.
- Modify `src/backend/wrangler.toml`: add development and production queue producer/consumer bindings.
- Modify `src/backend/tests/analysis.test.ts`: update POST route tests from processing/waitUntil to queued/send behavior.
- Create `src/backend/tests/analysis-queue.test.ts`: queue consumer, retry, duplicate, stale job, and persistence tests.
- Modify `src/backend/docs/deployment-configuration.md`: document queue creation and deployment requirements.
- Modify `CHANGELOG.md`: record the user-visible reliability improvement.

## Task 1: Add Queue Types and Env Binding

**Files:**
- Create: `src/backend/types/analysis-queue.ts`
- Modify: `src/backend/types/env.ts`
- Test: `src/backend/tests/analysis-queue.test.ts`

- [x] **Step 1: Write the failing type-focused test**

Add this file:

```ts
import { describe, expect, it, vi } from 'vitest';
import type { Env } from '../types/env';

describe('analysis queue env binding', () => {
  it('accepts the ANALYSIS_QUEUE binding used by route and consumer tests', async () => {
    const env = {
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'client-id',
      SPOTIFY_CLIENT_SECRET: 'client-secret',
      JWT_SECRET: 'jwt-secret',
      CACHE_KV: {} as KVNamespace,
      SESSIONS_KV: {} as KVNamespace,
      ANALYSIS_QUEUE: {
        send: vi.fn(async () => undefined),
      } as unknown as Queue,
    } satisfies Env;

    await env.ANALYSIS_QUEUE.send({
      job_id: 'job-1',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      session_id: 'session-1',
      enqueued_at: '2026-06-19T00:00:00.000Z',
      attempt: 0,
    });

    expect(env.ANALYSIS_QUEUE.send).toHaveBeenCalledTimes(1);
  });
});
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis-queue.test.ts
```

Expected: TypeScript/Vitest fails because `Env` does not include `ANALYSIS_QUEUE` and `AnalysisQueueMessage` is not defined yet.

- [x] **Step 3: Add queue message and status types**

Create `src/backend/types/analysis-queue.ts`:

```ts
export interface AnalysisQueueMessage {
  job_id: string;
  playlist_id: string;
  user_id: string;
  session_id: string;
  enqueued_at: string;
  attempt: number;
}

export type AnalysisJobStatus =
  | 'queued'
  | 'processing'
  | 'retrying'
  | 'completed'
  | 'failed';

export interface AnalysisStatusRecord {
  job_id: string;
  playlist_id: string;
  user_id: string;
  status: AnalysisJobStatus;
  progress: number;
  queued_at?: string;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  retry_after?: string;
  attempt?: number;
  error?: string;
}
```

Modify `src/backend/types/env.ts`:

```ts
import type { AnalysisQueueMessage } from './analysis-queue';

export interface Env {
  ENVIRONMENT: string;
  SPOTIFY_CLIENT_ID: string;
  SPOTIFY_CLIENT_SECRET: string;
  JWT_SECRET: string;
  CACHE_KV: KVNamespace;
  SESSIONS_KV: KVNamespace;
  ANALYSIS_QUEUE: Queue<AnalysisQueueMessage>;
}
```

- [x] **Step 4: Run the test to verify it passes**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis-queue.test.ts
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add src/backend/types/analysis-queue.ts src/backend/types/env.ts src/backend/tests/analysis-queue.test.ts
git commit -m "feat: type analysis queue binding"
```

## Task 2: Configure Cloudflare Queues

**Files:**
- Modify: `src/backend/wrangler.toml`
- Test: `src/backend/wrangler.toml`

- [x] **Step 1: Add queue configuration**

Modify `src/backend/wrangler.toml` so the top-level, development, and production sections include the queue producer and consumer bindings:

```toml
[[queues.producers]]
binding = "ANALYSIS_QUEUE"
queue = "spotibye-analysis"

[[queues.consumers]]
queue = "spotibye-analysis"
max_batch_size = 1
max_batch_timeout = 5
max_retries = 3
dead_letter_queue = "spotibye-analysis-dlq"

[[env.development.queues.producers]]
binding = "ANALYSIS_QUEUE"
queue = "spotibye-analysis-dev"

[[env.development.queues.consumers]]
queue = "spotibye-analysis-dev"
max_batch_size = 1
max_batch_timeout = 5
max_retries = 3
dead_letter_queue = "spotibye-analysis-dev-dlq"

[[env.production.queues.producers]]
binding = "ANALYSIS_QUEUE"
queue = "spotibye-analysis"

[[env.production.queues.consumers]]
queue = "spotibye-analysis"
max_batch_size = 1
max_batch_timeout = 5
max_retries = 3
dead_letter_queue = "spotibye-analysis-dlq"
```

- [x] **Step 2: Validate Wrangler config**

Run:

```bash
cd src/backend && npx wrangler deploy --dry-run
```

Expected: Wrangler parses `wrangler.toml`. If queue resources do not exist yet, create them with:

```bash
cd src/backend
npx wrangler queues create spotibye-analysis-dev
npx wrangler queues create spotibye-analysis-dev-dlq
npx wrangler queues create spotibye-analysis
npx wrangler queues create spotibye-analysis-dlq
```

Then rerun:

```bash
cd src/backend && npx wrangler deploy --dry-run
```

Expected: dry run succeeds.

- [x] **Step 3: Commit**

Run:

```bash
git add src/backend/wrangler.toml
git commit -m "chore: configure analysis queue bindings"
```

## Task 3: Extract Idempotent Analysis Job Runner

**Files:**
- Create: `src/backend/services/analysis-job.ts`
- Modify: `src/backend/services/analysis.ts`
- Test: `src/backend/tests/analysis-queue.test.ts`

- [x] **Step 1: Add failing tests for completed, stale, and token-refresh behavior**

Append these tests to `src/backend/tests/analysis-queue.test.ts`:

```ts
import { AnalysisJobService } from '../services/analysis-job';
import { AnalysisService } from '../services/analysis';

const kvNamespace = (initial: Record<string, unknown> = {}) => {
  const store = new Map(
    Object.entries(initial).map(([key, value]) => [key, JSON.stringify(value)])
  );

  return {
    get: vi.fn(async (key: string) => store.get(key) ?? null),
    put: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    delete: vi.fn(async (key: string) => {
      store.delete(key);
    }),
    list: vi.fn(async () => ({ keys: [] })),
  } as unknown as KVNamespace;
};

describe('AnalysisJobService', () => {
  it('persists completed results and completed status for the current job', async () => {
    const statusKey = 'analysis:playlist-1:user-1:status';
    const resultsKey = 'analysis:playlist-1:user-1:results';
    const cacheKv = kvNamespace({
      [statusKey]: {
        job_id: 'job-1',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'queued',
        progress: 0,
      },
    });
    const sessionsKv = kvNamespace({
      'session-1': {
        user_id: 'user-1',
        access_token: 'fresh-token',
        refresh_token: 'refresh-token',
        expires_at: Date.now() + 3_600_000,
      },
    });
    const result = {
      job_id: 'job-1',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      status: 'completed',
      computed_at: '2026-06-19T00:00:00.000Z',
      completed_at: '2026-06-19T00:00:01.000Z',
      overview: {
        total_tracks: 1,
        total_duration_ms: 180000,
        average_duration_ms: 180000,
        formatted_duration: '3m 0s',
      },
      artists: {
        unique_artists: 1,
        top_artists: [{ artist: 'Artist 1', count: 1 }],
        diversity: 1,
      },
      genre_distribution: {},
      insights: [],
    };
    vi.spyOn(AnalysisService.prototype, 'analyzePlaylist').mockResolvedValue(result);

    const service = new AnalysisJobService({
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'client-id',
      SPOTIFY_CLIENT_SECRET: 'client-secret',
      JWT_SECRET: 'jwt-secret',
      CACHE_KV: cacheKv,
      SESSIONS_KV: sessionsKv,
      ANALYSIS_QUEUE: { send: vi.fn() } as unknown as Queue,
    });

    const outcome = await service.process({
      job_id: 'job-1',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      session_id: 'session-1',
      enqueued_at: '2026-06-19T00:00:00.000Z',
      attempt: 0,
    });

    expect(outcome).toEqual({ acknowledged: true, reason: 'completed' });
    expect(cacheKv.put).toHaveBeenCalledWith(resultsKey, JSON.stringify(result), { expirationTtl: 86400 });
    expect(cacheKv.put).toHaveBeenCalledWith(
      statusKey,
      expect.stringContaining('"status":"completed"'),
      { expirationTtl: 3600 }
    );
  });

  it('acknowledges stale duplicate deliveries without overwriting a newer job', async () => {
    const statusKey = 'analysis:playlist-1:user-1:status';
    const cacheKv = kvNamespace({
      [statusKey]: {
        job_id: 'job-newer',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'queued',
        progress: 0,
      },
    });
    const service = new AnalysisJobService({
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'client-id',
      SPOTIFY_CLIENT_SECRET: 'client-secret',
      JWT_SECRET: 'jwt-secret',
      CACHE_KV: cacheKv,
      SESSIONS_KV: kvNamespace(),
      ANALYSIS_QUEUE: { send: vi.fn() } as unknown as Queue,
    });
    const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist');

    const outcome = await service.process({
      job_id: 'job-old',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      session_id: 'session-1',
      enqueued_at: '2026-06-19T00:00:00.000Z',
      attempt: 0,
    });

    expect(outcome).toEqual({ acknowledged: true, reason: 'stale' });
    expect(analyzeSpy).not.toHaveBeenCalled();
  });

  it('refreshes an expired session token before analyzing', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      access_token: 'refreshed-token',
      expires_in: 3600,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })));
    const cacheKv = kvNamespace({
      'analysis:playlist-1:user-1:status': {
        job_id: 'job-1',
        playlist_id: 'playlist-1',
        user_id: 'user-1',
        status: 'queued',
        progress: 0,
      },
    });
    const sessionsKv = kvNamespace({
      'session-1': {
        user_id: 'user-1',
        access_token: 'expired-token',
        refresh_token: 'refresh-token',
        expires_at: Date.now() - 1000,
      },
    });
    const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist').mockResolvedValue({
      job_id: 'job-1',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      status: 'completed',
      computed_at: '2026-06-19T00:00:00.000Z',
      completed_at: '2026-06-19T00:00:01.000Z',
      overview: { total_tracks: 0, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
      artists: { unique_artists: 0, top_artists: [], diversity: 0 },
      genre_distribution: {},
      insights: [],
    });

    const service = new AnalysisJobService({
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'client-id',
      SPOTIFY_CLIENT_SECRET: 'client-secret',
      JWT_SECRET: 'jwt-secret',
      CACHE_KV: cacheKv,
      SESSIONS_KV: sessionsKv,
      ANALYSIS_QUEUE: { send: vi.fn() } as unknown as Queue,
    });

    await service.process({
      job_id: 'job-1',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      session_id: 'session-1',
      enqueued_at: '2026-06-19T00:00:00.000Z',
      attempt: 0,
    });

    expect(analyzeSpy.mock.instances[0]).toBeInstanceOf(AnalysisService);
    expect(fetch).toHaveBeenCalledWith(
      'https://accounts.spotify.com/api/token',
      expect.objectContaining({ method: 'POST' })
    );
    expect(sessionsKv.put).toHaveBeenCalledWith(
      'session-1',
      expect.stringContaining('"access_token":"refreshed-token"'),
      { expirationTtl: 2592000 }
    );
  });
});
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis-queue.test.ts
```

Expected: FAIL because `AnalysisJobService` does not exist.

- [x] **Step 3: Export the analysis result type**

Modify `src/backend/services/analysis.ts` so `AnalysisResult` can be reused by the job runner:

```ts
export interface AnalysisResult {
  job_id: string;
  playlist_id: string;
  user_id: string;
  status: string;
  computed_at: string;
  completed_at: string;
  overview?: {
    total_tracks: number;
    total_duration_ms: number;
    average_duration_ms: number;
    formatted_duration: string;
  };
  artists?: {
    unique_artists: number;
    top_artists: Array<{ artist: string; count: number }>;
    diversity: number;
  };
  genre_distribution?: Record<string, { count: number; percentage: number }>;
  audio_features?: AudioFeatureSummary;
  insights?: string[];
}
```

- [x] **Step 4: Implement the job runner**

Create `src/backend/services/analysis-job.ts`:

```ts
import { AnalysisService, type AnalysisResult } from './analysis';
import { CacheService } from './cache';
import { SpotifyAuthService } from './spotify-auth';
import { SPOTIFY_SESSION_TTL_SECONDS } from '../types/auth';
import type { AnalysisQueueMessage, AnalysisStatusRecord } from '../types/analysis-queue';
import type { AuthTokenResponse } from '../types/spotify-api';
import type { Env } from '../types/env';

interface SessionRecord {
  user_id: string;
  access_token: string;
  refresh_token?: string;
  expires_at: number;
}

export interface AnalysisJobOutcome {
  acknowledged: boolean;
  reason: 'completed' | 'stale' | 'already-completed';
}

export class AnalysisJobService {
  private cache: CacheService;

  constructor(private env: Env) {
    this.cache = new CacheService(env.CACHE_KV);
  }

  async process(message: AnalysisQueueMessage): Promise<AnalysisJobOutcome> {
    const statusKey = this.statusKey(message);
    const resultsKey = this.resultsKey(message);
    const current = await this.cache.get<AnalysisStatusRecord>(statusKey);

    if (!current || current.job_id !== message.job_id) {
      return { acknowledged: true, reason: 'stale' };
    }

    if (current.status === 'completed') {
      return { acknowledged: true, reason: 'already-completed' };
    }

    await this.writeStatus(statusKey, {
      ...current,
      status: 'processing',
      progress: 10,
      started_at: new Date().toISOString(),
      attempt: message.attempt,
    });

    try {
      const accessToken = await this.getAccessToken(message.session_id);
      const analysis = new AnalysisService(accessToken);
      const result = await analysis.analyzePlaylist(
        message.playlist_id,
        message.user_id,
        message.job_id
      );

      await this.cache.set(resultsKey, result satisfies AnalysisResult, 86400);
      await this.writeStatus(statusKey, {
        ...current,
        status: 'completed',
        progress: 100,
        completed_at: new Date().toISOString(),
        attempt: message.attempt,
      });

      return { acknowledged: true, reason: 'completed' };
    } catch (error) {
      await this.writeStatus(statusKey, {
        ...current,
        status: 'retrying',
        progress: current.progress,
        retry_after: new Date(Date.now() + 60_000).toISOString(),
        attempt: message.attempt + 1,
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  async markFailed(message: AnalysisQueueMessage, error: unknown): Promise<void> {
    const statusKey = this.statusKey(message);
    const current = await this.cache.get<AnalysisStatusRecord>(statusKey);
    if (!current || current.job_id !== message.job_id || current.status === 'completed') {
      return;
    }

    await this.writeStatus(statusKey, {
      ...current,
      status: 'failed',
      progress: current.progress,
      failed_at: new Date().toISOString(),
      attempt: message.attempt,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  private async getAccessToken(sessionId: string): Promise<string> {
    const raw = await this.env.SESSIONS_KV.get(sessionId);
    if (!raw) {
      throw new Error('Analysis session not found');
    }

    let session = JSON.parse(raw) as SessionRecord;
    if (Date.now() <= session.expires_at) {
      return session.access_token;
    }

    if (!session.refresh_token) {
      throw new Error('Analysis session has no refresh token');
    }

    const spotifyAuth = new SpotifyAuthService(
      this.env.SPOTIFY_CLIENT_ID,
      this.env.SPOTIFY_CLIENT_SECRET
    );
    const refreshed = await spotifyAuth.refreshAccessToken(session.refresh_token) as AuthTokenResponse;
    session = {
      ...session,
      access_token: refreshed.access_token,
      refresh_token: refreshed.refresh_token || session.refresh_token,
      expires_at: Date.now() + refreshed.expires_in * 1000,
    };

    await this.env.SESSIONS_KV.put(sessionId, JSON.stringify(session), {
      expirationTtl: SPOTIFY_SESSION_TTL_SECONDS,
    });

    return session.access_token;
  }

  private async writeStatus(key: string, status: AnalysisStatusRecord): Promise<void> {
    await this.cache.set(key, status, 3600);
  }

  private statusKey(message: AnalysisQueueMessage): string {
    return `analysis:${message.playlist_id}:${message.user_id}:status`;
  }

  private resultsKey(message: AnalysisQueueMessage): string {
    return `analysis:${message.playlist_id}:${message.user_id}:results`;
  }
}
```

- [x] **Step 5: Run tests to verify they pass**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis-queue.test.ts
```

Expected: PASS.

- [x] **Step 6: Commit**

Run:

```bash
git add src/backend/services/analysis.ts src/backend/services/analysis-job.ts src/backend/tests/analysis-queue.test.ts
git commit -m "feat: add idempotent analysis job runner"
```

## Task 4: Enqueue Analysis Jobs From the Route

**Files:**
- Modify: `src/backend/routes/analysis.ts`
- Reference: `src/backend/types/variables.ts`
- Test: `src/backend/tests/analysis.test.ts`

- [x] **Step 1: Update failing POST route test**

In `src/backend/tests/analysis.test.ts`, update `mockEnv` so it includes:

```ts
ANALYSIS_QUEUE: {
  send: vi.fn().mockResolvedValue(undefined),
} as unknown as Queue,
```

Replace the waitUntil test with:

```ts
it('writes queued status and enqueues the analysis job without running analysis inline', async () => {
  const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist');
  const request = new Request('http://localhost/analysis/playlist/playlist1', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer test-jwt-token',
      'Content-Type': 'application/json',
    },
  });

  const response = await app.request(request, undefined, mockEnv);
  const data = (await response.json()) as any;

  expect(response.status).toBe(200);
  expect(data.data).toMatchObject({
    playlist_id: 'playlist1',
    user_id: 'test-user-id',
    status: 'queued',
    progress: 0,
  });
  expect(mockEnv.CACHE_KV.put).toHaveBeenCalledWith(
    'analysis:playlist1:test-user-id:status',
    expect.stringContaining('"status":"queued"'),
    { expirationTtl: 3600 }
  );
  expect(mockEnv.ANALYSIS_QUEUE.send).toHaveBeenCalledWith(expect.objectContaining({
    playlist_id: 'playlist1',
    user_id: 'test-user-id',
    session_id: 'test-session-id',
    attempt: 0,
  }));
  expect(analyzeSpy).not.toHaveBeenCalled();
});
```

- [x] **Step 2: Run the route tests to verify they fail**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis.test.ts
```

Expected: FAIL because the route still writes `processing`, calls `AnalysisService`, and `Variables` may not expose `session_id`.

- [x] **Step 3: Verify `session_id` is typed in Hono variables**

Confirm `src/backend/types/variables.ts` includes `session_id` both on the user object and as a top-level variable:

```ts
export interface Variables {
  user: {
    id: string;
    email?: string;
    name: string;
    session_id: string;
  };
  session_id: string;
  access_token: string;
}
```

If the file already matches this shape, do not edit it.

- [x] **Step 4: Replace inline analysis with queue send**

In `src/backend/routes/analysis.ts`, remove the `AnalysisService` import and replace the POST route body after duplicate-status handling with:

```ts
const jobId = crypto.randomUUID();
const now = new Date().toISOString();
const status = {
  job_id: jobId,
  playlist_id: playlistId,
  user_id: userId,
  status: 'queued' as const,
  queued_at: now,
  progress: 0,
};

await cacheService.set(statusKey, status, 3600);

await c.env.ANALYSIS_QUEUE.send({
  job_id: jobId,
  playlist_id: playlistId,
  user_id: userId,
  session_id: c.get('session_id'),
  enqueued_at: now,
  attempt: 0,
});

return c.json({
  data: status,
  meta: { timestamp: new Date().toISOString() }
});
```

Update duplicate-status handling so active queued jobs are returned:

```ts
const isQueued = s.status === 'queued';
const isCompleted = s.status === 'completed';
const isActivelyProcessing =
  (s.status === 'processing' || s.status === 'retrying') &&
  (typeof s.started_at !== 'string' ||
    Date.now() - new Date(s.started_at).getTime() < 300_000);

if (isCompleted || isQueued || isActivelyProcessing) {
  return c.json({
    data: existingStatus,
    meta: { timestamp: new Date().toISOString() }
  });
}
```

- [x] **Step 5: Run the route tests**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis.test.ts
```

Expected: PASS.

- [x] **Step 6: Commit**

Run:

```bash
git add src/backend/routes/analysis.ts src/backend/tests/analysis.test.ts
git commit -m "feat: enqueue playlist analysis jobs"
```

## Task 5: Add Queue Consumer to the Worker Export

**Files:**
- Modify: `src/backend/index.ts`
- Test: `src/backend/tests/analysis-queue.test.ts`

- [x] **Step 1: Add failing queue consumer tests**

Append these tests to `src/backend/tests/analysis-queue.test.ts`:

```ts
import worker from '../index';

const queueMessage = (body: unknown, attempts = 1) => ({
  id: 'message-1',
  timestamp: new Date('2026-06-19T00:00:00.000Z'),
  body,
  attempts,
  ack: vi.fn(),
  retry: vi.fn(),
});

describe('analysis queue consumer', () => {
  it('processes each message in the queue batch', async () => {
    const processSpy = vi
      .spyOn(AnalysisJobService.prototype, 'process')
      .mockResolvedValue({ acknowledged: true, reason: 'completed' });
    const batch = {
      queue: 'spotibye-analysis-dev',
      messages: [
        queueMessage({
          job_id: 'job-1',
          playlist_id: 'playlist-1',
          user_id: 'user-1',
          session_id: 'session-1',
          enqueued_at: '2026-06-19T00:00:00.000Z',
          attempt: 0,
        }),
      ],
      retryAll: vi.fn(),
      ackAll: vi.fn(),
    } as unknown as MessageBatch;
    const env = {
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'client-id',
      SPOTIFY_CLIENT_SECRET: 'client-secret',
      JWT_SECRET: 'jwt-secret',
      CACHE_KV: kvNamespace(),
      SESSIONS_KV: kvNamespace(),
      ANALYSIS_QUEUE: { send: vi.fn() } as unknown as Queue,
    };

    await worker.queue(batch, env, {} as ExecutionContext);

    expect(processSpy).toHaveBeenCalledWith(expect.objectContaining({
      job_id: 'job-1',
      attempt: 1,
    }));
    expect(batch.messages[0].ack).toHaveBeenCalledTimes(1);
  });

  it('marks the job failed instead of retrying after the final queue attempt', async () => {
    vi.spyOn(AnalysisJobService.prototype, 'process').mockRejectedValue(new Error('Spotify timeout'));
    const markFailedSpy = vi.spyOn(AnalysisJobService.prototype, 'markFailed').mockResolvedValue(undefined);
    const message = queueMessage({
      job_id: 'job-1',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      session_id: 'session-1',
      enqueued_at: '2026-06-19T00:00:00.000Z',
      attempt: 0,
    }, 3);
    const batch = {
      queue: 'spotibye-analysis-dev',
      messages: [message],
      retryAll: vi.fn(),
      ackAll: vi.fn(),
    } as unknown as MessageBatch;
    const env = {
      ENVIRONMENT: 'test',
      SPOTIFY_CLIENT_ID: 'client-id',
      SPOTIFY_CLIENT_SECRET: 'client-secret',
      JWT_SECRET: 'jwt-secret',
      CACHE_KV: kvNamespace(),
      SESSIONS_KV: kvNamespace(),
      ANALYSIS_QUEUE: { send: vi.fn() } as unknown as Queue,
    };

    await worker.queue(batch, env, {} as ExecutionContext);

    expect(markFailedSpy).toHaveBeenCalledWith(expect.objectContaining({
      job_id: 'job-1',
      attempt: 3,
    }), expect.any(Error));
    expect(message.ack).toHaveBeenCalledTimes(1);
    expect(message.retry).not.toHaveBeenCalled();
  });
});
```

- [x] **Step 2: Run the consumer tests to verify they fail**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis-queue.test.ts
```

Expected: FAIL because `worker.queue` is not exported.

- [x] **Step 3: Export the queue consumer**

Modify `src/backend/index.ts`:

```ts
import { AnalysisJobService } from './services/analysis-job';
import type { AnalysisQueueMessage } from './types/analysis-queue';
```

Replace the default export with:

```ts
export default {
  fetch: app.fetch,
  async queue(batch: MessageBatch<AnalysisQueueMessage>, env: Env, _ctx: ExecutionContext): Promise<void> {
    const jobService = new AnalysisJobService(env);

    for (const message of batch.messages) {
      const body = {
        ...message.body,
        attempt: message.attempts,
      };

      try {
        await jobService.process(body);
        message.ack();
      } catch (error) {
        if (message.attempts >= 3) {
          await jobService.markFailed(body, error);
          message.ack();
          continue;
        }

        message.retry();
      }
    }
  },
};
```

- [x] **Step 4: Run the consumer tests**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis-queue.test.ts
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add src/backend/index.ts src/backend/tests/analysis-queue.test.ts
git commit -m "feat: process analysis queue messages"
```

## Task 6: Add End-to-End Status and Idempotency Coverage

**Files:**
- Modify: `src/backend/tests/analysis-queue.test.ts`
- Modify: `src/backend/tests/analysis.test.ts`

- [x] **Step 1: Add duplicate completed delivery coverage**

Append this test to `src/backend/tests/analysis-queue.test.ts`:

```ts
it('acknowledges duplicate delivery after completion without re-running analysis', async () => {
  const cacheKv = kvNamespace({
    'analysis:playlist-1:user-1:status': {
      job_id: 'job-1',
      playlist_id: 'playlist-1',
      user_id: 'user-1',
      status: 'completed',
      progress: 100,
      completed_at: '2026-06-19T00:00:01.000Z',
    },
  });
  const service = new AnalysisJobService({
    ENVIRONMENT: 'test',
    SPOTIFY_CLIENT_ID: 'client-id',
    SPOTIFY_CLIENT_SECRET: 'client-secret',
    JWT_SECRET: 'jwt-secret',
    CACHE_KV: cacheKv,
    SESSIONS_KV: kvNamespace(),
    ANALYSIS_QUEUE: { send: vi.fn() } as unknown as Queue,
  });
  const analyzeSpy = vi.spyOn(AnalysisService.prototype, 'analyzePlaylist');

  const outcome = await service.process({
    job_id: 'job-1',
    playlist_id: 'playlist-1',
    user_id: 'user-1',
    session_id: 'session-1',
    enqueued_at: '2026-06-19T00:00:00.000Z',
    attempt: 1,
  });

  expect(outcome).toEqual({ acknowledged: true, reason: 'already-completed' });
  expect(analyzeSpy).not.toHaveBeenCalled();
});
```

- [x] **Step 2: Add POST duplicate queued status coverage**

Add this test under `POST /analysis/playlist/:id` in `src/backend/tests/analysis.test.ts`:

```ts
it('returns existing queued status without enqueuing a duplicate job', async () => {
  (mockEnv.CACHE_KV.get as any).mockResolvedValueOnce(JSON.stringify({
    job_id: 'job-existing',
    playlist_id: 'playlist1',
    user_id: 'test-user-id',
    status: 'queued',
    queued_at: '2026-06-19T00:00:00.000Z',
    progress: 0,
  }));
  const request = new Request('http://localhost/analysis/playlist/playlist1', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer test-jwt-token',
      'Content-Type': 'application/json',
    },
  });

  const response = await app.request(request, undefined, mockEnv);
  const data = (await response.json()) as any;

  expect(response.status).toBe(200);
  expect(data.data).toMatchObject({
    job_id: 'job-existing',
    status: 'queued',
  });
  expect(mockEnv.ANALYSIS_QUEUE.send).not.toHaveBeenCalled();
});
```

- [x] **Step 3: Run focused tests**

Run:

```bash
cd src/backend && npm run test:run -- tests/analysis.test.ts tests/analysis-queue.test.ts
```

Expected: PASS.

- [x] **Step 4: Commit**

Run:

```bash
git add src/backend/tests/analysis.test.ts src/backend/tests/analysis-queue.test.ts
git commit -m "test: cover analysis queue idempotency"
```

## Task 7: Update Docs and Changelog

**Files:**
- Modify: `src/backend/docs/deployment-configuration.md`
- Modify: `CHANGELOG.md`
- Verify: `docs/index.md`

- [x] **Step 1: Document queue setup**

Add this section to `src/backend/docs/deployment-configuration.md`:

````md
## Analysis Queue

Playlist analysis uses Cloudflare Queues in production so large playlists can retry outside the initial HTTP request. The Worker module exports both `fetch` and `queue`; no separate Worker entry point is required.

Required queues:

```bash
cd src/backend
npx wrangler queues create spotibye-analysis-dev
npx wrangler queues create spotibye-analysis-dev-dlq
npx wrangler queues create spotibye-analysis
npx wrangler queues create spotibye-analysis-dlq
```

The producer and consumer binding name is `ANALYSIS_QUEUE`. Queue messages contain `job_id`, `playlist_id`, `user_id`, `session_id`, `enqueued_at`, and `attempt`; they never contain Spotify access tokens. The consumer loads the session from `SESSIONS_KV` and refreshes the Spotify token when needed.
````

- [x] **Step 2: Add changelog entry**

Add this bullet under the current unreleased section in `CHANGELOG.md`:

```md
- Hardened backend playlist analysis by queueing large analysis jobs with retry-safe status updates instead of relying on request-scoped background work.
```

- [x] **Step 3: Run docs link check by inspection**

Run:

```bash
rg -n "Analysis Queue|ANALYSIS_QUEUE|spotibye-analysis" src/backend/docs CHANGELOG.md docs/index.md
```

Expected: The new deployment section and changelog entry are found. `docs/index.md` does not need a new entry because `src/backend/docs/deployment-configuration.md` is already part of the backend docs map.

- [x] **Step 4: Commit**

Run:

```bash
git add src/backend/docs/deployment-configuration.md CHANGELOG.md
git commit -m "docs: document analysis queue deployment"
```

## Task 8: Final Verification

**Files:**
- Verify: `src/backend`
- Verify: `dev-docs/plans/reccobeats-wiring.md`

- [x] **Step 1: Run backend tests**

Run:

```bash
cd src/backend && npm run test:run
```

Expected: PASS.

- [x] **Step 2: Run backend lint**

Run:

```bash
cd src/backend && npm run lint
```

Expected: PASS.

- [x] **Step 3: Run backend build**

Run:

```bash
cd src/backend && npm run build
```

Expected: PASS.

- [x] **Step 4: Run full repository verification**

Run:

```bash
./scripts/verify-all.sh
```

Expected: silent success. If failures occur, capture the failing command and fix only failures introduced by this queue work.

- [x] **Step 5: Confirm Track D acceptance criteria**

Manually confirm these outcomes from tests and implementation:

```md
- [x] Analysis for a 300-track playlist is processed by the queue consumer, not the request handler.
- [x] If a Worker restarts mid-analysis, Cloudflare Queues retries the message.
- [x] Duplicate queue delivery exits without overwriting a newer or completed job.
- [x] Status correctly transitions `queued -> processing -> completed`.
- [x] Retryable failures expose `retrying`; exhausted retries expose `failed`.
```

- [x] **Step 6: Commit any verification fixes**

If verification required code fixes, run:

```bash
git add src/backend src/backend/docs CHANGELOG.md
git commit -m "fix: stabilize analysis queue verification"
```

If no fixes were required, do not create an empty commit.

## Self-Review Notes

- Worker export structure is covered by Task 5: same module, `fetch` plus `queue`.
- Wrangler producer/consumer configuration is covered by Task 2.
- `Env` typing for `ANALYSIS_QUEUE` is covered by Task 1.
- Queue message type and token lifetime strategy are covered by Tasks 1 and 3; access tokens are not enqueued.
- Status transitions and retry-visible failure states are covered by Tasks 3, 5, 6, and 8.
- Idempotency for duplicate and stale deliveries is covered by Tasks 3 and 6.
- Retry, duplicate delivery, and completed result persistence tests are covered by Tasks 3, 5, and 6.

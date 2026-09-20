import type {
  AnalysisStatusRecord,
  ChunkRegistration,
  FanoutCountdownState,
} from '../types/analysis-queue';

const STATUS_KEY = 'status';
const FANOUT_KEY_PREFIX = 'fanout:';
/** Stuck-finalizer lease: re-claim allowed after this many ms without terminal status. */
const FINALIZER_LEASE_MS = 300_000;

export interface InitFanoutBody {
  job_id: string;
  expected: number;
}

export interface RegisterChunkBody {
  job_id: string;
  chunk_id: string;
  ok: boolean;
}

export interface RegisterChunkResponse extends ChunkRegistration {
  received: number;
  expected: number;
  /** True when the countdown no longer exists (cancelled/expired). */
  gone: boolean;
}

function fanoutKey(jobId: string): string {
  return `${FANOUT_KEY_PREFIX}${jobId}`;
}

function isTerminalStatus(status: AnalysisStatusRecord | undefined): boolean {
  return status?.status === 'completed' || status?.status === 'failed';
}

export type AnalysisStatusNamespace = Pick<DurableObjectNamespace, 'getByName'>;

export class AnalysisStatusObject {
  constructor(private state: DurableObjectState) {}

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/status') {
      return this.handleStatus(request);
    }

    if (url.pathname === '/fanout' || url.pathname === '/fanout/register') {
      return this.handleFanout(url, request);
    }

    return new Response('Not Found', { status: 404 });
  }

  private async handleStatus(request: Request): Promise<Response> {
    if (request.method === 'GET') {
      const status = await this.state.storage.get<AnalysisStatusRecord>(STATUS_KEY);
      return Response.json({ status: status ?? null });
    }

    if (request.method === 'PUT') {
      const status = await request.json<AnalysisStatusRecord>();
      await this.state.storage.put(STATUS_KEY, status);
      return Response.json({ status });
    }

    if (request.method === 'PATCH') {
      const partial = await request.json<Partial<AnalysisStatusRecord>>();
      const current = await this.state.storage.get<AnalysisStatusRecord>(STATUS_KEY);
      if (!current) {
        return Response.json({ status: null });
      }
      const status = { ...current, ...partial } satisfies AnalysisStatusRecord;
      await this.state.storage.put(STATUS_KEY, status);
      return Response.json({ status });
    }

    if (request.method === 'DELETE') {
      await this.state.storage.delete(STATUS_KEY);
      return Response.json({ status: null });
    }

    return new Response('Method Not Allowed', { status: 405 });
  }

  private async handleFanout(url: URL, request: Request): Promise<Response> {
    if (url.pathname === '/fanout' && request.method === 'GET') {
      const jobId = url.searchParams.get('job_id');
      if (!jobId) {
        return new Response('Missing job_id', { status: 400 });
      }
      const state = await this.state.storage.get<FanoutCountdownState>(fanoutKey(jobId));
      return Response.json({ fanout: state ?? null });
    }

    if (url.pathname === '/fanout' && request.method === 'PUT') {
      const body = await request.json<InitFanoutBody>();
      const existing = await this.state.storage.get<FanoutCountdownState>(fanoutKey(body.job_id));
      if (existing) {
        return Response.json({ fanout: existing });
      }
      const state: FanoutCountdownState = {
        expected: body.expected,
        received: {},
        finalizerClaimedAt: null,
        created_at: new Date().toISOString(),
      };
      await this.state.storage.put(fanoutKey(body.job_id), state);
      // Backstop for orphaned countdowns (jobs that die before any worker
      // registers): sweep state older than 24h. Overwrites any existing
      // alarm — one sweep covers all countdowns on this object.
      await this.state.storage.setAlarm(Date.now() + 24 * 3600 * 1000);
      return Response.json({ fanout: state });
    }

    if (url.pathname === '/fanout' && request.method === 'DELETE') {
      const jobId = url.searchParams.get('job_id');
      if (!jobId) {
        return new Response('Missing job_id', { status: 400 });
      }
      await this.state.storage.delete(fanoutKey(jobId));
      return Response.json({ fanout: null });
    }

    if (url.pathname === '/fanout/register' && request.method === 'POST') {
      const body = await request.json<RegisterChunkBody>();
      // ONE storage transaction: concurrent registrations serialize here,
      // so the finalizer claim is a single atomic transition (never a
      // post-register zero-read plus status pre-check across awaits).
      const response = await this.state.storage.transaction(async (txn) => {
        const state = await txn.get<FanoutCountdownState>(fanoutKey(body.job_id));
        if (!state) {
          return { isFinalizer: false, received: 0, expected: 0, gone: true } satisfies RegisterChunkResponse;
        }
        if (!(body.chunk_id in state.received)) {
          state.received[body.chunk_id] = body.ok ? 'ok' : 'failed';
        }
        const received = Object.keys(state.received).length;
        let isFinalizer = false;
        if (received >= state.expected) {
          const status = await txn.get<AnalysisStatusRecord>(STATUS_KEY);
          if (!state.finalizerClaimedAt) {
            state.finalizerClaimedAt = new Date().toISOString();
            isFinalizer = true;
          } else if (
            !isTerminalStatus(status) &&
            Date.now() - Date.parse(state.finalizerClaimedAt) > FINALIZER_LEASE_MS
          ) {
            // Stuck-finalizer recovery: claim expired without terminal
            // status, so re-claim and re-run finalize (lease, no watchdog).
            state.finalizerClaimedAt = new Date().toISOString();
            isFinalizer = true;
          }
        }
        await txn.put(fanoutKey(body.job_id), state);
        return { isFinalizer, received, expected: state.expected, gone: false } satisfies RegisterChunkResponse;
      });
      return Response.json(response);
    }

    return new Response('Method Not Allowed', { status: 405 });
  }

  /** Sweep fan-out countdown state older than 24h (orphan cleanup). */
  async alarm(): Promise<void> {
    const entries = await this.state.storage.list<FanoutCountdownState>({
      prefix: FANOUT_KEY_PREFIX,
    });
    const cutoff = Date.now() - 24 * 3600 * 1000;
    for (const [key, state] of entries) {
      if (Date.parse(state.created_at) < cutoff) {
        await this.state.storage.delete(key);
      }
    }
  }
}

export class AnalysisStatusStore {
  constructor(private namespace: AnalysisStatusNamespace) {}

  async getStatus(userId: string, playlistId: string): Promise<AnalysisStatusRecord | null> {
    const response = await this.statusRequest(userId, playlistId, 'GET');
    return this.parseStatusResponse(response);
  }

  async writeStatus(userId: string, playlistId: string, status: AnalysisStatusRecord): Promise<void> {
    const response = await this.statusRequest(userId, playlistId, 'PUT', status);
    if (!response.ok) {
      throw new Error(`Failed to write analysis status: HTTP ${response.status}`);
    }
  }

  async mergeStatus(
    userId: string,
    playlistId: string,
    partial: Partial<AnalysisStatusRecord>
  ): Promise<AnalysisStatusRecord | null> {
    const response = await this.statusRequest(userId, playlistId, 'PATCH', partial);
    if (!response.ok) {
      throw new Error(`Failed to merge analysis status: HTTP ${response.status}`);
    }
    return this.parseStatusResponse(response);
  }

  async deleteStatus(userId: string, playlistId: string): Promise<void> {
    const response = await this.statusRequest(userId, playlistId, 'DELETE');
    if (!response.ok) {
      throw new Error(`Failed to delete analysis status: HTTP ${response.status}`);
    }
  }

  async initFanoutCountdown(
    userId: string,
    playlistId: string,
    jobId: string,
    expected: number,
  ): Promise<FanoutCountdownState> {
    const response = await this.fanoutRequest(userId, playlistId, 'PUT', '/fanout', {
      job_id: jobId,
      expected,
    } satisfies InitFanoutBody);
    if (!response.ok) {
      throw new Error(`Failed to init fan-out countdown: HTTP ${response.status}`);
    }
    const data = await response.json<{ fanout: FanoutCountdownState }>();
    return data.fanout;
  }

  async registerChunkResult(
    userId: string,
    playlistId: string,
    jobId: string,
    chunkId: string,
    ok: boolean,
  ): Promise<RegisterChunkResponse> {
    const response = await this.fanoutRequest(userId, playlistId, 'POST', '/fanout/register', {
      job_id: jobId,
      chunk_id: chunkId,
      ok,
    } satisfies RegisterChunkBody);
    if (!response.ok) {
      throw new Error(`Failed to register chunk result: HTTP ${response.status}`);
    }
    return response.json<RegisterChunkResponse>();
  }

  async cancelFanoutCountdown(userId: string, playlistId: string, jobId: string): Promise<void> {
    const response = await this.fanoutRequest(
      userId, playlistId, 'DELETE', `/fanout?job_id=${encodeURIComponent(jobId)}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to cancel fan-out countdown: HTTP ${response.status}`);
    }
  }

  async getFanoutCountdown(
    userId: string,
    playlistId: string,
    jobId: string,
  ): Promise<FanoutCountdownState | null> {
    const response = await this.fanoutRequest(
      userId, playlistId, 'GET', `/fanout?job_id=${encodeURIComponent(jobId)}`,
    );
    if (!response.ok) {
      throw new Error(`Failed to read fan-out countdown: HTTP ${response.status}`);
    }
    const data = await response.json<{ fanout: FanoutCountdownState | null }>();
    return data.fanout;
  }

  private statusRequest(
    userId: string,
    playlistId: string,
    method: 'GET' | 'PUT' | 'PATCH' | 'DELETE',
    body?: AnalysisStatusRecord | Partial<AnalysisStatusRecord>
  ): Promise<Response> {
    const stub = this.namespace.getByName(analysisStatusObjectName(userId, playlistId));
    return stub.fetch('https://analysis-status.internal/status', {
      method,
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  }

  private fanoutRequest(
    userId: string,
    playlistId: string,
    method: 'GET' | 'PUT' | 'POST' | 'DELETE',
    path: string,
    body?: InitFanoutBody | RegisterChunkBody,
  ): Promise<Response> {
    const stub = this.namespace.getByName(analysisStatusObjectName(userId, playlistId));
    return stub.fetch(`https://analysis-status.internal${path}`, {
      method,
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  }

  private async parseStatusResponse(response: Response): Promise<AnalysisStatusRecord | null> {
    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error(`Failed to read analysis status: HTTP ${response.status}`);
    }

    const data = await response.json<{ status: AnalysisStatusRecord | null }>();
    return data.status;
  }
}

export function analysisStatusObjectName(userId: string, playlistId: string): string {
  return `analysis:${userId}:${playlistId}`;
}

export function createAnalysisStatusNamespaceStub(): AnalysisStatusNamespace {
  const stores = new Map<string, AnalysisStatusRecord>();
  const fanouts = new Map<string, FanoutCountdownState>();

  return {
    getByName(name: string) {
      return {
        async fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
          const request = new Request(input, init);
          const method = request.method.toUpperCase();
          const url = new URL(request.url);
          if (url.pathname === '/fanout' && method === 'GET') {
            const jobId = url.searchParams.get('job_id');
            if (!jobId) {
              return new Response('Missing job_id', { status: 400 });
            }
            return Response.json({ fanout: fanouts.get(`${name}:fanout:${jobId}`) ?? null });
          }
          if (url.pathname === '/fanout' && method === 'PUT') {
            const body = await request.json<InitFanoutBody>();
            const key = `${name}:fanout:${body.job_id}`;
            const existing = fanouts.get(key);
            if (existing) {
              return Response.json({ fanout: existing });
            }
            const state: FanoutCountdownState = {
              expected: body.expected,
              received: {},
              finalizerClaimedAt: null,
              created_at: new Date().toISOString(),
            };
            fanouts.set(key, state);
            return Response.json({ fanout: state });
          }
          if (url.pathname === '/fanout' && method === 'DELETE') {
            const jobId = url.searchParams.get('job_id');
            if (!jobId) {
              return new Response('Missing job_id', { status: 400 });
            }
            fanouts.delete(`${name}:fanout:${jobId}`);
            return Response.json({ fanout: null });
          }
          if (url.pathname === '/fanout/register' && method === 'POST') {
            const body = await request.json<RegisterChunkBody>();
            const key = `${name}:fanout:${body.job_id}`;
            const state = fanouts.get(key);
            if (!state) {
              return Response.json({
                isFinalizer: false, received: 0, expected: 0, gone: true,
              } satisfies RegisterChunkResponse);
            }
            if (!(body.chunk_id in state.received)) {
              state.received[body.chunk_id] = body.ok ? 'ok' : 'failed';
            }
            const received = Object.keys(state.received).length;
            let isFinalizer = false;
            if (received >= state.expected) {
              const status = stores.get(name);
              const terminal = status?.status === 'completed' || status?.status === 'failed';
              if (!state.finalizerClaimedAt) {
                state.finalizerClaimedAt = new Date().toISOString();
                isFinalizer = true;
              } else if (
                !terminal &&
                Date.now() - Date.parse(state.finalizerClaimedAt) > FINALIZER_LEASE_MS
              ) {
                state.finalizerClaimedAt = new Date().toISOString();
                isFinalizer = true;
              }
            }
            return Response.json({
              isFinalizer, received, expected: state.expected, gone: false,
            } satisfies RegisterChunkResponse);
          }
          if (url.pathname !== '/status') {
            return new Response('Not Found', { status: 404 });
          }
          if (method === 'GET') {
            return Response.json({ status: stores.get(name) ?? null });
          }
          if (method === 'PUT') {
            const status = await request.json<AnalysisStatusRecord>();
            stores.set(name, status);
            return Response.json({ status });
          }
          if (method === 'PATCH') {
            const current = stores.get(name);
            if (!current) {
              return Response.json({ status: null });
            }
            const partial = await request.json<Partial<AnalysisStatusRecord>>();
            const status = { ...current, ...partial } satisfies AnalysisStatusRecord;
            stores.set(name, status);
            return Response.json({ status });
          }
          if (method === 'DELETE') {
            stores.delete(name);
            return Response.json({ status: null });
          }
          return new Response('Method Not Allowed', { status: 405 });
        },
      } as DurableObjectStub;
    },
  };
}

import type { AnalysisStatusRecord } from '../types/analysis-queue';

const STATUS_KEY = 'status';

export type AnalysisStatusNamespace = Pick<DurableObjectNamespace, 'getByName'>;

export class AnalysisStatusObject {
  constructor(private state: DurableObjectState) {}

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname !== '/status') {
      return new Response('Not Found', { status: 404 });
    }

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

  return {
    getByName(name: string) {
      return {
        async fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
          const request = new Request(input, init);
          const method = request.method.toUpperCase();
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

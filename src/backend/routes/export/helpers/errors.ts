import type { ContentfulStatusCode } from 'hono/utils/http-status';

export function resolveErrorStatus(code: string, message: string): ContentfulStatusCode {
  if (/cpu time limit|exceeded cpu/i.test(message)) {
    return 503;
  }
  if (/HTTP\s+401/i.test(message)) {
    return 401;
  }
  if (/HTTP\s+429/i.test(message)) {
    return 429;
  }
  return code.includes('DOWNLOAD') ? 503 : 500;
}

export function parseUpstreamStatus(errorMessage: string): number | undefined {
  const match = /HTTP\s+(\d{3})/i.exec(errorMessage);
  if (!match) {
    return undefined;
  }
  const parsed = Number.parseInt(match[1], 10);
  return Number.isNaN(parsed) ? undefined : parsed;
}

export function buildExportErrorPayload(code: string, message: string, requestId: string, details: Record<string, unknown> = {}) {
  const upstreamStatus = parseUpstreamStatus(message);
  const upstream = upstreamStatus ? 'spotify' : undefined;
  const cpuLimited = /cpu time limit|exceeded cpu/i.test(message);
  return {
    error: {
      code,
      message,
      request_id: requestId,
      details: {
        ...details,
        upstream,
        upstream_status: upstreamStatus,
        cpu_limited: cpuLimited,
      },
    },
  };
}

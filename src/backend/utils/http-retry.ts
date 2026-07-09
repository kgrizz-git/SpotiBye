import { parseRetryAfter } from '../services/spotify';

export interface FetchRetryConfig {
  maxRetries?: number;
  timeoutMs?: number;
  backoffMs?: number;
}

/**
 * Builds a `fetch`-compatible function with timeout + retry behavior:
 * - 429: honors `Retry-After` before retrying.
 * - 5xx: exponential backoff (`backoffMs * 2^attempt`).
 * - Timeout: counts as a retryable attempt (Workers lack `AbortSignal.timeout()`,
 *   so timeouts are implemented with `AbortController` + `setTimeout`).
 * - 4xx (non-429): thrown immediately, not retried.
 * - Retries exhausted: throws the last error.
 */
export function createFetchWithRetry(
  config: FetchRetryConfig = {}
): (url: string | URL, init?: RequestInit) => Promise<Response> {
  const { maxRetries = 3, timeoutMs = 15000, backoffMs = 500 } = config;

  return async function fetchWithRetry(url: string | URL, init?: RequestInit): Promise<Response> {
    let lastError: unknown;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      try {
        const response = await fetch(url, { ...init, signal: controller.signal });
        clearTimeout(timeoutId);

        if (response.status === 429) {
          const retryAfterSeconds = parseRetryAfter(response.headers.get('Retry-After'));
          lastError = new Error(`HTTP 429: rate limited`);
          if (attempt === maxRetries - 1) throw lastError;
          await sleep(retryAfterSeconds * 1000);
          continue;
        }

        if (response.status >= 500) {
          lastError = new Error(`HTTP ${response.status}: ${response.statusText}`);
          if (attempt === maxRetries - 1) throw lastError;
          await sleep(backoffMs * 2 ** attempt);
          continue;
        }

        return response;
      } catch (error) {
        clearTimeout(timeoutId);
        lastError = error;

        const isAbort = error instanceof Error && error.name === 'AbortError';
        if (!isAbort && error instanceof Error && error.message.startsWith('HTTP ')) {
          // Non-retryable HTTP error thrown above for 429/5xx on the final attempt.
          throw error;
        }

        if (attempt === maxRetries - 1) {
          throw isAbort ? new Error(`Request timed out after ${timeoutMs}ms`) : error;
        }

        await sleep(backoffMs * 2 ** attempt);
      }
    }

    throw lastError instanceof Error ? lastError : new Error('Max retries exceeded');
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

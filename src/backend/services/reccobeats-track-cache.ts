/**
 * Global per-track ReccoBeats enrichment cache.
 *
 * Resolves Spotify track IDs to ReccoBeats audio-features / track-metadata via
 * KV (6-month positive TTL, 7-day per-endpoint absent sentinels), fetching only
 * cache misses. Shared across users under `global:reccobeats:*` keys (GP#4
 * exception — see golden-principles.md).
 *
 * Inputs: Spotify track ID lists + optional `{ force }` to clear positive and
 * absent keys before refetch.
 * Outputs: merged `Map<spotifyTrackId, row>` of positive hits plus counters
 * (`resolvedIds` / `absentIds` / `unresolvedIds`). Callers must not re-fetch
 * misses themselves.
 *
 * In-flight dedup is per Worker isolate only — concurrent isolates can still
 * duplicate ReccoBeats HTTP (blast radius bounded by batch ≤30).
 */

import { CacheService } from './cache';
import { createFetchWithRetry } from '../utils/http-retry';
import { logger } from '../utils/logger';
import {
  RECCOBEATS_BATCH_SIZE,
  RECCOBEATS_HTTP_CONCURRENCY,
  RECCOBEATS_JITTER_DELAY_MS,
  RECCOBEATS_KV_CONCURRENCY,
  RECCOBEATS_NEGATIVE_CACHE_TTL_SECONDS,
  RECCOBEATS_TRACK_ENRICHMENT_TTL_SECONDS,
} from '../utils/constants';
import {
  isReccoBeatsAudioFeature,
  isReccoBeatsContentEnvelope,
  isReccoBeatsTrackMetadata,
  mapReccoBeatsContentBySpotifyId,
} from '../utils/reccobeats-helpers';
import type {
  ReccoBeatsAbsentSentinel,
  ReccoBeatsAudioFeature,
  ReccoBeatsResolveCounters,
  ReccoBeatsResolveResult,
  ReccoBeatsTrackMetadata,
} from '../types/analysis';

type ReccoBeatsEndpoint = 'audio-features' | 'track-metadata';

type KeyFn = (spotifyTrackId: string) => string;

interface CacheLookupState<T> {
  bySpotifyId: Map<string, T>;
  absentIds: Set<string>;
  missIds: string[];
  negativeSkipped: number;
}

interface FetchMissesResult {
  fetchedCount: number;
  unparseableCount: number;
}

const RECCOBEATS_BASE_URL = 'https://api.reccobeats.com/v1';

/** Module-level in-flight coalesce (per isolate). */
const inFlight = new Map<string, Promise<ReccoBeatsResolveResult<unknown>>>();

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function chunk<T>(items: T[], size: number): T[][] {
  const result: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    result.push(items.slice(i, i + size));
  }
  return result;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function truncateResponseBody(body: string, maxLength = 500): string {
  return body.length > maxLength ? `${body.slice(0, maxLength)}...` : body;
}

function uniqueSortedTrackIds(trackIds: string[]): string[] {
  return [...new Set(trackIds.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

/** Stable coalesce key for ≤30-ID batches (deterministic join). */
function coalesceKey(endpoint: ReccoBeatsEndpoint, force: boolean, sortedIds: string[]): string {
  return `${endpoint}:${force ? 'force:' : ''}${sortedIds.join(',')}`;
}

export function audioFeaturesCacheKey(spotifyTrackId: string): string {
  return `global:reccobeats:audio-features:${spotifyTrackId}`;
}

export function trackMetadataCacheKey(spotifyTrackId: string): string {
  return `global:reccobeats:track-metadata:${spotifyTrackId}`;
}

export function absentAudioFeaturesCacheKey(spotifyTrackId: string): string {
  return `global:reccobeats:absent:audio-features:${spotifyTrackId}`;
}

export function absentTrackMetadataCacheKey(spotifyTrackId: string): string {
  return `global:reccobeats:absent:track-metadata:${spotifyTrackId}`;
}

function isAbsentSentinel(value: unknown): value is ReccoBeatsAbsentSentinel {
  return !!value
    && typeof value === 'object'
    && (value as ReccoBeatsAbsentSentinel).absent === true;
}

async function mapPool<T>(
  items: T[],
  concurrency: number,
  worker: (item: T) => Promise<void>
): Promise<void> {
  if (items.length === 0) return;
  let nextIndex = 0;
  const runners = Array.from(
    { length: Math.min(concurrency, items.length) },
    async () => {
      while (nextIndex < items.length) {
        const current = nextIndex;
        nextIndex += 1;
        await worker(items[current]);
      }
    }
  );
  await Promise.all(runners);
}

function partitionResolvedIds(
  uniqueIds: string[],
  bySpotifyId: Map<string, unknown>,
  absentIds: Set<string>
): { resolvedIds: string[]; unresolvedIds: string[] } {
  const resolvedIds: string[] = [];
  const unresolvedIds: string[] = [];
  for (const id of uniqueIds) {
    if (bySpotifyId.has(id) || absentIds.has(id)) {
      resolvedIds.push(id);
    } else {
      unresolvedIds.push(id);
    }
  }
  return { resolvedIds, unresolvedIds };
}

export class ReccoBeatsTrackCacheService {
  private cache?: CacheService;
  private fetchWithRetry = createFetchWithRetry();

  constructor(cache?: CacheService) {
    this.cache = cache;
  }

  async resolveAudioFeatures(
    trackIds: string[],
    options: { force?: boolean; onGroupComplete?: () => Promise<void> } = {}
  ): Promise<ReccoBeatsResolveResult<ReccoBeatsAudioFeature>> {
    return this.resolveEndpoint(
      'audio-features',
      trackIds,
      options.force === true,
      isReccoBeatsAudioFeature,
      audioFeaturesCacheKey,
      absentAudioFeaturesCacheKey,
      (batch) => this.fetchAudioFeaturesBatch(batch),
      options.onGroupComplete
    );
  }

  async resolveTrackMetadata(
    trackIds: string[],
    options: { force?: boolean; onGroupComplete?: () => Promise<void> } = {}
  ): Promise<ReccoBeatsResolveResult<ReccoBeatsTrackMetadata>> {
    return this.resolveEndpoint(
      'track-metadata',
      trackIds,
      options.force === true,
      isReccoBeatsTrackMetadata,
      trackMetadataCacheKey,
      absentTrackMetadataCacheKey,
      (batch) => this.fetchTrackMetadataBatch(batch),
      options.onGroupComplete
    );
  }

  private async resolveEndpoint<T extends { href?: string }>(
    endpoint: ReccoBeatsEndpoint,
    trackIds: string[],
    force: boolean,
    isRow: (row: unknown) => row is T,
    positiveKey: KeyFn,
    absentKey: KeyFn,
    fetchBatch: (batchIds: string[]) => Promise<{ bySpotifyId: Map<string, T>; unparseableCount: number }>,
    onGroupComplete?: () => Promise<void>
  ): Promise<ReccoBeatsResolveResult<T>> {
    const uniqueIds = uniqueSortedTrackIds(trackIds);
    if (uniqueIds.length === 0) {
      return {
        bySpotifyId: new Map(),
        counters: emptyCounters([]),
      };
    }

    const key = coalesceKey(endpoint, force, uniqueIds);
    const existing = inFlight.get(key);
    if (existing) {
      return existing as Promise<ReccoBeatsResolveResult<T>>;
    }

    const promise = this.resolveEndpointUncoalesced(
      endpoint,
      uniqueIds,
      force,
      isRow,
      positiveKey,
      absentKey,
      fetchBatch,
      onGroupComplete
    ).finally(() => {
      inFlight.delete(key);
    });

    inFlight.set(key, promise as Promise<ReccoBeatsResolveResult<unknown>>);
    return promise;
  }

  private async resolveEndpointUncoalesced<T extends { href?: string }>(
    endpoint: ReccoBeatsEndpoint,
    uniqueIds: string[],
    force: boolean,
    isRow: (row: unknown) => row is T,
    positiveKey: KeyFn,
    absentKey: KeyFn,
    fetchBatch: (batchIds: string[]) => Promise<{ bySpotifyId: Map<string, T>; unparseableCount: number }>,
    onGroupComplete?: () => Promise<void>
  ): Promise<ReccoBeatsResolveResult<T>> {
    if (force) {
      await this.deleteKnownKeys(uniqueIds, positiveKey, absentKey);
    }

    const lookup = await this.lookupCachedIds(uniqueIds, force, isRow, positiveKey, absentKey);
    const fetchResult = await this.fetchAndCacheMisses(
      endpoint,
      lookup,
      positiveKey,
      absentKey,
      fetchBatch,
      onGroupComplete
    );

    const { resolvedIds, unresolvedIds } = partitionResolvedIds(
      uniqueIds,
      lookup.bySpotifyId,
      lookup.absentIds
    );

    logger.info('ReccoBeats track-cache resolve complete', {
      endpoint,
      force,
      requested: uniqueIds.length,
      hits: lookup.bySpotifyId.size,
      absents: lookup.absentIds.size,
      fetchedCount: fetchResult.fetchedCount,
      negativeSkipped: lookup.negativeSkipped,
      unparseableCount: fetchResult.unparseableCount,
      unresolved: unresolvedIds.length,
    });

    return {
      bySpotifyId: lookup.bySpotifyId,
      counters: {
        fetchedCount: fetchResult.fetchedCount,
        negativeSkipped: lookup.negativeSkipped,
        unparseableCount: fetchResult.unparseableCount,
        resolvedCount: resolvedIds.length,
        resolvedIds,
        absentIds: [...lookup.absentIds],
        unresolvedIds,
      },
    };
  }

  /** Two-stage KV lookup: positive first, absent only on miss. */
  private async lookupCachedIds<T>(
    uniqueIds: string[],
    force: boolean,
    isRow: (row: unknown) => row is T,
    positiveKey: KeyFn,
    absentKey: KeyFn
  ): Promise<CacheLookupState<T>> {
    const state: CacheLookupState<T> = {
      bySpotifyId: new Map(),
      absentIds: new Set(),
      missIds: [],
      negativeSkipped: 0,
    };

    if (!this.cache || force) {
      state.missIds.push(...uniqueIds);
      return state;
    }

    await mapPool(uniqueIds, RECCOBEATS_KV_CONCURRENCY, async (id) => {
      const positive = await this.cache!.get<T>(positiveKey(id));
      if (positive && isRow(positive)) {
        state.bySpotifyId.set(id, positive);
        return;
      }
      const absent = await this.cache!.get<ReccoBeatsAbsentSentinel>(absentKey(id));
      if (isAbsentSentinel(absent)) {
        state.absentIds.add(id);
        state.negativeSkipped += 1;
        return;
      }
      state.missIds.push(id);
    });

    return state;
  }

  private async fetchAndCacheMisses<T extends { href?: string }>(
    endpoint: ReccoBeatsEndpoint,
    lookup: CacheLookupState<T>,
    positiveKey: KeyFn,
    absentKey: KeyFn,
    fetchBatch: (batchIds: string[]) => Promise<{ bySpotifyId: Map<string, T>; unparseableCount: number }>,
    onGroupComplete?: () => Promise<void>
  ): Promise<FetchMissesResult> {
    if (lookup.missIds.length === 0) {
      return { fetchedCount: 0, unparseableCount: 0 };
    }

    let fetchedCount = 0;
    let unparseableCount = 0;
    const batches = chunk(lookup.missIds, RECCOBEATS_BATCH_SIZE);

    for (let i = 0; i < batches.length; i += RECCOBEATS_HTTP_CONCURRENCY) {
      const group = batches.slice(i, i + RECCOBEATS_HTTP_CONCURRENCY);
      const results = await Promise.all(group.map((batch) => fetchBatch(batch)));

      for (let batchIndex = 0; batchIndex < results.length; batchIndex++) {
        const batchStats = await this.applyFetchedBatch(
          group[batchIndex],
          results[batchIndex],
          lookup,
          positiveKey,
          absentKey
        );
        fetchedCount += batchStats.fetchedCount;
        unparseableCount += batchStats.unparseableCount;
      }

      if (i + RECCOBEATS_HTTP_CONCURRENCY < batches.length && endpoint === 'audio-features') {
        await sleep(RECCOBEATS_JITTER_DELAY_MS);
      }
      await onGroupComplete?.();
    }

    return { fetchedCount, unparseableCount };
  }

  /**
   * Merge one batch into lookup state and write positive/absent KV entries.
   * Absents are written only when the batch map had zero unparseable rows.
   */
  private async applyFetchedBatch<T>(
    batch: string[],
    fetched: { bySpotifyId: Map<string, T>; unparseableCount: number },
    lookup: CacheLookupState<T>,
    positiveKey: KeyFn,
    absentKey: KeyFn
  ): Promise<FetchMissesResult> {
    const stillMissing: string[] = [];
    const positiveWrites: Array<{ id: string; row: T }> = [];

    for (const id of batch) {
      const row = fetched.bySpotifyId.get(id);
      if (row) {
        lookup.bySpotifyId.set(id, row);
        positiveWrites.push({ id, row });
      } else {
        stillMissing.push(id);
      }
    }

    await this.writePositiveEntries(positiveWrites, positiveKey);

    // Verified absents only after a clean map — href-parse failures must not
    // poison the negative cache for still-missing requested IDs.
    if (fetched.unparseableCount === 0 && stillMissing.length > 0) {
      for (const id of stillMissing) {
        lookup.absentIds.add(id);
      }
      await this.writeAbsentEntries(stillMissing, absentKey);
    }

    return {
      fetchedCount: fetched.bySpotifyId.size,
      unparseableCount: fetched.unparseableCount,
    };
  }

  private async writePositiveEntries<T>(
    entries: Array<{ id: string; row: T }>,
    positiveKey: KeyFn
  ): Promise<void> {
    if (!this.cache || entries.length === 0) return;
    await mapPool(entries, RECCOBEATS_KV_CONCURRENCY, async ({ id, row }) => {
      await this.cache!.set(positiveKey(id), row, RECCOBEATS_TRACK_ENRICHMENT_TTL_SECONDS);
    });
  }

  private async writeAbsentEntries(ids: string[], absentKey: KeyFn): Promise<void> {
    if (!this.cache || ids.length === 0) return;
    const cachedAt = new Date().toISOString();
    await mapPool(ids, RECCOBEATS_KV_CONCURRENCY, async (id) => {
      const sentinel: ReccoBeatsAbsentSentinel = { absent: true, cached_at: cachedAt };
      await this.cache!.set(absentKey(id), sentinel, RECCOBEATS_NEGATIVE_CACHE_TTL_SECONDS);
    });
  }

  private async deleteKnownKeys(
    ids: string[],
    positiveKey: KeyFn,
    absentKey: KeyFn
  ): Promise<void> {
    if (!this.cache) return;
    const keys = ids.flatMap((id) => [positiveKey(id), absentKey(id)]);
    await mapPool(keys, RECCOBEATS_KV_CONCURRENCY, async (key) => {
      await this.cache!.delete(key);
    });
  }

  private async fetchAudioFeaturesBatch(
    batchIds: string[]
  ): Promise<{ bySpotifyId: Map<string, ReccoBeatsAudioFeature>; unparseableCount: number }> {
    const url = new URL(`${RECCOBEATS_BASE_URL}/audio-features`);
    for (const trackId of batchIds) {
      url.searchParams.append('ids', trackId);
    }

    const rawData = await this.fetchJson(url.toString(), 'audio-features', batchIds.length);
    if (!isReccoBeatsContentEnvelope(rawData.data)) {
      logger.warn('Invalid ReccoBeats audio features response shape', {
        endpoint: 'audio-features',
        status: rawData.status,
        batchSize: batchIds.length,
        bodyPreview: rawData.bodyPreview,
      });
      throw new Error('Invalid ReccoBeats audio features response shape');
    }

    return mapReccoBeatsContentBySpotifyId(
      rawData.data.content,
      isReccoBeatsAudioFeature,
      'audio-features'
    );
  }

  private async fetchTrackMetadataBatch(
    batchIds: string[]
  ): Promise<{ bySpotifyId: Map<string, ReccoBeatsTrackMetadata>; unparseableCount: number }> {
    const url = new URL(`${RECCOBEATS_BASE_URL}/track`);
    for (const trackId of batchIds) {
      url.searchParams.append('ids', trackId);
    }

    const rawData = await this.fetchJson(url.toString(), 'track', batchIds.length);
    if (!isReccoBeatsContentEnvelope(rawData.data)) {
      logger.warn('Invalid ReccoBeats track metadata response shape', {
        endpoint: 'track',
        status: rawData.status,
        batchSize: batchIds.length,
        bodyPreview: rawData.bodyPreview,
      });
      throw new Error('Invalid ReccoBeats track metadata response shape');
    }

    return mapReccoBeatsContentBySpotifyId(
      rawData.data.content,
      isReccoBeatsTrackMetadata,
      'track'
    );
  }

  private async fetchJson(
    url: string,
    endpoint: 'audio-features' | 'track',
    batchSize: number
  ): Promise<{ data: unknown; bodyPreview: string; status: number }> {
    let response: Response;
    try {
      response = await this.fetchWithRetry(url);
    } catch (error) {
      throw new Error(`ReccoBeats API error: ${errorMessage(error)}`, { cause: error });
    }

    if (!response.ok) {
      throw new Error(`ReccoBeats API error: HTTP ${response.status}: ${response.statusText}`);
    }

    const bodyText = await response.text();
    const bodyPreview = truncateResponseBody(bodyText);
    try {
      return { data: JSON.parse(bodyText), bodyPreview, status: response.status };
    } catch (error) {
      logger.warn('Invalid ReccoBeats JSON response', {
        endpoint,
        status: response.status,
        batchSize,
        bodyPreview,
        error: errorMessage(error),
      });
      throw new Error(`Invalid ReccoBeats ${endpoint} response JSON`, { cause: error });
    }
  }
}

function emptyCounters(uniqueIds: string[]): ReccoBeatsResolveCounters {
  return {
    fetchedCount: 0,
    negativeSkipped: 0,
    unparseableCount: 0,
    resolvedCount: 0,
    resolvedIds: [],
    absentIds: [],
    unresolvedIds: [...uniqueIds],
  };
}

/** Test helper: clear the isolate-local in-flight map between tests. */
export function clearReccoBeatsTrackCacheInFlightForTests(): void {
  inFlight.clear();
}

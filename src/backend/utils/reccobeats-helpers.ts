/**
 * ReccoBeats boundary helpers: Spotify ID extraction from `href`, row-level
 * validators, and content→Map mapping.
 *
 * Inputs: ReccoBeats HTTP JSON shapes (`content` arrays of audio-feature or
 * track-metadata rows).
 * Outputs: parseable Spotify track IDs and `Map<spotifyTrackId, row>` values.
 *
 * Join rule (see `dev-docs/reccobeats-api-contract.md`): never treat ReccoBeats
 * UUID `id` as a Spotify track ID — parse the track-level `href` instead.
 *
 * Cross-reference: mirrors `extract_spotify_id_from_href` in
 * `scripts/test_reccobeats_coverage.py` for the `/track/` path form; also
 * accepts `spotify:track:{id}` defensively. Do not share runtime with the script.
 */

import { logger } from './logger';
import type {
  ReccoBeatsAudioFeature,
  ReccoBeatsTrackMetadata,
} from '../types/analysis';

const OPEN_SPOTIFY_TRACK_MARKER = '/track/';
const SPOTIFY_URI_PREFIX = 'spotify:track:';

/**
 * Parse a Spotify track ID from a ReccoBeats track-level `href` (or URI).
 * Returns null when missing/unparseable — callers must not fall back to the
 * ReccoBeats UUID `id`.
 */
export function parseSpotifyTrackIdFromHref(href: unknown): string | null {
  if (typeof href !== 'string' || href.length === 0) {
    return null;
  }

  if (href.startsWith(SPOTIFY_URI_PREFIX)) {
    const trackId = href.slice(SPOTIFY_URI_PREFIX.length).split('?')[0].split('#')[0];
    return trackId || null;
  }

  const markerIndex = href.lastIndexOf(OPEN_SPOTIFY_TRACK_MARKER);
  if (markerIndex === -1) {
    return null;
  }

  const trackId = href
    .slice(markerIndex + OPEN_SPOTIFY_TRACK_MARKER.length)
    .split('?')[0]
    .split('#')[0];
  return trackId || null;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

/** Row-level guard: `href` is optional (missing href → skip at map time). */
export function isReccoBeatsAudioFeature(data: unknown): data is ReccoBeatsAudioFeature {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const record = data as Record<string, unknown>;
  if (typeof record.id !== 'string') {
    return false;
  }
  if (record.href !== undefined && typeof record.href !== 'string') {
    return false;
  }

  return isFiniteNumber(record.acousticness)
    && isFiniteNumber(record.danceability)
    && isFiniteNumber(record.energy)
    && isFiniteNumber(record.instrumentalness)
    && isFiniteNumber(record.liveness)
    && isFiniteNumber(record.loudness)
    && isFiniteNumber(record.speechiness)
    && isFiniteNumber(record.tempo)
    && isFiniteNumber(record.valence);
}

/** Row-level guard: track-level `href` is optional. */
export function isReccoBeatsTrackMetadata(data: unknown): data is ReccoBeatsTrackMetadata {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const record = data as Record<string, unknown>;
  if (typeof record.id !== 'string' || typeof record.trackTitle !== 'string') {
    return false;
  }
  if (typeof record.durationMs !== 'number') {
    return false;
  }
  if (record.href !== undefined && typeof record.href !== 'string') {
    return false;
  }
  if (!Array.isArray(record.artists)) {
    return false;
  }

  const artistsValid = record.artists.every((artist) => {
    if (!artist || typeof artist !== 'object') return false;
    const a = artist as Record<string, unknown>;
    return typeof a.id === 'string' && typeof a.name === 'string' && typeof a.href === 'string';
  });
  if (!artistsValid) {
    return false;
  }
  if (record.isrc !== undefined && typeof record.isrc !== 'string') {
    return false;
  }
  if (record.popularity !== undefined && typeof record.popularity !== 'number') {
    return false;
  }
  if (record.ean !== undefined && typeof record.ean !== 'string') {
    return false;
  }
  if (record.upc !== undefined && typeof record.upc !== 'string') {
    return false;
  }
  if (record.availableCountries !== undefined) {
    if (!Array.isArray(record.availableCountries)) {
      return false;
    }
    if (!record.availableCountries.every((c) => typeof c === 'string')) {
      return false;
    }
  }
  return true;
}

/**
 * True when `data` is an object with a `content` array. Does **not** require
 * every row to be well-formed — callers filter per-row.
 */
export function isReccoBeatsContentEnvelope(data: unknown): data is { content: unknown[] } {
  if (!data || typeof data !== 'object') {
    return false;
  }
  return Array.isArray((data as { content?: unknown }).content);
}

export interface MapContentResult<T> {
  bySpotifyId: Map<string, T>;
  unparseableCount: number;
}

/**
 * Map ReccoBeats `content` rows keyed by Spotify track ID from `href`.
 * Skips + logs rows that fail the row guard or lack a parseable `href`.
 * Does **not** write negative sentinels for parse failures (caller responsibility).
 */
export function mapReccoBeatsContentBySpotifyId<T extends { href?: string }>(
  content: unknown[],
  isRow: (row: unknown) => row is T,
  endpoint: 'audio-features' | 'track'
): MapContentResult<T> {
  const bySpotifyId = new Map<string, T>();
  let unparseableCount = 0;

  for (const item of content) {
    if (!isRow(item)) {
      unparseableCount += 1;
      logger.warn('Skipping malformed ReccoBeats content row', {
        endpoint,
        reason: 'row_guard_failed',
      });
      continue;
    }

    const spotifyId = parseSpotifyTrackIdFromHref(item.href);
    if (!spotifyId) {
      unparseableCount += 1;
      logger.warn('Skipping ReccoBeats content row with missing/unparseable href', {
        endpoint,
        reason: 'href_unparseable',
        // Never log ReccoBeats UUID as if it were a Spotify ID; include only for diagnostics.
        reccobeatsId: typeof (item as unknown as { id?: unknown }).id === 'string'
          ? (item as unknown as { id: string }).id
          : undefined,
      });
      continue;
    }

    bySpotifyId.set(spotifyId, item);
  }

  return { bySpotifyId, unparseableCount };
}

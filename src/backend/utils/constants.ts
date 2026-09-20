/** Pitch-class names for ReccoBeats/Spotify `key` values 0-11 (0 = C). */
export const MUSIC_KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const;

/** Mode names for ReccoBeats/Spotify `mode` values (0 = minor, 1 = major). */
export const MODE_NAMES: Record<number, string> = { 0: 'minor', 1: 'major' };

/** Bumped whenever the shape of `AnalysisResult` changes in a way that stale cached results can't satisfy. */
export const ANALYSIS_SCHEMA_VERSION = '1.1';

/** Delay between ReccoBeats audio-features batch concurrency groups, to avoid bursting the rate limit. */
export const RECCOBEATS_JITTER_DELAY_MS = 50;

/** Positive per-track ReccoBeats enrichment TTL (6 months). */
export const RECCOBEATS_TRACK_ENRICHMENT_TTL_SECONDS = 15_552_000;

/** Per-endpoint negative (absent) sentinel TTL (7 days). */
export const RECCOBEATS_NEGATIVE_CACHE_TTL_SECONDS = 604_800;

/** Max ReccoBeats IDs per HTTP request (upstream rejects larger batches). */
export const RECCOBEATS_BATCH_SIZE = 30;

/** Bound concurrent ReccoBeats HTTP batch groups. */
export const RECCOBEATS_HTTP_CONCURRENCY = 3;

/** Bound concurrent KV get/put/delete for known per-track keys. */
export const RECCOBEATS_KV_CONCURRENCY = 25;

/**
 * Default TTL for cached analysis results. Overridable per-environment via
 * the `ANALYSIS_RESULTS_TTL_SECONDS` Worker var (see `Env`); this constant is
 * the fallback when that var is unset.
 */
export const ANALYSIS_RESULTS_TTL_SECONDS = 86400;

/**
 * TTL for fan-out job state (track snapshot + chunk partials). Bounds the
 * lifetime of orphaned countdowns/partials if a job dies mid-flight.
 */
export const FANOUT_STATE_TTL_SECONDS = 3600;

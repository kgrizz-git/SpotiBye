/** Pitch-class names for ReccoBeats/Spotify `key` values 0-11 (0 = C). */
export const MUSIC_KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'] as const;

/** Mode names for ReccoBeats/Spotify `mode` values (0 = minor, 1 = major). */
export const MODE_NAMES: Record<number, string> = { 0: 'minor', 1: 'major' };

/** Bumped whenever the shape of `AnalysisResult` changes in a way that stale cached results can't satisfy. */
export const ANALYSIS_SCHEMA_VERSION = '1.0';

/** Delay between ReccoBeats audio-features batch concurrency groups, to avoid bursting the rate limit. */
export const RECCOBEATS_JITTER_DELAY_MS = 50;

/**
 * Default TTL for cached analysis results. Overridable per-environment via
 * the `ANALYSIS_RESULTS_TTL_SECONDS` Worker var (see `Env`); this constant is
 * the fallback when that var is unset.
 */
export const ANALYSIS_RESULTS_TTL_SECONDS = 86400;

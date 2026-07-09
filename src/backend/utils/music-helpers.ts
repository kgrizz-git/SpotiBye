import { MUSIC_KEYS, MODE_NAMES } from './constants';

/**
 * Name for a pitch-class `key` value (0-11), or `null` when out of range.
 * Callers map `null` to a display fallback themselves — this must not
 * return a truthy placeholder like `'N/A'`.
 */
export function keyName(key: number | undefined | null): string | null {
  if (typeof key !== 'number' || key < 0 || key >= MUSIC_KEYS.length) {
    return null;
  }
  return MUSIC_KEYS[key];
}

/**
 * Name for a `mode` value (0 = minor, 1 = major), or `null` when unknown.
 */
export function modeName(mode: number | undefined | null): string | null {
  if (typeof mode !== 'number') {
    return null;
  }
  return MODE_NAMES[mode] ?? null;
}

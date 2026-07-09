/**
 * Compares two `"major.minor"` schema-version strings as positive integers
 * (no `v` prefix, no pre-release suffix) — numeric compare, so `"1.10" >
 * "1.9"`. Returns `-1` if `a < b`, `0` if equal, `1` if `a > b`.
 *
 * Callers use `compareVersions(schema_version, ANALYSIS_SCHEMA_VERSION) < 0`
 * to detect a stale cached result.
 */
export function compareVersions(a: string, b: string): -1 | 0 | 1 {
  const [aMajor, aMinor] = parseVersion(a);
  const [bMajor, bMinor] = parseVersion(b);

  if (aMajor !== bMajor) return aMajor < bMajor ? -1 : 1;
  if (aMinor !== bMinor) return aMinor < bMinor ? -1 : 1;
  return 0;
}

function parseVersion(version: string): [number, number] {
  const [major, minor] = version.split('.').map((part) => parseInt(part, 10));
  return [major || 0, minor || 0];
}

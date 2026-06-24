export function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours > 0) {
    return `${hours}:${remainingMinutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }
  return `${remainingMinutes}:${seconds.toString().padStart(2, '0')}`;
}

export function getTrackHeaders(): string[] {
  return [
    'Artist',
    'Album',
    'Track',
    'Duration',
    'Spotify URL',
    'Tempo',
    'Key',
    'Danceability',
    'Energy',
    'Valence',
    'Acousticness',
    'Instrumentalness',
    'Liveness',
    'Speechiness',
    'Loudness',
    'Time Signature',
  ];
}

export function sanitizeSheetName(name: string): string {
  const cleaned = name.replace(/[\\/*?:[\]]/g, ' ').trim();
  return (cleaned || 'Playlist').slice(0, 31);
}

// Make a sheet name unique within `usedNames` (case-insensitive, per Excel).
// Appends " (N)" with N starting at 2, shrinking the base to fit within 31 chars.
export function uniquifySheetName(base: string, usedNames: Set<string>): string {
  const key = base.toLowerCase();
  if (!usedNames.has(key)) {
    usedNames.add(key);
    return base;
  }
  for (let n = 2; n <= 9999; n += 1) {
    const suffix = ` (${n})`;
    const candidate = base.slice(0, 31 - suffix.length) + suffix;
    const candidateKey = candidate.toLowerCase();
    if (!usedNames.has(candidateKey)) {
      usedNames.add(candidateKey);
      return candidate;
    }
  }
  return base; // unreachable in practice
}

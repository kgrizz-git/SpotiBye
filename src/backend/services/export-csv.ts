import type { ExportData, ResumableExportAssemblyState } from './export-types';
import { getTrackHeaders } from './export-format-helpers';

export function escapeCsvValue(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

export async function generateCsvFile(exportData: ExportData): Promise<ArrayBuffer> {
  const headers = getTrackHeaders();
  let csvContent = headers.join(',') + '\n';
  // Metadata row padded to the header width; values sit in columns A, E, and I.
  const metadataRow: string[] = new Array<string>(headers.length).fill('');
  metadataRow[0] = `"Playlist: ${exportData.playlist.name}"`;
  metadataRow[4] = `"Total Tracks: ${exportData.playlist.total_tracks}"`;
  metadataRow[8] = `"Owner: ${exportData.playlist.owner}"`;
  csvContent += metadataRow.join(',') + '\n';
  csvContent += '\n';
  for (const track of exportData.tracks) {
    const row = headers.map((header) => escapeCsvValue(String(track[header] ?? '')));
    csvContent += row.join(',') + '\n';
  }
  const encoder = new TextEncoder();
  return encoder.encode(csvContent).buffer as ArrayBuffer;
}

export async function buildCsvChunk(exportData: ExportData): Promise<string> {
  const csvBytes = await generateCsvFile(exportData);
  return new TextDecoder().decode(csvBytes);
}

export async function generateCombinedCsvFromAssembly(
  assemblyState: ResumableExportAssemblyState,
): Promise<ArrayBuffer> {
  return new TextEncoder().encode(assemblyState.csv_chunks.join('\n\n')).buffer as ArrayBuffer;
}

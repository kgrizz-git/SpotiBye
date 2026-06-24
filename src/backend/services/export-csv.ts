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
  csvContent += `"Playlist: ${exportData.playlist.name}",,,,"Total Tracks: ${exportData.playlist.total_tracks}",,,,"Owner: ${exportData.playlist.owner}",,,,,,,\n`;
  csvContent += '\n';
  for (const track of exportData.tracks) {
    const row = headers.map((header) => escapeCsvValue(String((track as any)[header] ?? '')));
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

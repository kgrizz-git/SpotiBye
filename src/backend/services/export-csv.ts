import type { ExportData, ResumableExportAssemblyState } from './export-types';
import { getTrackHeaders } from './export-format-helpers';

/**
 * Prefix a cell that a spreadsheet would run as a formula (=, +, @, tab, CR,
 * or a non-numeric leading -) with a quote, per OWASP CSV-injection guidance.
 * Plain negative numbers such as `-5.2` are left alone.
 */
function neutralizeFormula(value: string): string {
  const isFormulaLike =
    /^[=+@\t\r]/.test(value) || (value.startsWith('-') && Number.isNaN(Number(value)));
  return isFormulaLike ? `'${value}` : value;
}

export function escapeCsvValue(value: string): string {
  const safe = neutralizeFormula(value);
  if (/[",\r\n]/.test(safe)) {
    return `"${safe.replaceAll('"', '""')}"`;
  }
  return safe;
}

export async function generateCsvFile(exportData: ExportData): Promise<ArrayBuffer> {
  const headers = getTrackHeaders();
  let csvContent = headers.join(',') + '\n';
  // Metadata row padded to the header width; values sit in columns A, E, and I.
  const metadataRow: string[] = new Array<string>(headers.length).fill('');
  metadataRow[0] = escapeCsvValue(`Playlist: ${exportData.playlist.name}`);
  metadataRow[4] = escapeCsvValue(`Total Tracks: ${exportData.playlist.total_tracks}`);
  metadataRow[8] = escapeCsvValue(`Owner: ${exportData.playlist.owner}`);
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

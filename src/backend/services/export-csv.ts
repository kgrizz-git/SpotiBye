import type { ExportData, ResumableExportAssemblyState } from './export-types';
import { getTrackHeaders } from './export-format-helpers';

// A formula trigger: =, +, @, tab, CR, LF, or their full-width forms.
const LEADING_FORMULA_TRIGGER = /^[=+@\t\r\n\uFF1D\uFF0B\uFF20]/;

/**
 * True when a spreadsheet would run `segment` as a formula: it starts with a
 * formula trigger, or with - / － and the whole segment is not a number.
 */
function isFormulaLike(segment: string): boolean {
  return (
    LEADING_FORMULA_TRIGGER.test(segment) ||
    (/^[-\uFF0D]/.test(segment) && !Number.isFinite(Number(segment)))
  );
}

/**
 * Prefix formula-like text with a quote, per OWASP CSV-injection guidance.
 * That covers a leading =, +, @, tab, CR, LF, their full-width forms
 * (＝ ＋ ＠), and a leading - or － unless the text is a plain number such as
 * `-5.2`.
 *
 * Excel in a locale whose list separator is `;` splits each line on `;` and
 * ignores the commas, and a quote only counts at the start of a field. So
 * every `;`-separated segment of a cell can become its own cell. Check each
 * segment the same way as the start of the cell.
 */
function neutralizeFormula(value: string): string {
  return value
    .split(';')
    .map((segment) => (isFormulaLike(segment) ? `'${segment}` : segment))
    .join(';');
}

export function escapeCsvValue(value: string): string {
  const safe = neutralizeFormula(value);
  // `;` too: Excel uses it as the list separator in many locales.
  if (/[",;\r\n]/.test(safe)) {
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

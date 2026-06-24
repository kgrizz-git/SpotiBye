import type { ExportData, ResumableExportAssemblyState, ResumableExportJobState } from './export-types';
import { formatDuration } from './export-format-helpers';
import { buildCsvChunk } from './export-csv';
import { buildWorksheetAssembly } from './export-xlsx-lite';

export function createAssemblyState(): ResumableExportAssemblyState {
  return {
    summary_headers: ['Playlist Name', 'Owner', 'Track Count', 'Duration'],
    summary_rows: [],
    worksheets: [],
    csv_chunks: [],
    next_assemble_index: 0,
  };
}

// Shared helper: push exportData into the assembly state (csv chunk or worksheet + summary row).
// Called inline during collect (pre-assembly) and during the assemble phase.
export async function preAssemblePlaylist(
  exportData: ExportData,
  job: Pick<ResumableExportJobState, 'file_format'>,
  assemblyState: ResumableExportAssemblyState,
): Promise<void> {
  if (job.file_format === 'csv') {
    assemblyState.csv_chunks.push(await buildCsvChunk(exportData));
  } else {
    const usedNames = new Set(assemblyState.worksheets.map((w) => w.sheet_name.toLowerCase()));
    assemblyState.worksheets.push(buildWorksheetAssembly(exportData, usedNames));
  }
  assemblyState.summary_rows.push([
    exportData.playlist.name,
    exportData.playlist.owner,
    exportData.tracks.length,
    formatDuration(exportData.total_duration_ms),
  ]);
}

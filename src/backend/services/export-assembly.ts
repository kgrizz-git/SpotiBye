import type {
  ExportData,
  ResumableExportAssemblyState,
  ResumableExportJobState,
  ResumableExportStepResult,
} from './export-types';
import { encodeCursor } from './export-cursor';
import { createResumeToken } from './export-job-state';
import { preAssemblePlaylist } from './export-assemble';
import { calculateAssembleProgress } from './export-collect';

export async function runAssembleStep(
  job: ResumableExportJobState,
  exportDataList: ExportData[],
  assemblyState: ResumableExportAssemblyState,
  maxPlaylistsPerStep: number,
  startAssembleIndex: number,
): Promise<ResumableExportStepResult> {
  const totalPlaylists = exportDataList.length;
  let assembleIndex = Math.max(0, startAssembleIndex || assemblyState.next_assemble_index || job.assemble_index || 0);
  let remaining = Math.max(maxPlaylistsPerStep, 1);

  while (remaining > 0 && assembleIndex < totalPlaylists) {
    const exportData = exportDataList[assembleIndex];

    // Playlists with no tracks were pre-assembled inline during the collect phase — skip them.
    if (exportData.tracks.length === 0) {
      assembleIndex += 1;
      continue;
    }

    await preAssemblePlaylist(exportData, job, assemblyState);
    assembleIndex += 1;
    remaining -= 1;
  }

  assemblyState.next_assemble_index = assembleIndex;
  job.phase = 'assemble';
  job.status = assembleIndex >= totalPlaylists ? 'completed' : 'assembling';
  job.assemble_index = assembleIndex;
  job.updated_at = new Date().toISOString();
  job.last_completed_cursor = job.current_cursor;
  job.last_completed_token = job.current_resume_token;

  if (assembleIndex >= totalPlaylists) {
    job.progress = 100;
    job.continuation_required = false;
    job.completed_at = new Date().toISOString();
    job.file_url = `/export/jobs/${job.job_id}/download`;
    job.file_size = JSON.stringify(assemblyState).length;
    job.result = { download_id: job.job_id };
  } else {
    job.progress = calculateAssembleProgress(job, totalPlaylists);
    job.continuation_required = true;
  }

  job.current_cursor = encodeCursor(job.next_playlist_index, 'assemble', 0, assembleIndex);
  job.current_resume_token = createResumeToken();
  return { job, exportDataList, assemblyState };
}

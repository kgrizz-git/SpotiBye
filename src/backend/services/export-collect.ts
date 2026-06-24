import type {
  ExportData,
  ResumableExportAssemblyState,
  ResumableExportJobState,
  ResumableExportStepResult,
} from './export-types';
import { encodeCursor } from './export-cursor';
import { createResumeToken } from './export-job-state';
import { preAssemblePlaylist } from './export-assemble';
import { buildExportTracks, calculateTotalDurationMs, buildPlaylistMetadata } from './export-tracks';
import { SpotifyService } from './spotify';

export function mergeExportSlice(
  existingExportData: ExportData | undefined,
  sliceExportData: ExportData,
): ExportData {
  if (!existingExportData) {
    return sliceExportData;
  }
  return {
    playlist: {
      ...existingExportData.playlist,
      ...sliceExportData.playlist,
    },
    tracks: [...existingExportData.tracks, ...sliceExportData.tracks],
    total_duration_ms: existingExportData.total_duration_ms + sliceExportData.total_duration_ms,
    generated_at: sliceExportData.generated_at,
  };
}

export function calculateJobProgress(job: ResumableExportJobState): number {
  const playlistIds = job.playlist_ids;
  if (playlistIds.length === 0) {
    return 100;
  }
  let aggregateProgress = 0;
  for (const playlistId of playlistIds) {
    const progress = job.playlist_progress[playlistId];
    if (!progress) {
      continue;
    }
    if (progress.done) {
      aggregateProgress += 1;
      continue;
    }
    if (progress.total_tracks > 0) {
      aggregateProgress += Math.min(progress.collected_tracks / progress.total_tracks, 0.99);
    }
  }
  return Math.min(99, Math.floor((aggregateProgress / playlistIds.length) * 100));
}

export function calculateAssembleProgress(job: ResumableExportJobState, totalPlaylists: number): number {
  if (totalPlaylists <= 0) {
    return 100;
  }
  const assembleProgress = Math.min(job.assemble_index / totalPlaylists, 0.99);
  return Math.min(99, 95 + Math.floor(assembleProgress * 4));
}

export async function generatePlaylistExportSlice(
  accessToken: string,
  playlistId: string,
  options: {
    includeAudioFeatures?: boolean;
    offset?: number;
    limit?: number;
    existingExportData?: ExportData;
  },
): Promise<{ exportData: ExportData; fetchedCount: number; rawCount: number; totalTracks: number }> {
  const spotifyService = new SpotifyService(accessToken);
  const includeAudioFeatures = options.includeAudioFeatures === true;
  const offset = Math.max(0, options.offset || 0);
  const limit = Math.max(1, options.limit || 100);
  const existingExportData = options.existingExportData;
  const playlist = existingExportData?.playlist.id === playlistId
    ? undefined
    : await spotifyService.getPlaylist(playlistId);
  const tracksData = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
  const exportTracks = await buildExportTracks(tracksData.items, includeAudioFeatures, spotifyService);
  const totalDurationMs = calculateTotalDurationMs(tracksData.items);
  const playlistMetadata = existingExportData?.playlist || buildPlaylistMetadata(playlist, tracksData.total);

  return {
    exportData: {
      playlist: {
        ...playlistMetadata,
        total_tracks: tracksData.total || playlistMetadata.total_tracks,
      },
      tracks: exportTracks,
      total_duration_ms: totalDurationMs,
      generated_at: new Date().toISOString(),
    },
    fetchedCount: tracksData.items.length,
    rawCount: tracksData.rawCount,
    totalTracks: tracksData.total,
  };
}

export async function runCollectStep(
  accessToken: string,
  job: ResumableExportJobState,
  exportDataList: ExportData[],
  assemblyState: ResumableExportAssemblyState,
  maxPlaylistsPerStep: number,
  startPlaylistIndex: number,
  startTrackOffset: number,
): Promise<ResumableExportStepResult> {
  let nextPlaylistIndex = startPlaylistIndex;
  let nextTrackOffset = startTrackOffset;
  let remainingSlices = Math.max(maxPlaylistsPerStep, 1);

  while (remainingSlices > 0 && nextPlaylistIndex < job.playlist_ids.length) {
    const playlistId = job.playlist_ids[nextPlaylistIndex];
    const existingExportData = exportDataList.find((item) => item.playlist.id === playlistId);
    const playlistProgress = job.playlist_progress[playlistId] || {
      next_offset: nextTrackOffset,
      total_tracks: existingExportData?.playlist.total_tracks || 0,
      collected_tracks: existingExportData?.tracks.length || 0,
      done: false,
    };
    const slice = await generatePlaylistExportSlice(accessToken, playlistId, {
      includeAudioFeatures: job.include_audio_features,
      offset: playlistProgress.next_offset,
      limit: job.track_page_size,
      existingExportData,
    });

    const mergedExportData = mergeExportSlice(existingExportData, slice.exportData);
    const existingIndex = exportDataList.findIndex((item) => item.playlist.id === playlistId);

    const totalTracks = slice.totalTracks || mergedExportData.playlist.total_tracks || mergedExportData.tracks.length;
    const collectedTracks = mergedExportData.tracks.length;
    // Advance the Spotify cursor by the raw page size (Spotify's `total` and
    // offsets count local/unavailable items that we filter out of `items`).
    const rawOffsetAfter = playlistProgress.next_offset + slice.rawCount;
    const playlistDone = slice.rawCount === 0
      || slice.rawCount < job.track_page_size
      || rawOffsetAfter >= totalTracks;

    job.playlist_progress[playlistId] = {
      next_offset: rawOffsetAfter,
      total_tracks: totalTracks,
      collected_tracks: collectedTracks,
      done: playlistDone,
    };

    if (playlistDone) {
      // Pre-assemble immediately to prevent raw track data accumulating in KV across steps.
      await preAssemblePlaylist(mergedExportData, job, assemblyState);
      assemblyState.next_assemble_index = (assemblyState.next_assemble_index || 0) + 1;

      // Store a tracks-free sentinel so the assemble phase can identify pre-assembled entries.
      const strippedData = { ...mergedExportData, tracks: [] as typeof mergedExportData.tracks };
      if (existingIndex >= 0) {
        exportDataList[existingIndex] = strippedData;
      } else {
        exportDataList.push(strippedData);
      }

      nextPlaylistIndex += 1;
      nextTrackOffset = 0;
    } else {
      if (existingIndex >= 0) {
        exportDataList[existingIndex] = mergedExportData;
      } else {
        exportDataList.push(mergedExportData);
      }
      nextTrackOffset = job.playlist_progress[playlistId].next_offset;
    }

    remainingSlices -= 1;
  }

  job.next_playlist_index = nextPlaylistIndex;
  job.current_track_offset = nextTrackOffset;
  job.processed_count = Object.values(job.playlist_progress).filter((progress) => progress.done).length;
  job.track_count = Object.values(job.playlist_progress).reduce((sum, p) => sum + p.collected_tracks, 0);
  job.updated_at = new Date().toISOString();
  job.last_completed_cursor = job.current_cursor;
  job.last_completed_token = job.current_resume_token;

  if (job.next_playlist_index >= job.playlist_ids.length) {
    const preAssembledCount = assemblyState.next_assemble_index || 0;
    const totalPlaylists = job.playlist_ids.length;
    job.phase = 'assemble';
    job.assemble_index = preAssembledCount;

    if (preAssembledCount >= totalPlaylists) {
      // All playlists were pre-assembled inline during collect — complete immediately.
      job.status = 'completed';
      job.progress = 100;
      job.continuation_required = false;
      job.completed_at = new Date().toISOString();
      job.file_url = `/export/jobs/${job.job_id}/download`;
      job.file_size = JSON.stringify(assemblyState).length;
      job.result = { download_id: job.job_id };
    } else {
      job.status = 'assembling';
      job.progress = calculateAssembleProgress(job, totalPlaylists);
      job.continuation_required = true;
    }

    job.current_cursor = encodeCursor(job.next_playlist_index, 'assemble', 0, job.assemble_index);
    job.current_resume_token = createResumeToken();
    return { job, exportDataList, assemblyState };
  }

  job.phase = 'collect';
  job.status = 'running';
  job.continuation_required = true;
  job.progress = calculateJobProgress(job);
  job.current_cursor = encodeCursor(job.next_playlist_index, 'collect', job.current_track_offset, job.assemble_index);
  job.current_resume_token = createResumeToken();

  return { job, exportDataList, assemblyState };
}

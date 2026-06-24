export function buildExportJobKey(jobId: string, userId: string): string {
  return `export:job:${jobId}:${userId}`;
}

export function buildExportJobDataKey(jobId: string, userId: string): string {
  return `${buildExportJobKey(jobId, userId)}:data`;
}

export function buildExportJobAssemblyKey(jobId: string, userId: string): string {
  return `${buildExportJobKey(jobId, userId)}:assembly`;
}

// mode: 'default' = canonical export file (served by fallback chain)
//       'rich' | 'lite' = XLSX render variants (served by mode query)
//       'csv' = pre-built CSV write target only — never selected by the fallback chain
export function buildExportFileKey(baseKey: string, mode: 'default' | 'rich' | 'lite' | 'csv' = 'default'): string {
  if (mode === 'default') {
    return `${baseKey}:file`;
  }
  return `${baseKey}:file:${mode}`;
}

export function buildBatchKey(jobId: string, userId: string): string {
  return `export:batch:${jobId}:${userId}`;
}

export function buildBatchDataKey(jobId: string, userId: string): string {
  return `${buildBatchKey(jobId, userId)}:data`;
}

export function buildBatchFileKey(jobId: string, userId: string): string {
  return `${buildBatchKey(jobId, userId)}:file`;
}

export function buildSingleExportKey(playlistId: string, userId: string): string {
  return `export:${playlistId}:${userId}`;
}

export function buildSingleExportDataKey(playlistId: string, userId: string): string {
  return `${buildSingleExportKey(playlistId, userId)}:data`;
}

export function buildSingleExportFileKey(playlistId: string, userId: string): string {
  return `${buildSingleExportKey(playlistId, userId)}:file`;
}

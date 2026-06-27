export function buildExportJobKey(jobId: string, userId: string): string {
  return `export:job:${jobId}:${userId}`;
}

export function buildExportJobDataKey(jobId: string, userId: string): string {
  return `${buildExportJobKey(jobId, userId)}:data`;
}

export function buildExportJobAssemblyKey(jobId: string, userId: string): string {
  return `${buildExportJobKey(jobId, userId)}:assembly`;
}

/** canonical fallback slot */
export function buildExportFileKey(baseKey: string): string {
  return `${baseKey}:file`;
}

/** XLSX render variants rich/lite */
export function buildXlsxVariantKey(baseKey: string, variant: 'rich' | 'lite'): string {
  return `${baseKey}:file:${variant}`;
}

/** prebuilt format slots like csv */
export function buildPrebuiltFormatKey(baseKey: string, format: 'csv'): string {
  return `${baseKey}:file:${format}`;
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

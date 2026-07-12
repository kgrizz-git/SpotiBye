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

import type { ExportFormat } from './types';

export interface SingleExportKeyOptions {
  format?: ExportFormat;
  /** When true, export includes ReccoBeats enrichment columns. */
  includeEnrichment?: boolean;
}

export function buildSingleExportKey(
  playlistId: string,
  userId: string,
  options?: SingleExportKeyOptions,
): string {
  const base = `export:${playlistId}:${userId}`;
  if (!options) {
    return base;
  }
  const format = options.format ?? 'xlsx';
  const enrichment = options.includeEnrichment === true ? 'enriched' : 'plain';
  return `${base}:${format}:${enrichment}`;
}

/** Prefix for single-export KV keys (all format/enrichment variants). */
export function buildSingleExportPrefix(playlistId: string, userId: string): string {
  return `export:${playlistId}:${userId}`;
}

export function buildSingleExportDataKey(
  playlistId: string,
  userId: string,
  options?: SingleExportKeyOptions,
): string {
  return `${buildSingleExportKey(playlistId, userId, options)}:data`;
}

export function buildSingleExportFileKey(
  playlistId: string,
  userId: string,
  options?: SingleExportKeyOptions,
): string {
  return `${buildSingleExportKey(playlistId, userId, options)}:file`;
}

/** Points at the most recent single-export variant (format + enrichment). */
export function buildSingleExportLatestKey(playlistId: string, userId: string): string {
  return `${buildSingleExportPrefix(playlistId, userId)}:latest`;
}

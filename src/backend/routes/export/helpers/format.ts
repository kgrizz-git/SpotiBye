import type { XlsxRenderMode } from '../../../services/export';
import type { ExportFormat } from './types';

export function parseXlsxRenderMode(value: string | undefined): XlsxRenderMode {
  const normalized = String(value || '').toLowerCase();
  if (normalized === 'rich' || normalized === 'lite') {
    return normalized;
  }
  return 'auto';
}

export function resolveRequestedFormat(body: Record<string, unknown>): ExportFormat {
  const format = String(body?.format || '').toLowerCase();
  if (format === 'csv') return 'csv';
  if (format === 'json') return 'json';
  return 'xlsx';
}

// Normalize a persisted file_format value (untrusted KV/JSON) to a known format.
export function resolveStoredFormat(value: unknown): ExportFormat {
  return value === 'csv' ? 'csv' : value === 'json' ? 'json' : 'xlsx';
}

// HTTP Content-Type + filename extension for a given export format.
export function formatHttpMeta(format: ExportFormat): [string, string] {
  if (format === 'csv') return ['text/csv; charset=utf-8', 'csv'];
  if (format === 'json') return ['application/json; charset=utf-8', 'json'];
  return ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'];
}

export function resolveIncludeAudioFeatures(body: Record<string, unknown>): boolean {
  // Semantics: include ReccoBeats per-track enrichment columns (not Spotify /audio-features).
  return body?.include_audio_features === true;
}

export function resolveStepSize(body: Record<string, unknown>): number {
  const requested = Number.isInteger(body?.max_playlists_per_step)
    ? Number(body.max_playlists_per_step)
    : Number.isInteger(body?.chunk_size)
      ? Number(body.chunk_size)
      : 1;
  return Math.min(Math.max(requested, 1), 3);
}

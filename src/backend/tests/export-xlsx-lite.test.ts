import { describe, it, expect } from 'vitest';
import { buildWorksheetAssembly } from '../services/export-xlsx-lite';
import type { ExportData } from '../services/export-types';
import { makeExportData } from './helpers/export-data';

const sampleExportData: ExportData = makeExportData();

describe('buildWorksheetAssembly', () => {
  it('maps ExportTrack rows to header-keyed values', () => {
    const usedNames = new Set<string>();
    const result = buildWorksheetAssembly(sampleExportData, usedNames);

    expect(result.playlist_name).toBe('Road Trip');
    expect(result.playlist_owner).toBe('alice');
    expect(result.playlist_followers).toBe(42);
    expect(result.headers).toContain('Artist');
    expect(result.headers).toContain('Time Signature');
    expect(result.rows).toHaveLength(1);

    // Row values should correspond to headers
    const artistIdx = result.headers.indexOf('Artist');
    expect(result.rows[0][artistIdx]).toBe('Artist A');
  });

  it('uses empty string fallback for missing track fields', () => {
    const sparseTrack = { Artist: 'Only Artist' } as any;
    const data: ExportData = { ...sampleExportData, tracks: [sparseTrack] };
    const result = buildWorksheetAssembly(data, new Set());
    const tempoIdx = result.headers.indexOf('Tempo');
    expect(result.rows[0][tempoIdx]).toBe('');
  });

  it('uniquifies sheet name on collision', () => {
    const usedNames = new Set(['road trip - alice']);
    const result = buildWorksheetAssembly(sampleExportData, usedNames);
    expect(result.sheet_name).toContain('(2)');
  });

  it('formats total_duration from total_duration_ms', () => {
    const result = buildWorksheetAssembly(sampleExportData, new Set());
    expect(result.total_duration).toBe('3:21');
  });
});

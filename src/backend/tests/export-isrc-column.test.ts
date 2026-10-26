import { describe, it, expect } from 'vitest';
import ExcelJS from 'exceljs';
import { generateCsvFile } from '../services/export-csv';
import { generateCombinedExcelFile } from '../services/export-xlsx';
import { buildWorksheetAssembly } from '../services/export-xlsx-lite';
import { getTrackHeaders } from '../services/export-format-helpers';
import type { ExportData, ExportTrack } from '../services/export-types';

const track: ExportTrack = {
  Artist: 'Artist A',
  Album: 'Album A',
  Track: 'Track A',
  Duration: '3:21',
  'Spotify URL': 'https://open.spotify.com/track/a',
  Tempo: 120,
  Key: 'C major',
  Danceability: 0.8,
  Energy: 0.9,
  Valence: 0.5,
  Acousticness: 0.1,
  Instrumentalness: 0,
  Liveness: 0.2,
  Speechiness: 0.05,
  Loudness: -5,
  'Time Signature': 'N/A',
  ISRC: 'USUG12103683',
};

const exportData: ExportData = {
  playlist: {
    id: 'pl1',
    name: 'Road Trip',
    description: '',
    total_tracks: 1,
    owner: 'alice',
    followers: 0,
    url: 'https://open.spotify.com/playlist/pl1',
  },
  tracks: [track],
  total_duration_ms: 201000,
  generated_at: '2026-10-25T00:00:00Z',
};

describe('ISRC export column', () => {
  it('writes ISRC as the last CSV column, with every row the header width', async () => {
    const text = new TextDecoder().decode(await generateCsvFile(exportData));
    const lines = text.split('\n');
    const width = getTrackHeaders().length;

    expect(lines[0].split(',').at(-1)).toBe('ISRC');
    // Metadata row: no commas inside its quoted values here, so a plain split is safe.
    expect(lines[1].split(',')).toHaveLength(width);
    expect(lines[3].split(',')).toHaveLength(width);
    expect(lines[3].split(',').at(-1)).toBe('USUG12103683');
  });

  it('writes ISRC to column Q of the rich XLSX sheet and keeps the URL in column E', async () => {
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.load(await generateCombinedExcelFile([exportData]));
    const sheet = workbook.worksheets.find((ws) => ws.getCell('A11').value === 'Artist');

    expect(sheet).toBeDefined();
    expect(sheet!.getCell('Q11').value).toBe('ISRC');
    expect(sheet!.getCell('Q12').value).toBe('USUG12103683');
    expect(sheet!.getCell('E11').value).toBe('Spotify URL');
  });

  it('puts ISRC last in the lite XLSX assembly rows', () => {
    const result = buildWorksheetAssembly(exportData, new Set());
    expect(result.headers.at(-1)).toBe('ISRC');
    expect(result.rows[0].at(-1)).toBe('USUG12103683');
  });
});

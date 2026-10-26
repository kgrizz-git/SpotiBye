import { describe, it, expect } from 'vitest';
import ExcelJS from 'exceljs';
import { generateCsvFile } from '../services/export-csv';
import { generateCombinedJson } from '../services/export-json';
import { generateCombinedExcelFile } from '../services/export-xlsx';
import { buildWorksheetAssembly, generateCombinedExcelFileFromAssemblyLite } from '../services/export-xlsx-lite';
import { getTrackHeaders } from '../services/export-format-helpers';
import type { ExportData } from '../services/export-types';
import { makeExportData, makeExportTrack } from './helpers/export-data';

// One track with a known ISRC, one with none.
const exportData: ExportData = makeExportData({
  tracks: [makeExportTrack(), makeExportTrack({ Track: 'Track B', ISRC: '' })],
});

async function loadSheet(bytes: ArrayBuffer): Promise<ExcelJS.Worksheet> {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(bytes);
  const sheet = workbook.worksheets.find((ws) => ws.getCell('A11').value === 'Artist');
  expect(sheet).toBeDefined();
  return sheet!;
}

function expectIsrcInColumnQ(sheet: ExcelJS.Worksheet): void {
  expect(sheet.getCell('E11').value).toBe('Spotify URL');
  expect(sheet.getCell('Q11').value).toBe('ISRC');
  expect(sheet.getCell('Q12').value).toBe('USUG12103683');
  expect(sheet.getCell('Q13').value ?? '').toBe('');
}

describe('ISRC export column', () => {
  it('writes ISRC as the last CSV column, with every row the header width', async () => {
    const lines = new TextDecoder().decode(await generateCsvFile(exportData)).split('\n');
    const width = getTrackHeaders().length;

    expect(lines[0].split(',').at(-1)).toBe('ISRC');
    // The quoted metadata values contain no commas, so a plain split is safe.
    expect(lines[1].split(',')).toHaveLength(width);
    for (const line of [lines[3], lines[4]]) {
      expect(line.split(',')).toHaveLength(width);
    }
    expect(lines[3].split(',').at(-1)).toBe('USUG12103683');
    expect(lines[4].split(',').at(-1)).toBe('');
  });

  it('escapes quotes, commas, and newlines in the CSV metadata row', async () => {
    const tricky = makeExportData({
      playlist: { ...makeExportData().playlist, name: 'Road "Trip", Vol. 1\nB-sides', owner: 'a,b' },
    });
    const text = new TextDecoder().decode(await generateCsvFile(tricky));
    // The quoted name spans a newline, so check the raw text rather than splitting lines.
    expect(text).toContain('"Playlist: Road ""Trip"", Vol. 1\nB-sides",,,,Total Tracks: 1,,,,"Owner: a,b"');
  });

  it('writes ISRC on every JSON track', () => {
    const payload = JSON.parse(new TextDecoder().decode(generateCombinedJson([exportData])));
    const tracks = payload.playlists[0].tracks;
    expect(tracks[0].ISRC).toBe('USUG12103683');
    expect(tracks[1].ISRC).toBe('');
  });

  it('writes ISRC to column Q of the rich XLSX file', async () => {
    expectIsrcInColumnQ(await loadSheet(await generateCombinedExcelFile([exportData])));
  });

  it('writes ISRC to column Q of the lite XLSX file', async () => {
    const worksheet = buildWorksheetAssembly(exportData, new Set());
    const bytes = await generateCombinedExcelFileFromAssemblyLite({
      summary_headers: ['Playlist Name', 'Owner', 'Track Count', 'Duration'],
      summary_rows: [],
      csv_chunks: [],
      next_assemble_index: 1,
      worksheets: [worksheet],
    });
    expectIsrcInColumnQ(await loadSheet(bytes));
  });
});

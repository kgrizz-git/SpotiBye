import { describe, it, expect } from 'vitest';
import { escapeCsvValue, generateCombinedCsvFromAssembly, generateCsvFile } from '../services/export-csv';
import { makeExportData, makeExportTrack } from './helpers/export-data';
import type { ResumableExportAssemblyState } from '../services/export-types';

describe('escapeCsvValue', () => {
  // [why, input, expected output]
  const cases: Array<[string, string, string]> = [
    ['plain text', 'hello', 'hello'],
    ['plain number', '123', '123'],
    ['negative number', '-5.2', '-5.2'],
    ['negative integer', '-60', '-60'],
    ['comma', 'a,b', '"a,b"'],
    ['semicolon', 'a;b', '"a;b"'],
    ['double quote', 'say "hi"', '"say ""hi"""'],
    ['only quotes', '"quoted"', '"""quoted"""'],
    ['newline', 'line1\nline2', '"line1\nline2"'],
    ['bare carriage return', 'a\rb', '"a\rb"'],
    ['leading =', '=SUM(A1:A2)', "'=SUM(A1:A2)"],
    ['leading +', '+1+1', "'+1+1"],
    ['leading @', '@cmd', "'@cmd"],
    ['leading non-numeric -', '-x+1', "'-x+1"],
    ['leading tab', '\t=1', "'\t=1"],
    ['leading full-width =', '\uFF1DSUM(A1)', "'\uFF1DSUM(A1)"],
    ['leading full-width +', '\uFF0B1', "'\uFF0B1"],
    ['leading full-width @', '\uFF20cmd', "'\uFF20cmd"],
    ['leading full-width -', '\uFF0D1', "'\uFF0D1"],
    ['neutralized and quoted', '=a,b', `"'=a,b"`],
    ['leading CR then =', '\r=1', `"'\r=1"`],
    ['leading LF then =', '\n=1', `"'\n=1"`],
    ['= after ;', 'safe;=1+1;tail', `"safe;'=1+1;tail"`],
    ['+ after ;', 'a;+1', `"a;'+1"`],
    ['@ after ;', 'a;@cmd', `"a;'@cmd"`],
    ['non-numeric - after ;', 'a;-x', `"a;'-x"`],
    ['full-width = after ;', 'a;\uFF1D1', `"a;'\uFF1D1"`],
    ['number after ;', 'a;-5', '"a;-5"'],
    ['space before = after ;', 'a; =1', '"a; =1"'],
  ];

  it.each(cases)('%s', (_why, input, expected) => {
    expect(escapeCsvValue(input)).toBe(expected);
  });
});

describe('generateCombinedCsvFromAssembly', () => {
  it('joins csv chunks with double newline', async () => {
    const state: ResumableExportAssemblyState = {
      summary_headers: [],
      summary_rows: [],
      worksheets: [],
      csv_chunks: ['chunk1', 'chunk2', 'chunk3'],
      next_assemble_index: 3,
    };
    const buffer = await generateCombinedCsvFromAssembly(state);
    const text = new TextDecoder().decode(buffer);
    expect(text).toBe('chunk1\n\nchunk2\n\nchunk3');
  });

  it('returns empty string for no chunks', async () => {
    const state: ResumableExportAssemblyState = {
      summary_headers: [],
      summary_rows: [],
      worksheets: [],
      csv_chunks: [],
      next_assemble_index: 0,
    };
    const buffer = await generateCombinedCsvFromAssembly(state);
    const text = new TextDecoder().decode(buffer);
    expect(text).toBe('');
  });
});

describe('CSV output read with a semicolon list separator', () => {
  it('exposes no formula cell when Excel splits a row on ;', async () => {
    const data = makeExportData({
      tracks: [makeExportTrack({ Track: 'safe;=1+1;tail', Artist: 'x;@SUM(A1)' })],
    });
    const lines = new TextDecoder().decode(await generateCsvFile(data)).split('\n');
    const trackRow = lines[3];
    // A semicolon-locale Excel splits on ; and ignores commas and mid-field quotes.
    const cells = trackRow.split(';');
    expect(cells.length).toBeGreaterThan(1);
    for (const cell of cells) {
      expect(cell).not.toMatch(/^[=+@\uFF1D\uFF0B\uFF20]/);
    }
  });
});

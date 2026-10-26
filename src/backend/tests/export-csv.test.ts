import { describe, it, expect } from 'vitest';
import { escapeCsvValue, generateCombinedCsvFromAssembly } from '../services/export-csv';
import type { ResumableExportAssemblyState } from '../services/export-types';

describe('escapeCsvValue', () => {
  it('passes through plain values unchanged', () => {
    expect(escapeCsvValue('hello')).toBe('hello');
    expect(escapeCsvValue('123')).toBe('123');
  });

  it('wraps in quotes when value contains a comma', () => {
    expect(escapeCsvValue('a,b')).toBe('"a,b"');
  });

  it('wraps in quotes when value contains a double quote', () => {
    expect(escapeCsvValue('say "hi"')).toBe('"say ""hi"""');
  });

  it('wraps in quotes when value contains a newline', () => {
    expect(escapeCsvValue('line1\nline2')).toBe('"line1\nline2"');
  });

  it('quotes a value containing a bare carriage return', () => {
    expect(escapeCsvValue('a\rb')).toBe('"a\rb"');
  });

  it.each([
    ['=SUM(A1:A2)', "'=SUM(A1:A2)"],
    ['+1+1', "'+1+1"],
    ['@cmd', "'@cmd"],
    ['-x+1', "'-x+1"],
    ['\t=1', "'\t=1"],
  ])('neutralizes the formula-like value %j', (input, expected) => {
    expect(escapeCsvValue(input)).toBe(expected);
  });

  it('quotes a neutralized value that also needs CSV quoting', () => {
    expect(escapeCsvValue('=a,b')).toBe(`"'=a,b"`);
    expect(escapeCsvValue('\r=1')).toBe(`"'\r=1"`);
  });

  it('leaves plain negative numbers alone', () => {
    expect(escapeCsvValue('-5.2')).toBe('-5.2');
    expect(escapeCsvValue('-60')).toBe('-60');
  });

  it('doubles embedded double quotes', () => {
    expect(escapeCsvValue('"quoted"')).toBe('"""quoted"""');
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

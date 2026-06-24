import { describe, it, expect, vi, afterEach } from 'vitest';
import { generateCombinedExcelFileFromAssembly } from '../services/export-xlsx';
import * as lite from '../services/export-xlsx-lite';
import type { ResumableExportAssemblyState } from '../services/export-types';

function makeAssemblyState(worksheetCount: number, rowsPerSheet: number): ResumableExportAssemblyState {
  return {
    summary_headers: ['Playlist Name', 'Owner', 'Track Count', 'Duration'],
    summary_rows: [],
    csv_chunks: [],
    next_assemble_index: worksheetCount,
    worksheets: Array.from({ length: worksheetCount }, (_, i) => ({
      sheet_name: `Sheet ${i + 1}`,
      playlist_name: `Playlist ${i + 1}`,
      playlist_owner: 'owner',
      playlist_followers: 0,
      playlist_description: '',
      playlist_url: '',
      total_duration: '1:00',
      headers: ['Artist', 'Track'],
      rows: Array.from({ length: rowsPerSheet }, () => ['Artist A', 'Track A']),
    })),
  };
}

describe('generateCombinedExcelFileFromAssembly renderer selection', () => {
  afterEach(() => vi.restoreAllMocks());

  it('uses lite renderer when renderMode is "lite"', async () => {
    const liteSpy = vi.spyOn(lite, 'generateCombinedExcelFileFromAssemblyLite')
      .mockResolvedValue(new ArrayBuffer(0));
    await generateCombinedExcelFileFromAssembly(makeAssemblyState(1, 1), 'lite');
    expect(liteSpy).toHaveBeenCalledTimes(1);
  });

  it('uses rich renderer when renderMode is "rich" (lite not called)', async () => {
    const liteSpy = vi.spyOn(lite, 'generateCombinedExcelFileFromAssemblyLite')
      .mockResolvedValue(new ArrayBuffer(0));
    // The rich renderer calls generateCombinedExcelFile which writes a real buffer
    // — we just verify lite was NOT called.
    try {
      await generateCombinedExcelFileFromAssembly(makeAssemblyState(1, 0), 'rich');
    } catch {
      // ExcelJS may error in test env; that's OK — we only care about lite not being called.
    }
    expect(liteSpy).not.toHaveBeenCalled();
  });

  it('auto mode: uses lite when worksheets > 18', async () => {
    const liteSpy = vi.spyOn(lite, 'generateCombinedExcelFileFromAssemblyLite')
      .mockResolvedValue(new ArrayBuffer(0));
    await generateCombinedExcelFileFromAssembly(makeAssemblyState(19, 1), 'auto');
    expect(liteSpy).toHaveBeenCalledTimes(1);
  });

  it('auto mode: uses lite when track rows > 2400', async () => {
    const liteSpy = vi.spyOn(lite, 'generateCombinedExcelFileFromAssemblyLite')
      .mockResolvedValue(new ArrayBuffer(0));
    // 1 worksheet with 2401 rows
    await generateCombinedExcelFileFromAssembly(makeAssemblyState(1, 2401), 'auto');
    expect(liteSpy).toHaveBeenCalledTimes(1);
  });

  it('auto mode: uses rich when worksheets <= 18 and rows <= 2400 (lite not called)', async () => {
    const liteSpy = vi.spyOn(lite, 'generateCombinedExcelFileFromAssemblyLite')
      .mockResolvedValue(new ArrayBuffer(0));
    try {
      await generateCombinedExcelFileFromAssembly(makeAssemblyState(1, 0), 'auto');
    } catch {
      // ExcelJS may error in test env
    }
    expect(liteSpy).not.toHaveBeenCalled();
  });
});

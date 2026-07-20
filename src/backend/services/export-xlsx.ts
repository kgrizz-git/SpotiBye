import ExcelJS from 'exceljs';
import type { ExportData, ResumableExportAssemblyState, ExportTrack, XlsxRenderMode } from './export-types';
import { formatDuration, getTrackHeaders, sanitizeSheetName, uniquifySheetName } from './export-format-helpers';
import { generateCombinedExcelFileFromAssemblyLite } from './export-xlsx-lite';

export function arrayBufferToBase64(bytes: ArrayBuffer): string {
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(bytes).toString('base64');
  }
  const byteArray = new Uint8Array(bytes);
  const chars = new Array<string>(byteArray.length);
  for (let i = 0; i < byteArray.length; i++) {
    chars[i] = String.fromCharCode(byteArray[i]);
  }
  return btoa(chars.join(''));
}

export async function tryAddCoverImage(
  workbook: ExcelJS.Workbook,
  sheet: ExcelJS.Worksheet,
  imageUrl?: string,
): Promise<void> {
  if (!imageUrl) {
    return;
  }
  try {
    const response = await fetch(imageUrl);
    if (!response.ok) {
      console.warn('[export] cover image fetch failed', { imageUrl, status: response.status });
      return;
    }
    const bytes = await response.arrayBuffer();
    const contentType = response.headers.get('content-type') || '';
    const extension = contentType.includes('jpeg') || contentType.includes('jpg') ? 'jpeg' : 'png';
    const mimeType = extension === 'jpeg' ? 'image/jpeg' : 'image/png';
    const base64 = arrayBufferToBase64(bytes);
    const imageId = workbook.addImage({
      base64: `data:${mimeType};base64,${base64}`,
      extension,
    });
    sheet.addImage(imageId, {
      tl: { col: 1.1, row: 0.1 },
      ext: { width: 120, height: 120 },
    });
  } catch (error) {
    console.warn('[export] cover image embedding failed', {
      imageUrl,
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

export async function generateCombinedExcelFile(exportDataList: ExportData[]): Promise<ArrayBuffer> {
  const workbook = new ExcelJS.Workbook();
  const summarySheet = workbook.addWorksheet('Playlists');
  summarySheet.columns = [
    { header: 'Playlist Name', key: 'name', width: 29 },
    { header: 'Owner', key: 'owner', width: 24 },
    { header: 'Track Count', key: 'track_count', width: 16 },
    { header: 'Duration', key: 'duration', width: 19 },
  ];

  const summaryHeader = summarySheet.getRow(1);
  summaryHeader.font = { bold: true, color: { argb: 'FFFFFFFF' }, size: 13 };
  summaryHeader.fill = {
    type: 'pattern',
    pattern: 'solid',
    fgColor: { argb: 'FF4F81BD' },
  };

  for (const exportData of exportDataList) {
    summarySheet.addRow({
      name: exportData.playlist.name,
      owner: exportData.playlist.owner,
      track_count: exportData.tracks.length,
      duration: formatDuration(exportData.total_duration_ms),
    });
  }

  const headers = getTrackHeaders();
  const usedSheetNames = new Set<string>();

  for (const exportData of exportDataList) {
    const baseName = sanitizeSheetName(`${exportData.playlist.name} - ${exportData.playlist.owner}`);
    const sheetName = uniquifySheetName(baseName, usedSheetNames);

    const sheet = workbook.addWorksheet(sheetName);
    sheet.columns = [
      { key: 'A', width: 30 },
      { key: 'B', width: 40 },
      { key: 'C', width: 40 },
      { key: 'D', width: 15 },
      { key: 'E', width: 60 },
      { key: 'F', width: 12 },
      { key: 'G', width: 14 },
      { key: 'H', width: 12 },
      { key: 'I', width: 12 },
      { key: 'J', width: 12 },
      { key: 'K', width: 12 },
      { key: 'L', width: 16 },
      { key: 'M', width: 12 },
      { key: 'N', width: 12 },
      { key: 'O', width: 12 },
      { key: 'P', width: 14 },
    ];

    sheet.getCell('A1').value = exportData.playlist.name;
    sheet.getCell('A1').font = { bold: true, size: 16 };
    sheet.getCell('A2').value = `Created by: ${exportData.playlist.owner}`;
    sheet.getCell('A3').value = `Followers: ${exportData.playlist.followers}`;
    sheet.getCell('A4').value = `Tracks exported: ${exportData.tracks.length}`;
    sheet.getCell('A5').value = `Total duration: ${formatDuration(exportData.total_duration_ms)}`;
    sheet.getCell('A6').value = `Playlist URL: ${exportData.playlist.url || 'N/A'}`;
    sheet.getCell('A7').value = `Description: ${exportData.playlist.description || 'N/A'}`;

    if (exportData.playlist.url) {
      sheet.getCell('A6').value = {
        text: `Playlist URL: ${exportData.playlist.url}`,
        hyperlink: exportData.playlist.url,
      };
    }

    await tryAddCoverImage(workbook, sheet, exportData.playlist.cover_image_url);

    sheet.getRow(11).values = headers;
    const headerRow = sheet.getRow(11);
    headerRow.font = { bold: true, color: { argb: 'FFFFFFFF' } };
    headerRow.fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: 'FF4F81BD' },
    };

    let rowNumber = 12;
    for (const track of exportData.tracks) {
      const rowValues = headers.map((header) => track[header] ?? '');
      sheet.getRow(rowNumber).values = rowValues;
      const urlValue = track['Spotify URL'];
      if (typeof urlValue === 'string' && urlValue.startsWith('http')) {
        sheet.getCell(`E${rowNumber}`).value = { text: urlValue, hyperlink: urlValue };
        sheet.getCell(`E${rowNumber}`).font = { color: { argb: 'FF0563C1' }, underline: true };
      }
      rowNumber += 1;
    }

    if (rowNumber > 12) {
      const lastColLetter = String.fromCharCode(64 + headers.length);
      const fullRef = `A11:${lastColLetter}${rowNumber - 1}`;
      // Excel table names allow letters/digits/underscore only — use CSPRNG hex, not Math.random (Sonar S2245).
      const uniqueSuffix = crypto.randomUUID().replace(/-/g, '').slice(0, 8);
      const tableName = `tbl_${sheetName.replace(/[^A-Za-z0-9_]/g, '').slice(0, 20)}_${uniqueSuffix}`;
      const tbl = sheet.addTable({
        name: tableName,
        ref: 'A11',
        headerRow: true,
        style: {
          theme: 'TableStyleMedium9',
          showRowStripes: true,
        },
        columns: headers.map((header) => ({ name: header })),
        rows: [],
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- ExcelJS Table type omits tableRef/autoFilterRef from its public declaration
      (tbl as any).table.tableRef = fullRef;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- ExcelJS Table type omits tableRef/autoFilterRef from its public declaration
      (tbl as any).table.autoFilterRef = fullRef;
    }

    for (let r = 1; r <= rowNumber; r += 1) {
      const row = sheet.getRow(r);
      row.alignment = { vertical: 'middle', horizontal: 'left', wrapText: r > 7 };
    }
  }

  const buffer = await workbook.xlsx.writeBuffer();
  return buffer as ArrayBuffer;
}

export async function generateCombinedExcelFileFromAssembly(
  assemblyState: ResumableExportAssemblyState,
  renderMode: XlsxRenderMode = 'auto',
): Promise<ArrayBuffer> {
  const totalWorksheets = Array.isArray(assemblyState.worksheets) ? assemblyState.worksheets.length : 0;
  const totalTrackRows = (assemblyState.worksheets || []).reduce(
    (sum, worksheet) => sum + (Array.isArray(worksheet.rows) ? worksheet.rows.length : 0),
    0,
  );

  // Rich ExcelJS rendering (tables + cover images) is CPU heavy on large jobs under
  // Workers CPU limits. Use it when safely sized; otherwise degrade to a lightweight
  // renderer that prioritizes successful combined download.
  const useRichRenderer = renderMode === 'rich'
    ? true
    : renderMode === 'lite'
      ? false
      : totalWorksheets <= 18 && totalTrackRows <= 2400;

  if (!useRichRenderer) {
    console.warn('[export] using lightweight XLSX assembly renderer due to job size', {
      worksheetCount: totalWorksheets,
      trackRows: totalTrackRows,
    });
    return generateCombinedExcelFileFromAssemblyLite(assemblyState);
  }

  // Reconstruct lightweight ExportData objects and reuse the full ExcelJS renderer
  // so assembled resumable exports keep table styles and embedded cover images.
  const exportDataList: ExportData[] = assemblyState.worksheets.map((worksheet) => {
    const tracks = worksheet.rows.map((row) => {
      const track: Partial<ExportTrack> = {};
      for (let i = 0; i < worksheet.headers.length; i += 1) {
        const key = worksheet.headers[i] as keyof ExportTrack;
        track[key] = row[i] ?? '';
      }
      return track as ExportTrack;
    });

    return {
      playlist: {
        id: '',
        name: worksheet.playlist_name,
        description: worksheet.playlist_description || '',
        total_tracks: tracks.length,
        owner: worksheet.playlist_owner,
        followers: worksheet.playlist_followers,
        url: worksheet.playlist_url || '',
        cover_image_url: worksheet.playlist_cover_image_url,
      },
      tracks,
      total_duration_ms: 0,
      generated_at: new Date().toISOString(),
    };
  });

  return generateCombinedExcelFile(exportDataList);
}

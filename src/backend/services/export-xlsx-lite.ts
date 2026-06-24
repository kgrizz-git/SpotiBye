import ExcelJS from 'exceljs';
import type { ExportData, ResumableExportAssemblyState, WorksheetAssemblyData } from './export-types';
import { formatDuration, getTrackHeaders, sanitizeSheetName, uniquifySheetName } from './export-format-helpers';

export function buildWorksheetAssembly(exportData: ExportData, usedSheetNames: Set<string>): WorksheetAssemblyData {
  const headers = getTrackHeaders();
  const baseName = sanitizeSheetName(`${exportData.playlist.name} - ${exportData.playlist.owner}`);
  return {
    sheet_name: uniquifySheetName(baseName, usedSheetNames),
    playlist_name: exportData.playlist.name,
    playlist_owner: exportData.playlist.owner,
    playlist_followers: exportData.playlist.followers,
    playlist_cover_image_url: exportData.playlist.cover_image_url,
    playlist_description: exportData.playlist.description || 'N/A',
    playlist_url: exportData.playlist.url || '',
    total_duration: formatDuration(exportData.total_duration_ms),
    headers,
    rows: exportData.tracks.map((track) => headers.map((header) => track[header] ?? '')),
  };
}

export async function generateCombinedExcelFileFromAssemblyLite(
  assemblyState: ResumableExportAssemblyState,
): Promise<ArrayBuffer> {
  const workbook = new ExcelJS.Workbook();

  const summarySheet = workbook.addWorksheet('Playlists');
  summarySheet.columns = [
    { key: 'A', width: 29 },
    { key: 'B', width: 24 },
    { key: 'C', width: 16 },
    { key: 'D', width: 19 },
  ];
  summarySheet.addRow(assemblyState.summary_headers);
  for (const row of assemblyState.summary_rows) {
    summarySheet.addRow(row);
  }

  for (const worksheet of assemblyState.worksheets) {
    const sheet = workbook.addWorksheet(worksheet.sheet_name);
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

    sheet.addRow([worksheet.playlist_name]);
    sheet.addRow([`Created by: ${worksheet.playlist_owner}`]);
    sheet.addRow([`Followers: ${worksheet.playlist_followers}`]);
    sheet.addRow([`Tracks exported: ${worksheet.rows.length}`]);
    sheet.addRow([`Total duration: ${worksheet.total_duration}`]);
    if (worksheet.playlist_url) {
      sheet.addRow([{
        text: `Playlist URL: ${worksheet.playlist_url}`,
        hyperlink: worksheet.playlist_url,
      }]);
    } else {
      sheet.addRow(['Playlist URL: N/A']);
    }
    sheet.addRow([`Description: ${worksheet.playlist_description || 'N/A'}`]);
    sheet.addRow([]);
    sheet.addRow([]);
    sheet.addRow([]);
    sheet.addRow(worksheet.headers);

    for (const row of worksheet.rows) {
      const excelRow = sheet.addRow(row);
      const spotifyUrl = row[4];
      if (typeof spotifyUrl === 'string' && spotifyUrl.startsWith('http')) {
        const cell = excelRow.getCell(5);
        cell.value = { text: spotifyUrl, hyperlink: spotifyUrl };
        cell.font = {
          color: { argb: 'FF0563C1' },
          underline: true,
        };
      }
    }

    if (worksheet.rows.length > 0) {
      sheet.autoFilter = {
        from: { row: 11, column: 1 },
        to: { row: 11 + worksheet.rows.length, column: worksheet.headers.length },
      };
    }
  }

  const buffer = await workbook.xlsx.writeBuffer();
  return buffer as ArrayBuffer;
}

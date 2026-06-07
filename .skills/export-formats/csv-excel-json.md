# Export Formats: CSV, Excel, JSON

## Export Service

The export service in `src/backend/services/export.ts` handles converting Spotify playlist data to different formats.

## CSV Format

**Structure:**
- Header row with column names
- One row per track
- Comma-separated values
- UTF-8 encoding

**Columns:**
- Track Name
- Artist Name
- Album Name
- Track Number
- Duration (ms)
- Added At
- Spotify URI

**Implementation:**
```typescript
function toCSV(tracks: Track[]): string {
  const header = "Track Name,Artist Name,Album Name,Track Number,Duration,Added At,Spotify URI\n"
  const rows = tracks.map(track =>
    `${track.name},${track.artist},${track.album},${track.track_number},${track.duration_ms},${track.added_at},${track.uri}`
  ).join('\n')
  return header + rows
}
```

## Excel Format

**Structure:**
- Similar to CSV but with proper Excel formatting
- Uses xlsx library for generation
- Includes worksheet with playlist name

**Implementation:**
```typescript
function toExcel(tracks: Track[], playlistName: string): Buffer {
  const workbook = new ExcelJS.Workbook()
  const worksheet = workbook.addWorksheet(playlistName)
  // Add header row
  // Add data rows
  return workbook.xlsx.writeBuffer()
}
```

## JSON Format

**Structure:**
- Nested JSON object
- Playlist metadata at top level
- Tracks array with full track objects

**Schema:**
```json
{
  "playlist_name": "My Playlist",
  "playlist_id": "spotify:playlist:id",
  "tracks": [
    {
      "name": "Track Name",
      "artist": "Artist Name",
      "album": "Album Name",
      "track_number": 1,
      "duration_ms": 180000,
      "added_at": "2024-01-01T00:00:00Z",
      "uri": "spotify:track:id"
    }
  ]
}
```

## Best Practices

- Handle special characters in CSV (quotes, commas)
- Use consistent date formatting (ISO 8601)
- Validate data before export
- Handle large playlists with streaming
- Provide progress updates for long exports

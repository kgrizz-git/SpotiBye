Debug test 2 with longer content
# Export Formats Implementation Guide

## Overview

This document outlines the implementation plan for adding CSV and JSON export options to SpotiBye, along with playlist cover image downloads and organized folder structure.

## Current Export Architecture

### Existing Implementation
- Uses _prepare_playlist_track_rows() to get structured track data
- Creates pandas DataFrame from track data
- Exports to Excel with formatting
- Handles file naming and directory creation
- Located in src/spotify_playlist_exporter_v2/screens/main_screen.py
- **Already includes Spotify URI export** in track data structure

### Key Functions
- _export_playlists_worker() - Main export logic
- _prepare_playlist_track_rows() - Data preparation
- _format_excel_file() - Excel formatting

### Currently Exported Fields
The existing implementation already exports the following track information:
- Track Name
- Artist
- Album
- Duration
- **Spotify URI** (spotify:track:xxxxxxxx)
- Spotify URL
- Audio features (Tempo, Key, Danceability, Energy, etc.)

## Implementation Difficulty: Low to Medium

### CSV Export (Easy)
- Simple pandas DataFrame method
- Minimal code changes required
- Maintains existing data structure

### JSON Export (Easy)
- Multiple JSON format options available
- Can include additional metadata
- Structured data format

### Cover Image Download (Medium)
- Requires HTTP requests
- Image file handling
- Error handling for missing images

## Detailed Export Format Analysis

### CSV Export Implementation

#### Difficulty: **Easy**
- **Complexity**: Low
- **Estimated Time**: 2-4 hours
- **Dependencies**: pandas (already available)

#### Implementation Steps:
1. **Modify _export_playlists_worker() function**
   - Add format parameter (csv, json, xlsx)
   - Create conditional export logic based on format

2. **Add CSV export method**
   ```python
   def _export_to_csv(self, df: pd.DataFrame, file_path: str):
       df.to_csv(file_path, index=False, encoding='utf-8')
   ```

3. **Update UI to include format selection**
   - Add radio buttons or dropdown for export format
   - Update file extension handling

#### CSV Export Columns (Including Spotify URI)
The CSV export will include all existing fields:
- Track Name
- Artist
- Album
- Duration
- **Spotify URI** (spotify:track:xxxxxxxx)
- Spotify URL
- Audio features (Tempo, Key, Danceability, Energy, etc.)

#### Advantages:
- Universal compatibility
- Small file size
- Easy to implement
- Fast export speed
- **Includes Spotify URIs for cross-platform use**

#### Limitations:
- No rich formatting
- Limited data types
- No multiple sheets

### JSON Export Implementation

#### Difficulty: **Easy to Medium**
- **Complexity**: Low to Medium
- **Estimated Time**: 4-6 hours
- **Dependencies**: json (built-in), optionally pandas

#### Implementation Steps:
1. **Create JSON data structure**
   ```python
   def _prepare_playlist_json_data(self, playlist_data: Dict) -> Dict:
       """Convert playlist data to JSON-serializable format with Excel/CSV consistency."""
       from datetime import datetime

       # Convert 'N/A' strings to None for JSON compatibility
       def convert_na_to_none(value):
           if value == 'N/A':
               return None
           return value

       # Process tracks to match Excel/CSV field structure
       processed_tracks = []
       for track in playlist_data.get('tracks', []):
           processed_track = {}
           for key, value in track.items():
               processed_track[key] = convert_na_to_none(value)
           processed_tracks.append(processed_track)

       return {
           "playlist_info": {
               "name": playlist_data.get('name', 'Unknown'),
               "description": playlist_data.get('description', ''),
               "total_tracks": len(processed_tracks),
               "export_date": datetime.now().isoformat()
           },
           "tracks": processed_tracks
       }
   ```

2. **Add JSON export method**
   ```python
   def _export_to_json(self, data: Dict, file_path: str):
       with open(file_path, 'w', encoding='utf-8') as f:
           json.dump(data, f, indent=2, ensure_ascii=False)
   ```

3. **Ensure consistency with Excel/CSV formats**
   - Use same `combined_rows` data structure as Excel/CSV
   - Maintain PascalCase field naming convention
   - Convert "N/A" strings to null for JSON compatibility
   - Use identical data types (numbers for features, strings for basic info)

#### JSON Export Structure (Including Spotify URI)
```json
{
  "playlist_info": {
    "name": "Playlist Name",
    "description": "Description",
    "total_tracks": 25,
    "export_date": "2023-12-16T00:00:00Z"
  },
  "tracks": [
    {
      "Artist": "Artist Name",
      "Album": "Album Name",
      "Track": "Track Title",
      "Duration": "MM:SS",
      "Spotify URL": "https://open.spotify.com/track/xxxxxxxx",
      "Spotify URI": "spotify:track:xxxxxxxx",
      "Tempo": 120.0,
      "Key": "C major",
      "Danceability": 0.8,
      "Energy": 0.7,
      "Valence": 0.6,
      "Acousticness": 0.2,
      "Instrumentalness": 0.1,
      "Liveness": 0.1,
      "Speechiness": 0.05,
      "Loudness": -5.2,
      "Time Signature": 4
    }
  ]
}
```

#### Advantages:
- Rich data structure
- Preserves all metadata
- Easy to parse programmatically
- Supports nested data
- **Includes Spotify URIs for API integration**

#### Limitations:
- Larger file sizes
- Not spreadsheet-friendly
- Requires JSON viewer for casual users

### XLSX Export

#### Status: **MOSTLY COMPLETED**
- **Complexity**: Medium (completed)
- **Implementation Time**: 6-8 hours (completed)
- **Dependencies**: pandas, openpyxl (already available)

#### Current Implementation Review:
- ✅ Enhanced Excel export with advanced formatting
- ✅ Comprehensive styling and column width adjustment
- ✅ Multi-sheet export with summary statistics
- ✅ Hyperlink support for track URLs
- ✅ Cover image insertion when available

#### Implemented Features:
1. **✅ Enhanced formatting**
   - Column width auto-adjustment
   - Header styling
   - Table styling

2. **✅ Multi-sheet support**
   - Separate playlists into different sheets
   - Summary sheet
   - Metadata display on each playlist sheet

3. **✅ Advanced features**
   - Hyperlinks for track URLs (clickable in Excel)
   - Cover image insertion (120x120 pixels) when available
   - Comprehensive error handling - NOT YET IMPLEMENTED
   - Progress indicators for large exports - ? Not sure if implemented

#### Remaining Tasks:
- [ ] Add data validation for specific columns
- [ ] Validate file size with large datasets
- [ ] Test compatibility across different Excel versions
- [ ] Confirm comprehensive error handling
- [ ] Confirm progress indicators for large exports

## Comparative Analysis

| Format | Implementation Difficulty | File Size | Compatibility | Features |
|--------|-------------------------|-----------|---------------|----------|
| CSV | Easy | Small | Universal | Basic data only |
| JSON | Easy-Medium | Medium | Good | Rich metadata |
| XLSX | Medium | Large | Good | Formatting, multi-sheet |

## Recommended Implementation Order

1. **CSV Export** (Quick win - 1 day)
2. **JSON Export** (Medium effort - 1-2 days)
3. **XLSX Enhancements** (Polish - 2-3 days)

## Code Structure Changes

### New Methods to Add:
```python
def _export_to_csv(self, df: pd.DataFrame, file_path: str) -> None
def _export_to_json(self, data: Dict, file_path: str) -> None
def _prepare_playlist_json_data(self, playlist_data: List[Dict]) -> Dict
def _get_file_extension(self, format_type: str) -> str
```

### Existing Methods to Modify:
```python
def _export_playlists_worker(self)  # Add format parameter
def _prepare_playlist_track_rows(self)  # Potentially enhance for JSON
```

## Testing Strategy

### Automated Tests (Can be fully automated)

#### Unit Tests:
- [ ] **CSV Export**: Test data integrity, encoding, special characters
- [ ] **JSON Export**: Validate schema correctness, data structure, nested objects
- [ ] **XLSX Export**: Test file creation, basic formatting, data types
- [ ] **File Naming**: Test extension handling, special characters in filenames
- [ ] **Error Handling**: Test exception scenarios, invalid inputs
- [ ] **Data Preparation**: Test `_prepare_playlist_track_rows()` with various data

#### Integration Tests:
- [ ] **Format Selection Logic**: Test conditional export paths
- [ ] **File Creation**: Verify files are created with correct paths and extensions
- [ ] **Data Flow**: Test end-to-end data transformation from API to file
- [ ] **Memory Management**: Test with large datasets (1000+ tracks)

#### Performance Tests:
- [ ] **Export Speed**: Benchmark export times for different playlist sizes
- [ ] **Memory Usage**: Monitor memory consumption during large exports
- [ ] **File Size Limits**: Test behavior with very large playlists

### Manual Tests (Require human verification)

#### User Interface Testing:
- [ ] **Format Selection UI**: Verify radio buttons/dropdown usability
- [ ] **File Dialog**: Test file picker interaction and default extensions
- [ ] **Progress Indicators**: Verify loading states and completion notifications
- [ ] **Error Messages**: Assess clarity and user-friendliness of error dialogs
- [ ] **Help Text**: Evaluate tooltips and format descriptions

#### File Compatibility Testing:
- [ ] **CSV Files**: Open in Excel, Google Sheets, LibreOffice Calc
- [ ] **JSON Files**: Validate parsing in different programming environments
- [ ] **XLSX Files**: Test in different Excel versions and alternatives
- [ ] **Special Characters**: Verify display of international characters across platforms

#### Cross-Platform Testing:
- [ ] **Windows**: Test file creation, permissions, Excel integration
- [ ] **macOS**: Test file creation, Numbers compatibility, special characters
- [ ] **Linux**: Test file creation, LibreOffice integration

#### User Experience Validation:
- [ ] **Export Workflow**: Complete user journey from selection to completion
- [ ] **Error Recovery**: User response to various error scenarios
- [ ] **File Organization**: Verify folder structure and naming conventions
- [ ] **Large Playlist Handling**: User experience with long export processes

## Error Handling Strategy

### Critical Error Scenarios

#### File System Errors
- **Insufficient Disk Space**: Check available space before export, warn user if insufficient
- **File Permission Issues**: Handle write permission errors gracefully
- **Invalid File Paths**: Validate file paths and handle illegal characters
- **File Already Exists**: Implement overwrite confirmation or auto-renaming
- **Network Drive Issues**: Handle timeouts and connectivity problems

#### Data Processing Errors
- **Missing Track Metadata**: Handle null/empty values gracefully
- **Invalid Data Types**: Type conversion errors for duration, popularity, etc.
- **Memory Limitations**: Handle out-of-memory errors for large playlists
- **Encoding Issues**: Handle special characters and international text
- **Malformed API Responses**: Validate data structure before processing

#### Export Format-Specific Errors
- **CSV Export**: Handle delimiter conflicts, quote escaping issues
- **JSON Export**: Handle circular references, non-serializable objects
- **XLSX Export**: Handle worksheet size limits, formatting errors

#### Network and API Errors
- **Spotify API Rate Limits**: Implement exponential backoff
- **Network Timeouts**: Handle connection failures gracefully
- **Authentication Failures**: Redirect to login flow
- **Missing Cover Images**: Handle 404s, timeouts, invalid URLs

### Error Handling Implementation

#### Try-Catch Structure
```python
def _export_playlists_worker(self, format_type: str):
    try:
        # Validate inputs
        self._validate_export_parameters(format_type)

        # Check disk space
        self._check_disk_space_requirements()

        # Process data
        playlist_data = self._prepare_playlist_track_rows()

        # Export based on format
        if format_type == 'csv':
            self._export_to_csv(playlist_data, file_path)
        elif format_type == 'json':
            self._export_to_json(playlist_data, file_path)
        elif format_type == 'xlsx':
            self._export_to_excel(playlist_data, file_path)

    except InsufficientDiskSpaceError as e:
        self._show_error_dialog("Insufficient disk space", str(e))
    except PermissionError as e:
        self._show_error_dialog("Permission denied", "Cannot write to selected location")
    except NetworkError as e:
        self._show_error_dialog("Network error", "Please check your connection")
    except ExportFormatError as e:
        self._show_error_dialog("Export failed", f"Format error: {str(e)}")
    except Exception as e:
        self._log_error(f"Unexpected export error: {str(e)}")
        self._show_error_dialog("Export failed", "An unexpected error occurred")
```

#### Validation Functions
```python
def _validate_export_parameters(self, format_type: str):
    if format_type not in ['csv', 'json', 'xlsx']:
        raise ValueError(f"Unsupported export format: {format_type}")

    if not self.selected_playlists:
        raise ValueError("No playlists selected for export")

def _check_disk_space_requirements(self, estimated_size: int):
    import shutil
    free_space = shutil.disk_usage(self.export_path).free
    if free_space < estimated_size * 2:  # 2x safety margin
        raise InsufficientDiskSpaceError(free_space, estimated_size)
```

#### User-Friendly Error Messages
- **Specific**: Clearly state what went wrong
- **Actionable**: Suggest what the user can do
- **Non-Technical**: Avoid technical jargon
- **Consistent**: Use same tone and format across all errors

### Error Recovery Strategies

#### Automatic Recovery
- **Retry Logic**: For network-related failures (max 3 retries)
- **Fallback Formats**: If primary format fails, suggest alternatives
- **Partial Export**: Save what was successfully processed

#### User-Guided Recovery
- **Alternative Locations**: Suggest different export paths
- **Format Selection**: Recommend different export formats
- **Data Cleanup**: Offer to clean problematic data

### Logging and Monitoring

#### Error Logging
```python
import logging

def _log_error(self, error_message: str, context: Dict = None):
    logging.error(f"Export Error: {error_message}", extra=context)
    # Send to error tracking service in production
```

#### Progress Tracking
- **Export Progress**: Show percentage complete
- **Current Operation**: Display "Processing track X/Y"
- **Time Estimates**: Show remaining time for large exports

## User Experience Considerations

### Format Selection UI:

#### Design Requirements:
- **Compact dropdown** (Spinner widget) for format selection
- **XLSX as default** format to maintain backward compatibility
- **Minimal space usage** in the export section
- **Integration** with existing filename input and export button

#### Implementation Details:

**UI Component Location:**
- Add format selector in `_create_export_section()` method
- Position between filename input and export button
- Use horizontal layout to maintain compact design

**Dropdown Specification:**
```python
# Add to _create_export_section() method
format_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
format_layout.add_widget(Label(text='Format:', size_hint_x=None, width=dp(60), font_size=dp(15)))

self.format_spinner = Spinner(
    text='XLSX',  # Default format
    values=['XLSX', 'CSV', 'JSON'],
    size_hint_x=None,
    width=dp(100),
    font_size=dp(14),
    background_color=[0.55, 0.55, 0.55, 1],
)
self.format_spinner.bind(text=self.on_format_change)
format_layout.add_widget(self.format_spinner)
```

**Format Change Handler:**
```python
def on_format_change(self, spinner, text):
    """Update filename extension when format changes."""
    current_filename = self.filename_input.text or ''
    if current_filename:
        # Remove existing extension and add new one
        base_name = os.path.splitext(current_filename)[0]
        extension = self._get_file_extension(text.lower())
        self.filename_input.text = f"{base_name}{extension}"

def _get_file_extension(self, format_type: str) -> str:
    """Get file extension for export format."""
    extensions = {
        'xlsx': '.xlsx',
        'csv': '.csv',
        'json': '.json'
    }
    return extensions.get(format_type, '.xlsx')
```

**Export Worker Integration:**
```python
def start_export(self, instance):
    """Modified to use selected format."""
    selected_format = self.format_spinner.text.lower()
    threading.Thread(
        target=self._export_playlists_worker,
        args=(selected_format,),
        daemon=True
    ).start()

def _export_playlists_worker(self, format_type: str):
    """Worker thread with format parameter."""
    # Conditional export logic based on format_type
    if format_type == 'csv':
        self._export_to_csv(df, file_path)
    elif format_type == 'json':
        json_data = self._prepare_playlist_json_data(playlist_data)
        self._export_to_json(json_data, file_path)
    else:  # xlsx (default)
        df.to_excel(file_path, index=False, engine='openpyxl')
        self._format_excel_file(file_path, playlist_name)
```

**Integration Points:**
- **Filename Generation**: Update `_generate_default_filename()` to use selected format
- **File Dialog**: Ensure file picker shows correct extension for selected format
- **Status Messages**: Update export status to show selected format
- **Error Handling**: Add format-specific error messages

#### UI Layout Impact:
- **Minimal space increase**: ~dp(40) height added to export section
- **No width expansion**: Uses existing horizontal layout
- **Maintains existing flow**: Fits naturally between filename and export button
- **Responsive design**: Works with existing responsive layout patterns

#### User Experience:
- **Default behavior**: XLSX format maintains current user experience
- **Easy discovery**: Dropdown clearly shows available formats
- **Immediate feedback**: Filename updates automatically when format changes
- **Consistent styling**: Matches existing UI components in export section

### File Naming:
- Consistent naming across formats
- Clear file extensions
- Avoid overwriting existing files

## Current Data Structure Documentation

### Export Row Structure
The current export system creates rows with the following columns:

**Basic Track Information:**
- `Artist` - Artist names (comma-separated for multiple artists)
- `Album` - Album name
- `Track` - Track title
- `Duration` - Formatted duration (MM:SS format)
- `Spotify URL` - External Spotify URL for the track
- `Spotify URI` - Spotify URI for the track

**Audio Features (from Reccobeats API):**
- `Tempo` - BPM (rounded to 2 decimal places)
- `Key` - Musical key with mode (e.g., "C major", "D# minor")
- `Danceability` - Danceability score (0-1, rounded to 3 decimal places)
- `Energy` - Energy score (0-1, rounded to 3 decimal places)
- `Valence` - Valence score (0-1, rounded to 3 decimal places)
- `Acousticness` - Acousticness score (0-1, rounded to 3 decimal places)
- `Instrumentalness` - Instrumentalness score (0-1, rounded to 3 decimal places)
- `Liveness` - Liveness score (0-1, rounded to 3 decimal places)
- `Speechiness` - Speechiness score (0-1, rounded to 3 decimal places)
- `Loudness` - Loudness in dB (rounded to 1 decimal place)
- `Time Signature` - Time signature (e.g., 4, 3, etc.)

**Internal Fields (removed before export):**
- `_duration_ms` - Raw duration in milliseconds
- `_spotify_id` - Internal Spotify track ID

### Data Processing Flow
1. Track data fetched from Spotify API
2. Basic track information normalized and formatted
3. Audio features fetched from Reccobeats API (if available)
4. Internal fields added for processing
5. Internal fields removed before final export
6. DataFrame created with final column structure

## Implementation Checklists

### CSV Export Checklist

#### Step 1: Preparation and Setup
**Review Current Implementation**
   - [x] Examine existing `_export_playlists_worker()` function structure
   - [x] Identify current DataFrame preparation logic in `_prepare_playlist_track_rows()`
   - [x] Confirm pandas dependency is available in requirements.txt
   - [x] Document current data columns and structure

**Design CSV Export Architecture**
   - [x] Define CSV column order and naming conventions
   - [x] Plan special character handling strategy
   - [x] Determine encoding requirements (UTF-8 recommended)
   - [x] Design file naming pattern for CSV exports

**CSV Column Order and Naming:**
1. Basic track info (most important first):
   - `Track` - Track title
   - `Artist` - Artist names
   - `Album` - Album name
   - `Duration` - Formatted duration

2. Spotify identifiers:
   - `Spotify URL` - External Spotify URL
   - `Spotify URI` - Spotify URI

3. Audio features (grouped logically):
   - `Tempo` - BPM
   - `Key` - Musical key with mode
   - `Energy` - Energy score
   - `Danceability` - Danceability score
   - `Valence` - Valence score
   - `Acousticness` - Acousticness score
   - `Instrumentalness` - Instrumentalness score
   - `Liveness` - Liveness score
   - `Speechiness` - Speechiness score
   - `Loudness` - Loudness in dB
   - `Time Signature` - Time signature

**Naming Conventions:**
- Use PascalCase for column names (consistent with current implementation)
- No spaces in column names (CSV best practice)
- Descriptive names that are clear to end users
- Maintain compatibility with existing Excel exports

**Special Character Handling Strategy:**
- **Unicode Support**: Use UTF-8 encoding to handle international characters
- **Commas in Data**: Let pandas handle CSV quoting automatically for fields containing commas
- **Newlines**: Allow pandas to handle newline characters within fields through proper quoting
- **Quotes**: Use standard CSV quoting for fields containing quote characters
- **Emojis/Special Symbols**: UTF-8 encoding will preserve emoji and special characters
- **Empty Fields**: Use empty strings for missing data (consistent with current N/A handling)
- **URL Safety**: Spotify URLs already properly formatted, no additional escaping needed

#### Step 2: Core Implementation
**Create CSV Export Method**
   ```python
   def _export_to_csv(self, df: pd.DataFrame, file_path: str) -> None:
       """Export DataFrame to CSV with proper encoding."""
       df.to_csv(file_path, index=False, encoding='utf-8')
   ```

**Modify Export Worker**
   - [x] Add `format_type` parameter to `_export_playlists_worker()`
   - [x] Implement conditional export logic:
     ```python
     if format_type == 'csv':
         self._export_to_csv(df, file_path)
     elif format_type == 'json':
         json_data = self._prepare_playlist_json_data(playlist_data)
         self._export_to_json(json_data, file_path)
     else:  # xlsx
         # Existing XLSX logic
     ```

**Add Helper Methods**
   - [x] Create `_get_file_extension(format_type: str) -> str` method
   - [x] Update `_generate_default_filename()` to use selected format
   - [x] Modify file naming logic to handle CSV extensions

#### Step 3: UI Integration
**Add Format Selection UI**
   - [x] Implement format dropdown in `_create_export_section()`
   - [x] Add format change handler to update filename extension
   - [x] Position format selector between filename and export button
   - [x] Style format selector to match existing UI components

**Update Export Workflow**
   - [x] Modify `start_export()` to pass selected format to worker
   - [x] Update status messages to show selected format
   - [x] Add format-specific error handling and user feedback

#### Step 4: Testing and Validation
**Unit Testing**
   - [ ] Create test file: `tests/test_csv_export.py`
   - [ ] Test CSV export with sample playlist data
   - [ ] Validate CSV file structure and column order
   - [ ] Test special character handling (Unicode, emojis, etc.)

**Integration Testing**
   - [ ] Test CSV export with various playlist sizes (1, 10, 100, 1000+ tracks)
   - [ ] Verify CSV opens correctly in Excel, Google Sheets, LibreOffice
   - [ ] Test filename generation with different formats
   - [ ] Validate data integrity between source and CSV output

**User Experience Testing**
   - [ ] Test format selection dropdown interaction
   - [ ] Verify filename updates when format changes
   - [ ] Test export workflow end-to-end with CSV format
   - [ ] Validate error messages for CSV-specific issues

### JSON Export Checklist

#### Step 1: Design and Architecture
**Define JSON Data Structure**
   - [x] Design JSON object structure matching Excel/CSV consistency:
     ```json
     {
       "playlist_info": {...},
       "tracks": [...]
     }
     ```
   - [x] Define playlist info object fields (name, description, total_tracks, export_date)
   - [x] Design track data object structure with identical field names as Excel/CSV
   - [x] Plan for all audio features with same naming convention as Excel/CSV

**Plan JSON Format Options**
   - [x] Use flat structure matching Excel/CSV columns (no nested audio_features)
   - [x] Use PascalCase field names consistent with Excel/CSV exports
   - [x] Plan datetime formatting (ISO 8601 for export_date)
   - [x] Handle missing data with null values instead of "N/A" strings
   - [x] Ensure data types match Excel/CSV (numbers for features, strings for basic info)

#### Step 2: Core Implementation
**Create JSON Data Preparation Method**
   - [x] Implement `_prepare_playlist_json_data()` method
   - [x] Add datetime import for export timestamps
   - [x] Use same `combined_rows` data structure as Excel/CSV for consistency
   - [x] Ensure proper JSON encoding (UTF-8)
   - [x] Convert "N/A" strings to null for JSON compatibility
   - [x] Maintain identical field names and data types as Excel/CSV

**Implement JSON Export Method**
   - [x] Create `_export_to_json()` method
   - [x] Add proper JSON formatting with indentation
   - [x] Handle special characters with ensure_ascii=False
   - [x] Add comprehensive error handling for JSON serialization
   - [x] Add file validation and JSON format verification

**Handle Data Transformation**
   - [x] Use same `combined_rows` data from `_prepare_playlist_track_rows()` as Excel/CSV
   - [x] Convert "N/A" strings to null for JSON compatibility
   - [x] Maintain PascalCase field naming consistency with Excel/CSV
   - [x] Ensure proper JSON encoding (UTF-8)
   - [x] Handle all data types consistently (numbers for features, strings for basic info)

#### Step 3: Integration with Export System
**Modify Export Worker**
   - [x] Add JSON export logic to `_export_playlists_worker()`
   - [x] Implement format-specific data preparation:
     ```python
     if format_type == 'json':
         json_data = self._prepare_playlist_json_data(playlist_data)
         self._export_to_json(json_data, file_path)
     ```
   - [x] Add comprehensive error handling for JSON export

**Update File Handling**
   - [x] Modify file naming logic for JSON extensions
   - [x] Update `_get_file_extension()` method
   - [x] Ensure JSON files are saved in correct directory structure

#### Step 4: Testing and Validation
**Unit Testing**
   - [ ] Create test file: `tests/test_json_export.py`
   - [ ] Test JSON schema validation with sample data
   - [ ] Verify JSON structure matches design specification
   - [ ] Test special character handling in JSON output

**Integration Testing**
   - [ ] Test JSON export with various playlist sizes
   - [ ] Validate JSON parsing in different programming environments
   - [ ] Test with playlists containing missing metadata
   - [ ] Verify JSON file size and performance with large datasets

**Data Integrity Testing**
   - [ ] Compare JSON output with source data for accuracy
   - [ ] Test nested object structure (audio features, metadata)
   - [ ] Validate datetime formatting consistency
   - [ ] Test Unicode and special character preservation

### XLSX Export Checklist

#### Step 1: Review Current Implementation (Status: Mostly Complete)
**Assess Existing Code**
   - [x] Review current Excel export implementation in `_export_playlists_worker()`
   - [x] Identify formatting limitations and enhancement opportunities
   - [x] Document current multi-sheet architecture
   - [x] Review summary sheet layout and data structure

**Validate Dependencies**
   - [x] Confirm pandas and openpyxl are available
   - [x] Check for any version compatibility issues
   - [x] Verify existing styling and formatting capabilities

#### Step 2: Complete Remaining Implementation
**Enhance Error Handling**
   - [x] Add comprehensive error handling to `_format_excel_file()`
   - [x] Implement fallback for failed formatting operations
   - [x] Add specific error messages for Excel-related issues
   - [x] Handle memory errors with large datasets
   - [x] Add file validation and integrity checks

**Add Missing Features**
   - [ ] Implement data validation for specific columns (duration, popularity)
   - [ ] Add progress indicators for large Excel exports
   - [ ] Create backup mechanism for interrupted exports
   - [ ] Optimize memory usage for very large playlists

#### Step 3: Advanced Features Completion
**Data Validation and Quality**
   - [ ] Add input validation for numeric columns
   - [ ] Implement range checking for duration fields
   - [ ] Add consistency checks for Spotify URIs/URLs
   - [ ] Create data quality reports in summary sheet

**Performance Optimization**
   - [ ] Optimize Excel file creation speed
   - [ ] Implement streaming for very large datasets
   - [ ] Add memory management for big playlists
   - [ ] Test with 1000+ track playlists

#### Step 4: Testing and Validation
**Compatibility Testing**
   - [ ] Test Excel files in different Excel versions (2016, 2019, 365)
   - [ ] Verify compatibility with LibreOffice Calc
   - [ ] Test on different operating systems (Windows, macOS, Linux)
   - [ ] Validate file size limits and performance

**Feature Validation**
   - [ ] Test hyperlink functionality in exported files
   - [ ] Verify multi-sheet navigation and structure
   - [ ] Test cover image insertion and display
   - [ ] Validate summary statistics accuracy

**Edge Case Testing**
   - [ ] Test with empty playlists
   - [ ] Test with playlists containing special characters
   - [ ] Test with very long track/artist names
   - [ ] Test with missing metadata fields

#### Step 5: Integration with Format Selection
**Update Export Worker**
   - [x] Modify `_export_playlists_worker()` to handle format selection
   - [x] Ensure XLSX remains the default format
   - [x] Add format-specific progress messages
   - [x] Update error handling for XLSX-specific issues
   - [x] Add comprehensive validation for Excel export

**File Management**
   - [x] Update filename generation for XLSX format
   - [x] Ensure proper file extension handling
   - [ ] Test file overwrite protection
   - [ ] Validate organized folder structure

### General Implementation Checklist

#### Step 1: Code Quality and Architecture
**Implement Comprehensive Error Handling**
   - [x] Add try-catch blocks around all export operations
   - [x] Create specific exception classes for different error types
   - [x] Implement user-friendly error messages with actionable guidance
   - [x] Add error logging with context information for debugging
   - [x] Add disk space validation and permission checking
   - [x] Implement parameter validation for export operations

**Ensure Code Consistency**
   - [ ] Apply consistent naming conventions across all export methods
   - [ ] Standardize method signatures and parameter naming
   - [ ] Add comprehensive docstrings for all new methods
   - [ ] Implement proper type hints throughout the codebase

**Add Logging and Monitoring**
   - [x] Implement structured logging for export operations
   - [ ] Add performance metrics tracking (export time, file size)
   - [x] Create debug logging for troubleshooting export issues
   - [x] Add export success/failure status tracking

#### Step 2: User Experience Enhancement
**Implement Progress Indicators**
   - [ ] Add progress bar updates for different export stages
   - [ ] Show current operation status ("Processing track X/Y")
   - [ ] Display estimated time remaining for large exports
   - [ ] Add export completion notifications with file location

**Improve User Interface**
   - [ ] Add loading indicators during export processing
   - [ ] Implement export cancellation functionality
   - [ ] Add format-specific tooltips and help text
   - [ ] Create export format comparison information

**Enhance Error Communication**
   - [ ] Design clear, non-technical error messages
   - [ ] Add suggested actions for common error scenarios
   - [ ] Implement error recovery options where possible
   - [ ] Add context-sensitive help links

#### Step 3: File Management and Organization
**Implement File Safety Features**
   - [ ] Add file overwrite protection with user confirmation
   - [ ] Create automatic file naming for conflicts (playlist_2.xlsx)
   - [ ] Implement file permission checks before export
   - [ ] Add disk space validation before starting export

**Organize Export Structure**
   - [ ] Create organized folder structure for different formats
   - [ ] Implement export location selection (user-defined paths)
   - [ ] Add timestamp-based organization options
   - [ ] Handle long file names gracefully with truncation

**File Format Validation**
   - [ ] Add file format validation after export
   - [ ] Implement file integrity checks
   - [ ] Create format-specific validation rules
   - [ ] Add file size monitoring and warnings

#### Step 4: Performance Optimization
**Optimize Export Speed**
   - [ ] Profile export performance for different playlist sizes
   - [ ] Implement streaming for very large datasets
   - [ ] Optimize memory usage for big playlists
   - [ ] Add parallel processing for multiple playlists

**Memory Management**
   - [ ] Implement memory-efficient data processing
   - [ ] Add garbage collection optimization for large exports
   - [ ] Create memory usage monitoring
   - [ ] Test with 1000+ track playlists for memory limits

**Resource Optimization**
   - [ ] Optimize CPU usage during export operations
   - [ ] Implement efficient file I/O operations
   - [ ] Add resource cleanup after export completion
   - [ ] Monitor system resource usage during export

### UI Implementation Checklist

#### Step 1: Format Selection Component Design
**Create Format Dropdown UI**
   - [x] Add Spinner widget to `_create_export_section()` method
   - [x] Configure dropdown with values: ['XLSX', 'CSV', 'JSON']
   - [x] Set default value to 'XLSX' for backward compatibility
   - [x] Style dropdown to match existing UI components

**Position Format Selector**
   - [x] Place format selector between filename input and export button
   - [x] Use horizontal layout for compact design
   - [x] Ensure proper spacing and alignment with existing elements
   - [ ] Test responsive behavior on different screen sizes - OPTIONAL/LATER

#### Step 2: Format Change Handling
**Implement Format Change Logic**
   - [x] Create `on_format_change()` method to handle dropdown selection
   - [x] Update filename extension when format changes
   - [x] Preserve base filename while changing extension
   - [x] Add validation for format selection

**Add Helper Methods**
   - [x] Implement `_get_file_extension()` method for format mapping
   - [ ] Create `_update_filename_extension()` helper method
   - [ ] Add format validation in `_validate_export_parameters()`
   - [ ] Create format-specific file naming logic

#### Step 3: Export Workflow Integration
**Modify Export Process**
   - [x] Update `start_export()` to pass selected format to worker thread
   - [x] Modify `_export_playlists_worker()` to accept format parameter
   - [x] Add format-specific progress messages
   - [ ] Update status labels to show selected format

**Enhance User Feedback**
   - [ ] Add format-specific loading indicators
   - [x] Update completion messages with format information
   - [ ] Create format-specific error messages
   - [ ] Add tooltips explaining each format's benefits - OPTIONAL/LATER

#### Step 4: UI Testing and Validation
**Component Testing**
   - [ ] Test dropdown functionality with all format options
   - [ ] Verify filename updates correctly when format changes
   - [ ] Test format selection with empty/default filenames
   - [ ] Validate UI responsiveness during format changes

**Integration Testing**
   - [ ] Test complete export workflow with each format
   - [ ] Verify UI state management during export process
   - [ ] Test format persistence across multiple exports
   - [ ] Validate error handling in UI components

**User Experience Testing**
   - [ ] Test format selection discoverability
   - [ ] Verify intuitive nature of format dropdown
   - [ ] Test accessibility features (keyboard navigation, screen readers)
   - [ ] Validate UI consistency with application design

#### Step 5: Advanced UI Features
**Format Information Display**
   - [ ] Add format comparison tooltips - OPTIONAL/LATER
   - [ ] Create format-specific help text - OPTIONAL/LATER
   - [ ] Implement format preview functionality (if feasible) - OPTIONAL/LATER
   - [ ] Add estimated file size indicators - OPTIONAL/LATER

**UI Polish and Refinement**
   - [ ] Add smooth transitions for format changes
   - [ ] Implement hover states for dropdown - OPTIONAL/LATER
   - [ ] Add visual feedback for format selection - OPTIONAL/LATER
   - [ ] Create format-specific icon indicators - OPTIONAL/LATER

### Integration Testing Checklist

#### End-to-End Testing
- [ ] Test complete export workflow for each format
- [ ] Verify file creation and naming
- [ ] Test export with multiple playlists selected
- [ ] Validate export with empty playlists

#### Cross-Platform Testing
- [ ] Test CSV export on Windows/Mac/Linux
- [ ] Verify JSON parsing in different environments
- [ ] Test Excel file compatibility
- [ ] Validate special character handling across platforms

#### Error Scenario Testing
- [ ] Test export with network connectivity issues
- [ ] Handle missing track metadata gracefully
- [ ] Test export cancellation scenarios
- [ ] Verify behavior with insufficient disk space

### Documentation Checklist

#### Technical Documentation
- [ ] Update API documentation for new methods
- [ ] Document JSON schema structure
- [ ] Add code comments for complex logic
- [ ] Create troubleshooting guide

#### User Documentation
- [ ] Update user guide with export format options
- [ ] Add FAQ for export-related questions
- [ ] Create tutorial for each export format
- [ ] Document file compatibility information

### Deployment Checklist

#### Release Preparation
- [ ] Version bump for new export features
- [ ] Update changelog with export improvements
- [ ] Test upgrade from previous version
- [ ] Verify backward compatibility

#### Quality Assurance
- [ ] Code review for all export changes
- [ ] Security audit for file handling
- [ ] Performance benchmarking
- [ ] Accessibility testing for UI components

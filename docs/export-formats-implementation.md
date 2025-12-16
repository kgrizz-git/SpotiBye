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

### Key Functions
- _export_playlists_worker() - Main export logic
- _prepare_playlist_track_rows() - Data preparation
- _format_excel_file() - Excel formatting

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

#### Advantages:
- Universal compatibility
- Small file size
- Easy to implement
- Fast export speed

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
   def _prepare_playlist_json_data(self, playlist_data: List[Dict]) -> Dict:
       return {
           "playlist_info": {
               "name": playlist_name,
               "description": description,
               "total_tracks": len(tracks),
               "export_date": datetime.now().isoformat()
           },
           "tracks": tracks
       }
   ```

2. **Add JSON export method**
   ```python
   def _export_to_json(self, data: Dict, file_path: str):
       with open(file_path, 'w', encoding='utf-8') as f:
           json.dump(data, f, indent=2, ensure_ascii=False)
   ```

3. **Handle different JSON formats**
   - Simple track list
   - Full metadata format
   - Spotify API response format

#### Advantages:
- Rich data structure
- Preserves all metadata
- Easy to parse programmatically
- Supports nested data

#### Limitations:
- Larger file sizes
- Not spreadsheet-friendly
- Requires JSON viewer for casual users

### XLSX Export Enhancement

#### Difficulty: **Medium** (for improvements)
- **Complexity**: Medium
- **Estimated Time**: 6-8 hours
- **Dependencies**: pandas, openpyxl (already available)

#### Current Implementation Review:
- Basic Excel export exists
- Limited formatting
- Single sheet export

#### Enhancement Steps:
1. **Improve formatting**
   - Add column width auto-adjustment
   - Apply number formatting for durations
   - Add header styling

2. **Multi-sheet support**
   - Separate playlists into different sheets
   - Add summary sheet with statistics

3. **Advanced features**
   - Add hyperlinks for track URLs
   - Include cover images (if downloaded)
   - Add data validation

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

### Unit Tests:
- Test each export format independently
- Verify data integrity
- Test error handling

### Integration Tests:
- Test format selection in UI
- Verify file creation and naming
- Test with various playlist sizes

## User Experience Considerations

### Format Selection UI:
- Radio buttons or dropdown menu
- Show format-specific options
- Display estimated file sizes

### File Naming:
- Consistent naming across formats
- Clear file extensions
- Avoid overwriting existing files

## Implementation Checklists

### CSV Export Checklist

#### Pre-Implementation
- [ ] Review current `_export_playlists_worker()` function structure
- [ ] Identify existing DataFrame preparation logic
- [ ] Confirm pandas dependency is available
- [ ] Design UI components for format selection

#### Implementation
- [ ] Add format parameter to `_export_playlists_worker()`
- [ ] Create `_export_to_csv()` method
- [ ] Implement conditional export logic based on format
- [ ] Add `_get_file_extension()` helper method
- [ ] Update file naming logic to handle CSV extension

#### UI Updates
- [ ] Add format selection radio buttons/dropdown
- [ ] Update file dialog to show correct extension
- [ ] Add format-specific help text
- [ ] Test format selection interaction

#### Testing
- [ ] Create unit test for CSV export
- [ ] Test with various playlist sizes
- [ ] Verify CSV file opens correctly in Excel/Google Sheets
- [ ] Test special characters in CSV output
- [ ] Validate data integrity

### JSON Export Checklist

#### Pre-Implementation
- [ ] Design JSON data structure schema
- [ ] Decide on JSON format options (simple vs detailed)
- [ ] Plan metadata inclusion strategy
- [ ] Review existing track data structure

#### Implementation
- [ ] Create `_prepare_playlist_json_data()` method
- [ ] Implement `_export_to_json()` method
- [ ] Add datetime import for export timestamps
- [ ] Handle nested data structures properly
- [ ] Ensure proper JSON encoding (UTF-8)

#### Data Structure Design
- [ ] Define playlist info object structure
- [ ] Design track data object structure
- [ ] Plan for optional metadata fields
- [ ] Handle missing data gracefully

#### Testing
- [ ] Create unit test for JSON export
- [ ] Validate JSON schema correctness
- [ ] Test JSON parsing in different languages
- [ ] Verify special character handling
- [ ] Test with large playlists

### XLSX Enhancement Checklist

#### Pre-Implementation
- [ ] Review current Excel export implementation
- [ ] Identify formatting limitations
- [ ] Plan multi-sheet architecture
- [ ] Design summary sheet layout

#### Implementation
- [ ] Enhance `_format_excel_file()` method
- [ ] Add column width auto-adjustment
- [ ] Implement number formatting for durations
- [ ] Add header styling with bold/centering
- [ ] Create multi-sheet export logic

#### Advanced Features
- [ ] Add hyperlink support for track URLs
- [ ] Implement cover image insertion (if images downloaded)
- [ ] Add data validation for specific columns
- [ ] Create summary statistics sheet

#### Testing
- [ ] Test enhanced formatting in Excel
- [ ] Verify multi-sheet functionality
- [ ] Test hyperlink functionality
- [ ] Validate file size with enhancements
- [ ] Test compatibility with different Excel versions

### General Implementation Checklist

#### Code Quality
- [ ] Add proper error handling for all formats
- [ ] Implement progress indicators for large exports
- [ ] Add logging for debugging export issues
- [ ] Ensure consistent code style across methods

#### User Experience
- [ ] Add loading indicators during export
- [ ] Show export completion notifications
- [ ] Provide clear error messages
- [ ] Add export format tooltips/help text

#### File Management
- [ ] Implement file overwrite protection
- [ ] Add export location selection
- [ ] Create organized folder structure
- [ ] Handle long file names gracefully

#### Performance
- [ ] Optimize export speed for large playlists
- [ ] Add memory management for big datasets
- [ ] Implement streaming for very large exports
- [ ] Test performance with 1000+ track playlists

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

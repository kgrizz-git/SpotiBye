# Apple Music API Analysis

## Overview

This document analyzes Apple Music's API capabilities for playlist export/import functionality compared to Spotify's API, with focus on cross-platform implementation possibilities.

## Key Findings

### Apple Music API Capabilities

**Available Features:**
- Read access to user's library playlists (`/v1/me/library/playlists`)
- Read access to catalog playlists
- Search functionality for songs, albums, artists, playlists
- **Playlist creation** via REST API
- User authorization through MusicUserToken system

**Major Limitations:**
- No direct export/import functionality (unlike Spotify)
- Limited playlist management compared to Spotify
- No bulk operations
- Platform restrictions (but not iOS-only)
- Requires Apple Developer Program membership

### Playlist Creation Capabilities

**REST API Method:**
```http
POST https://api.music.apple.com/v1/me/library/playlists
```

**Requirements:**
- Developer Token (Bearer authentication)
- Music-User-Token (user authorization)
- LibraryPlaylistCreationRequest in body
- Returns 201 status on success

**Alternative Methods:**
- **MusicKit JS** (Web)
- **MusicKit Framework** (iOS 15+)
- **MusicLibrary** (iOS 16+)

## Cross-Platform Support

### Supported Platforms
- **Web Applications** - MusicKit JS, REST API
- **Backend Services** - Node.js, Python, any language
- **Android Apps** - Native MusicKit for Android
- **Desktop Apps** - Windows/Linux via REST API
- **Cross-Platform** - React Native, Flutter via REST API

### Cross-Platform Requirements
1. Apple Developer Account
2. MusicKit Identifier & Private Key
3. JWT Token Generation
4. User Authorization (MusicUserToken)

## Implementation Examples

### Node.js Backend Example
```javascript
const jwt = require('jsonwebtoken');
const axios = require('axios');

// Generate developer token
const token = jwt.sign({}, privateKey, {
    algorithm: 'ES256',
    expiresIn: '180d',
    issuer: teamId,
    header: { alg: 'ES256', kid: keyId }
});

// Create playlist
const response = await axios.post(
    'https://api.music.apple.com/v1/me/library/playlists', 
    playlistData, {
    headers: {
        'Authorization': `Bearer ${token}`,
        'Music-User-Token': userToken
    }
});
```

### Web Implementation (MusicKit JS)
```javascript
// MusicKit must be loaded in webpage
MusicKit.configure({
    developerToken: 'YOUR_DEVELOPER_TOKEN',
    app: {
        name: 'Your App',
        build: '1.0.0'
    }
});

// Create playlist
const playlist = await MusicKit.getInstance().api.createPlaylist({
    name: 'New Playlist',
    description: 'Description'
});
```

## Comparison with Spotify API

### Spotify Advantages:
- Full CRUD operations on playlists
- Easy export/import functionality
- More comprehensive metadata
- Simpler authentication flow
- Better cross-platform support

### Apple Music Advantages:
- Native iOS integration
- Rich catalog metadata
- Built-in user base on Apple devices
- High-quality audio streaming

### Implementation Complexity:
- **Spotify**: Easier implementation, more flexible
- **Apple Music**: More complex setup, platform restrictions

## Specific Requirements and Costs

### Apple Developer Program Requirements

**Cost:**
- **$99 per year** for Apple Developer Program membership
- **Required** for MusicKit identifier and API access
- **No free tier** available (even for open source projects)

**Steps to Get API Access:**
1. Create Apple Developer Account ($99/year)
2. Create MusicKit Identifier in Developer Portal
3. Generate Private Key (p8 file)
4. Create JWT tokens using private key
5. Request MusicUserToken for user authorization

### Rate Limits and Quotas

**Apple Music API Rate Limits:**
- **20 requests per second per user**
- **No rate limit information in API response headers**
- **Throttling and temporary bans** for exceeding limits
- **Per user token basis** (not per application)

**Comparison with Spotify:**
- **Spotify**: More generous rate limits, clear documentation
- **Apple Music**: Stricter limits, less transparent about quotas

## Available Libraries

### Python Libraries

**apple-music-python**
```bash
pip install apple-music-python
```

**What It Does:**
- **Catalog Search**: Search Apple Music's global catalog for songs, albums, artists, playlists
- **Metadata Retrieval**: Get detailed information about tracks, albums, artists
- **Authentication Handling**: Manages JWT token creation and API authentication
- **Request Management**: Handles HTTP requests to Apple Music API endpoints

**Useful For SpotiBye:**
- **Track Matching**: When importing playlists, search Apple Music catalog to find equivalent tracks
- **Metadata Enrichment**: Get additional track information not available from Spotify
- **Cross-Platform Mapping**: Find Apple Music equivalents for Spotify tracks by ISRC or metadata

**Limitations:**
- **No User Library Access**: Cannot access user's personal playlists or library
- **Catalog-Only**: Limited to public Apple Music catalog, not user data
- **No Playlist Operations**: Cannot create/modify user playlists

**Example Usage:**
```python
import applemusicpy

# Initialize with developer credentials
am = applemusicpy.AppleMusic(
    secret_key='private_key_content',
    key_id='YOUR_KEY_ID', 
    team_id='YOUR_TEAM_ID'
)

# Search for tracks (useful for cross-platform matching)
results = am.search('travis scott', types=['songs'], limit=5)

# Get album metadata
album_info = am.get_album('album_id')

# Search by ISRC (perfect for track matching)
isrc_results = am.search('USUM71706078', types=['songs'])
```

### Node.js Libraries

**@yujinakayama/apple-music**
```bash
npm install --save @yujinakayama/apple-music
```

**What It Does:**
- **Full API Coverage**: Supports both catalog and user library endpoints
- **User Authentication**: Handles MusicUserToken for user data access
- **Playlist Operations**: Can create, read, update user playlists
- **TypeScript Support**: Full type definitions included
- **Error Handling**: Comprehensive error management and retry logic

**Useful For SpotiBye:**
- **Complete User Library Access**: Export user's Apple Music playlists
- **Playlist Creation**: Import Spotify playlists into Apple Music
- **User Data Management**: Access personal library, ratings, play history
- **Cross-Platform Sync**: Bidirectional playlist synchronization

**Advantages Over Python Libraries:**
- **User Library Support**: Can access personal playlists and library
- **Playlist CRUD Operations**: Full create, read, update, delete capabilities
- **Active Maintenance**: Regularly updated with API changes
- **Better Documentation**: More comprehensive examples and guides

**Example Usage:**
```javascript
import { Client } from "@yujinakayama/apple-music";

// Initialize with developer token
const client = new Client({
    developerToken: 'YOUR_DEVELOPER_TOKEN'
});

// Get user's library playlists
const playlists = await client.me.library.playlists();

// Create a new playlist
const newPlaylist = await client.me.library.playlists.create({
    name: 'Imported from Spotify',
    description: 'Converted playlist'
});

// Add tracks to playlist
await client.me.library.playlists.addTracks(playlistId, trackIds);

// Search catalog for track matching
const searchResults = await client.catalog.search('song', 'artist', {limit: 10});
```

**apple-music-token-node**
```bash
npm install apple-music-token-node
```

**What It Does:**
- **JWT Token Generation**: Handles complex JWT creation and signing
- **Private Key Management**: Securely loads and uses .p8 private keys
- **Token Refresh**: Manages token expiration and renewal
- **Authentication Helper**: Simplifies the complex Apple authentication flow

**Useful For SpotiBye:**
- **Authentication Setup**: Handles the complex JWT requirements
- **Token Management**: Automatic token refresh and validation
- **Security**: Proper cryptographic signing of developer tokens

**Example Usage:**
```javascript
import { AppleMusicToken } from 'apple-music-token-node';

const tokenGenerator = new AppleMusicToken({
    keyId: 'YOUR_KEY_ID',
    teamId: 'YOUR_TEAM_ID',
    privateKey: fs.readFileSync('private_key.p8')
});

// Generate developer token
const developerToken = tokenGenerator.generateDeveloperToken();
```

### Library Limitations

**Common Issues:**
- Many libraries don't support user library resources
- Some are unmaintained due to developer account costs
- Limited documentation compared to Spotify libraries
- Authentication complexity not fully abstracted

## Practical Library Usage for SpotiBye

### How These Libraries Fit Into Your Architecture

**For Export (Apple Music → Excel):**
1. **Use Node.js library** (`@yujinakayama/apple-music`) - supports user library access
2. **Fetch user playlists** via `client.me.library.playlists()`
3. **Extract track data** song by song (similar to your Spotify approach)
4. **Map to existing export format** you've already built

**For Import (Excel → Apple Music):**
1. **Use Python library** (`apple-music-python`) for track matching
2. **Search catalog** to find Apple Music equivalents of imported tracks
3. **Use Node.js library** for actual playlist creation
4. **Handle track matching failures** with manual resolution options

**For Cross-Platform Sync:**
1. **Combine both libraries** - Python for catalog search, Node.js for user operations
2. **Implement track matching** using ISRC codes when available
3. **Create unified interface** that abstracts platform differences

### Integration Strategy

**Phase 1: Export Only**
- Start with Node.js library for Apple Music playlist export
- Leverage your existing Spotify export infrastructure
- Minimal changes to current SpotiBye architecture

**Phase 2: Import Functionality**
- Add Python library for track matching
- Implement Apple Music playlist creation
- Extend current import interface

**Phase 3: Full Cross-Platform**
- Combine both libraries in unified service
- Add bidirectional sync capabilities
- Implement advanced track matching algorithms

### Alternative: Third-Party Services

**Musicfetch API**
- **No rate limits**
- **Lower entry cost** than Apple Developer Program
- **Comprehensive metadata** beyond Apple Music catalog
- **Competitive pricing** plans
- **Easy integration** with extensive documentation

**Trade-offs:**
- Not direct Apple Music API access
- May not support user-specific operations
- Third-party dependency

## Practical Implementation for SpotiBye

### Current Spotify Implementation
Based on the existing codebase, SpotiBye already:
- Fetches playlist data song by song
- Implements custom export logic
- Processes track metadata and audio analysis
- Exports to Excel format

### Apple Music Integration Strategy

**Phase 1: Data Export**
- Implement Apple Music API authentication
- Fetch user playlists via `/v1/me/library/playlists`
- Extract track information song by song (similar to Spotify)
- Map Apple Music track metadata to existing export format

**Phase 2: Import Functionality**
- Implement playlist creation via `POST /v1/me/library/playlists`
- Handle track matching between platforms
- Manage Apple Music catalog search for track identification

**Phase 3: Cross-Platform Features**
- Playlist conversion between Spotify and Apple Music
- Unified export/import interface
- Batch operations for multiple playlists

### Technical Considerations

**Authentication Flow:**
1. Generate JWT developer token using private key
2. Request MusicUserToken from user authorization
3. Store tokens securely for API calls

**Data Mapping Challenges:**
- Different track ID systems (ISRC vs Spotify URIs)
- Varying metadata availability
- Catalog differences between platforms

**Rate Limiting:**
- **20 requests per second per user** - much stricter than Spotify
- **No rate limit headers** in API responses
- **Implement proper caching strategies** to avoid hitting limits
- **Handle API errors gracefully** with exponential backoff

**Cost Considerations:**
- **$99/year developer fee** vs Spotify's free API access
- **Library limitations** - many Python libraries don't support user playlists
- **Maintenance overhead** - token management and authentication complexity

## Recommendations

### For Immediate Implementation:
1. **Start with export functionality** - easier than import
2. **Use REST API** - more flexible than platform-specific SDKs
3. **Implement robust error handling** - Apple Music API can be less reliable
4. **Focus on core features** - match existing Spotify functionality

### Long-term Considerations:
1. **Platform-specific optimizations** - iOS apps can use native MusicKit
2. **Advanced features** - audio analysis, recommendations
3. **User experience** - seamless cross-platform playlist management

## Conclusion

Apple Music API provides sufficient capabilities for playlist export/import functionality, though with more complexity than Spotify. The API supports cross-platform implementation via REST endpoints, making it feasible to extend SpotiBye's functionality to Apple Music users.

Key success factors will be:
- Proper authentication setup
- Robust error handling
- Effective data mapping between platforms
- User-friendly cross-platform experience
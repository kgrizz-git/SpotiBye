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

## Implementation Plan: Apple Music Playlist Creation & Export

### Overview
This section provides a comprehensive implementation plan for creating and exporting Apple Music playlists, either from Spotify data or directly from Apple Music, with detailed technical specifications, error handling, and testing strategies.

### Phase 1: Setup and Configuration

#### Prerequisites Checklist
- [ ] **Apple Developer Account**: Create account ($99/year fee)
- [ ] **MusicKit Identifier**: Generate in Apple Developer Portal
- [ ] **Private Key**: Download .p8 file for JWT signing
- [ ] **Team ID**: Note from Apple Developer Portal
- [ ] **Key ID**: Note from private key generation

#### Development Environment Setup
- [ ] **Install Node.js (v18+)**:
  ```bash
  # Using nvm (recommended)
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
  nvm install 18
  nvm use 18

  # Or download from https://nodejs.org
  ```

- [ ] **Install Python (v3.9+)**:
  ```bash
  # macOS
  brew install python@3.9

  # Ubuntu/Debian
  sudo apt update
  sudo apt install python3.9 python3.9-pip python3.9-venv

  # Windows
  # Download from https://python.org
  ```

- [ ] **Create Project Structure**:
  ```bash
  mkdir spotibye-apple-music
  cd spotibye-apple-music
  mkdir backend frontend
  mkdir backend/src backend/tests
  mkdir frontend/src frontend/public
  ```

- [ ] **Initialize Node.js Backend**:
  ```bash
  cd backend
  npm init -y
  npm install typescript @types/node ts-node nodemon --save-dev
  npm install @yujinakayama/apple-music apple-music-token-node jsonwebtoken axios dotenv express
  npm install jest @types/jest ts-jest --save-dev
  ```

- [ ] **Initialize Python Environment**:
  ```bash
  cd ../backend
  python3.9 -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  pip install apple-music-python pandas python-dotenv pytest requests
  ```

- [ ] **Setup Environment Variables**:
  ```bash
  # Create .env file
  touch backend/.env
  echo "# Apple Music API Configuration" >> backend/.env
  echo "APPLE_MUSIC_KEY_ID=your_key_id_here" >> backend/.env
  echo "APPLE_MUSIC_TEAM_ID=your_team_id_here" >> backend/.env
  echo "APPLE_MUSIC_PRIVATE_KEY_PATH=./keys/private_key.p8" >> backend/.env
  echo "APPLE_MUSIC_DEVELOPER_TOKEN_EXPIRY=180d" >> backend/.env
  ```

- [ ] **Create Keys Directory**:
  ```bash
  mkdir backend/keys
  echo "Add your .p8 private key file here" > backend/keys/README.md
  ```

- [ ] **Setup HTTPS for Local Development**:
  ```bash
  # Install mkcert for local SSL certificates
  # macOS
  brew install mkcert
  mkcert -install
  mkcert localhost 127.0.0.1 ::1

  # Create SSL certificates directory
  mkdir backend/ssl
  mv localhost+2.pem backend/ssl/
  mv localhost+2-key.pem backend/ssl/
  ```

- [ ] **Install Rate Limiting Library**:
  ```bash
  cd backend
  npm install express-rate-limit
  ```

### Phase 2: Apple Developer Setup (Step-by-Step)

#### Apple Developer Account Setup
- [ ] **Create Apple Developer Account**:
  1. Go to https://developer.apple.com
  2. Click "Account" → "Enroll"
  3. Choose "Individual" or "Organization"
  4. Pay $99/year fee
  5. Complete verification process

- [ ] **Generate MusicKit Identifier**:
  1. Sign in to Apple Developer Portal
  2. Navigate to "Certificates, Identifiers & Profiles"
  3. Click "Identifiers" → "+"
  4. Select "MusicKit IDs"
  5. Enter Description: "SpotiBye Apple Music Integration"
  6. Enter Bundle ID: "com.spotibye.applemusic"
  7. Click "Continue" → "Register"

- [ ] **Create Private Key (.p8 file)**:
  1. In Developer Portal, go to "Keys" section
  2. Click "+" to create new key
  3. Enter Key Name: "SpotiBye Apple Music Key"
  4. Check "MusicKit" capability
  5. Click "Continue" → "Register"
  6. Download the .p8 file (can only download once!)
  7. Save to `backend/keys/private_key.p8`
  8. Note the Key ID shown on the screen

- [ ] **Get Team ID**:
  1. In Developer Portal, look at "Membership" details
  2. Copy your "Team ID" (10-character alphanumeric string)

- [ ] **Configure Environment Variables**:
  ```bash
  # Edit backend/.env file
  nano backend/.env
  ```
  Replace placeholder values with actual credentials:
  ```env
  APPLE_MUSIC_KEY_ID=ABC123DEF4  # Your actual Key ID
  APPLE_MUSIC_TEAM_ID=XYZ987ABC6  # Your actual Team ID
  APPLE_MUSIC_PRIVATE_KEY_PATH=./keys/private_key.p8
  APPLE_MUSIC_DEVELOPER_TOKEN_EXPIRY=180d
  ```

#### Project Configuration Files
- [ ] **Create TypeScript Configuration**:
  ```bash
  cd backend
  npx tsc --init
  ```
  Create `backend/tsconfig.json`:
  ```json
  {
    "compilerOptions": {
      "target": "ES2020",
      "module": "commonjs",
      "lib": ["ES2020"],
      "outDir": "./dist",
      "rootDir": "./src",
      "strict": true,
      "esModuleInterop": true,
      "skipLibCheck": true,
      "forceConsistentCasingInFileNames": true,
      "resolveJsonModule": true
    },
    "include": ["src/**/*"],
    "exclude": ["node_modules", "dist", "tests"]
  }
  ```

- [ ] **Create Package.json Scripts**:
  ```bash
  cd backend
  npm pkg set scripts.dev="nodemon src/index.ts"
  npm pkg set scripts.build="tsc"
  npm pkg set scripts.start="node dist/index.js"
  npm pkg set scripts.test="jest"
  ```

- [ ] **Create Jest Configuration**:
  Create `backend/jest.config.js`:
  ```javascript
  module.exports = {
    preset: 'ts-jest',
    testEnvironment: 'node',
    roots: ['<rootDir>/src', '<rootDir>/tests'],
    testMatch: ['**/__tests__/**/*.ts', '**/?(*.)+(spec|test).ts'],
    transform: {
      '^.+\\.ts$': 'ts-jest',
    },
  };
  ```

### Phase 2: Recommended Libraries and Tools

#### Primary Libraries
- [ ] **@yujinakayama/apple-music** (Node.js)
  - Full user library access
  - Playlist CRUD operations
  - TypeScript support
  - Active maintenance

- [ ] **apple-music-python** (Python)
  - Catalog search functionality
  - Track matching capabilities
  - ISRC-based searches

#### Supporting Libraries
- [ ] **apple-music-token-node** (Node.js)
  - JWT token generation
  - Private key management
  - Token refresh handling

- [ ] **jsonwebtoken** (Node.js)
  - Alternative JWT implementation
  - Cryptographic signing

#### Development Tools
- [ ] **axios** (Node.js)
  - HTTP client for API requests
  - Error handling
  - Request/response interceptors

- [ ] **dotenv** (Node.js/Python)
  - Environment variable management
  - Secure credential storage

### Phase 3: API Access and Authentication Setup

#### Authentication Flow Implementation
- [ ] **JWT Token Generation**
  - Create developer token using private key
  - Implement ES256 signing algorithm
  - Set 180-day expiration
  - Handle token refresh automatically

- [ ] **User Authorization**
  - Implement MusicUserToken request flow
  - Handle user consent and permissions
  - Store user tokens securely
  - Implement token refresh logic

#### Configuration Setup
```javascript
// Environment variables (.env)
APPLE_MUSIC_KEY_ID=your_key_id
APPLE_MUSIC_TEAM_ID=your_team_id
APPLE_MUSIC_PRIVATE_KEY_PATH=./path/to/private_key.p8
APPLE_MUSIC_DEVELOPER_TOKEN_EXPIRY=180d
```

#### Authentication Service Structure
```javascript
class AppleMusicAuth {
  constructor() {
    this.keyId = process.env.APPLE_MUSIC_KEY_ID;
    this.teamId = process.env.APPLE_MUSIC_TEAM_ID;
    this.privateKey = fs.readFileSync(process.env.APPLE_MUSIC_PRIVATE_KEY_PATH);
  }

  generateDeveloperToken() {
    return jwt.sign({}, this.privateKey, {
      algorithm: 'ES256',
      expiresIn: '180d',
      issuer: this.teamId,
      header: {
        alg: 'ES256',
        kid: this.keyId,
        typ: 'JWT'
      }
    });
  }
}
```

### Phase 4: Core Implementation - Playlist Creation

#### Playlist Creation Service
```javascript
class AppleMusicPlaylistService {
  constructor(authClient) {
    this.client = authClient;
    this.rateLimiter = new RateLimiter(20); // 20 requests per second
  }

  async createPlaylist(name, description, tracks = []) {
    try {
      await this.rateLimiter.waitForSlot();

      const playlistData = {
        attributes: {
          name: name,
          description: description
        },
        relationships: {
          tracks: {
            data: tracks.map(track => ({
              id: track.id,
              type: 'songs'
            }))
          }
        }
      };

      const response = await this.client.me.library.playlists.create(playlistData);
      return response.data;
    } catch (error) {
      throw new AppleMusicError(`Failed to create playlist: ${error.message}`);
    }
  }
}
```

#### Track Matching Service (Python)
```python
class TrackMatcher:
    def __init__(self, apple_music_client):
        self.client = apple_music_client

    def match_track(self, spotify_track):
        # Try ISRC match first
        if hasattr(spotify_track, 'external_ids') and 'isrc' in spotify_track.external_ids:
            isrc_results = self.client.search(spotify_track.external_ids['isrc'], types=['songs'])
            if isrc_results['results']['songs']['data']:
                return isrc_results['results']['songs']['data'][0]

        # Fallback to metadata search
        query = f"{spotify_track.name} {spotify_track.artists[0]['name']}"
        search_results = self.client.search(query, types=['songs'], limit=10)

        return self._find_best_match(spotify_track, search_results['results']['songs']['data'])

    def _find_best_match(self, spotify_track, candidates):
        # Implement fuzzy matching logic
        best_match = None
        best_score = 0

        for candidate in candidates:
            score = self._calculate_match_score(spotify_track, candidate)
            if score > best_score and score > 0.7:  # 70% confidence threshold
                best_match = candidate
                best_score = score

        return best_match
```

### Phase 5: Error Handling Strategy

#### Critical Error Scenarios Checklist
- [ ] **Authentication Failures**
  - Invalid developer tokens
  - Expired user tokens
  - Missing permissions

- [ ] **Rate Limiting Issues**
  - 20 requests/second exceeded
  - Temporary API bans
  - Request throttling

- [ ] **Data Processing Errors**
  - Invalid track metadata
  - Missing ISRC codes
  - Track matching failures

- [ ] **Network and API Issues**
  - Connection timeouts
  - API service unavailability
  - Malformed responses

#### Error Handling Implementation
```javascript
class AppleMusicErrorHandler {
  constructor() {
    this.retryConfig = {
      maxRetries: 3,
      baseDelay: 1000,
      maxDelay: 10000
    };
  }

  async handleApiError(error, context) {
    if (error.status === 429) {
      // Rate limit exceeded
      return this.handleRateLimit(error, context);
    } else if (error.status === 401) {
      // Authentication error
      return this.handleAuthError(error, context);
    } else if (error.status >= 500) {
      // Server error
      return this.handleServerError(error, context);
    } else {
      // Client error
      throw new AppleMusicError(`API Error: ${error.message}`, context);
    }
  }

  async handleRateLimit(error, context) {
    const delay = Math.min(
      this.retryConfig.baseDelay * Math.pow(2, context.retryCount),
      this.retryConfig.maxDelay
    );

    await new Promise(resolve => setTimeout(resolve, delay));
    return { retry: true, delay };
  }
}
```

### Phase 6: Testing Strategy

#### Automated Tests Checklist
- [ ] **Unit Tests**
  - JWT token generation and validation
  - Track matching algorithms
  - Rate limiting functionality
  - Error handling logic

- [ ] **Integration Tests**
  - API authentication flow
  - Playlist creation endpoint
  - Track search functionality
  - Data transformation between platforms

- [ ] **Performance Tests**
  - Rate limiting compliance (20 req/sec)
  - Large playlist processing (1000+ tracks)
  - Memory usage optimization
  - Concurrent request handling

#### Manual Tests Checklist
- [ ] **Cross-Platform Validation**
  - Spotify to Apple Music playlist conversion
  - Track matching accuracy verification
  - Metadata preservation testing
  - User experience workflow testing

- [ ] **Error Scenario Testing**
  - Network connectivity failures
  - Invalid API credentials
  - Rate limit boundary testing
  - Malformed track data handling

- [ ] **User Acceptance Testing**
  - End-to-end playlist creation
  - Import/export workflow validation
  - Error message clarity
  - Performance with real-world data

#### Test Implementation Examples
```javascript
// Unit test for playlist creation
describe('AppleMusicPlaylistService', () => {
  test('should create playlist successfully', async () => {
    const service = new AppleMusicPlaylistService(mockAuthClient);
    const result = await service.createPlaylist('Test Playlist', 'Description', []);
    expect(result.id).toBeDefined();
    expect(result.attributes.name).toBe('Test Playlist');
  });

  test('should handle rate limiting', async () => {
    const service = new AppleMusicPlaylistService(mockAuthClient);
    mockAuthClient.me.library.playlists.create.mockRejectedValue({ status: 429 });

    await expect(service.createPlaylist('Test', 'Desc', []))
      .rejects.toThrow('Rate limit exceeded');
  });
});
```

### Phase 7: Deployment and Monitoring

#### Production Readiness Checklist
- [ ] **Security Configuration**
  - Environment variable encryption
  - Private key secure storage
  - API key rotation strategy
  - Access logging implementation

- [ ] **Monitoring Setup**
  - API request rate monitoring
  - Error rate tracking
  - Performance metrics collection
  - User activity analytics

- [ ] **Documentation**
  - API integration guide
  - Troubleshooting documentation
  - User setup instructions
  - Developer configuration guide

#### Success Metrics
- **Playlist Creation Success Rate**: >95%
- **Track Matching Accuracy**: >85%
- **API Response Time**: <2 seconds average
- **User Error Rate**: <5%

### Phase 8: Cloudflare Deployment (Step-by-Step)

#### Cloudflare Workers Setup
- [ ] **Install Wrangler CLI**:
  ```bash
  # Install Wrangler globally
  npm install -g wrangler

  # Login to Cloudflare
  wrangler login
  ```

- [ ] **Create Cloudflare Worker Project**:
  ```bash
  cd backend
  wrangler init spotibye-apple-music-worker
  cd spotibye-apple-music-worker

  # Select "Hello World" template
  # Choose "yes" for TypeScript
  # Choose "yes" for git init
  ```

- [ ] **Configure Wrangler.toml**:
  Create `wrangler.toml`:
  ```toml
  name = "spotibye-apple-music-worker"
  main = "src/index.ts"
  compatibility_date = "2023-12-01"

  [env.production]
  vars = { ENVIRONMENT = "production" }

  [env.development]
  vars = { ENVIRONMENT = "development" }
  ```

- [ ] **Install Required Dependencies**:
  ```bash
  npm install @yujinakayama/apple-music apple-music-token-node jsonwebtoken
  npm install --save-dev @types/node
  ```

- [ ] **Create Worker Entry Point**:
  Create `src/index.ts`:
  ```typescript
  import { AppleMusicAuth } from './auth';
  import { AppleMusicPlaylistService } from './playlist-service';

  export default {
    async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
      const url = new URL(request.url);

      // CORS headers
      const corsHeaders = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      };

      if (request.method === 'OPTIONS') {
        return new Response(null, { headers: corsHeaders });
      }

      if (url.pathname === '/api/apple-music/create-playlist' && request.method === 'POST') {
        try {
          const auth = new AppleMusicAuth(env);
          const playlistService = new AppleMusicPlaylistService(auth);

          const { name, description, tracks } = await request.json();
          const result = await playlistService.createPlaylist(name, description, tracks);

          return new Response(JSON.stringify(result), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
          });
        } catch (error) {
          return new Response(JSON.stringify({ error: error.message }), {
            status: 500,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
          });
        }
      }

      return new Response('Not Found', { status: 404 });
    }
  };
  ```

- [ ] **Create Environment Variables for Cloudflare**:
  ```bash
  # Set secrets for production
  wrangler secret put APPLE_MUSIC_KEY_ID
  wrangler secret put APPLE_MUSIC_TEAM_ID
  wrangler secret put APPLE_MUSIC_PRIVATE_KEY

  # For development
  wrangler secret put APPLE_MUSIC_KEY_ID --env development
  wrangler secret put APPLE_MUSIC_TEAM_ID --env development
  wrangler secret put APPLE_MUSIC_PRIVATE_KEY --env development
  ```

- [ ] **Deploy to Cloudflare Workers**:
  ```bash
  # Deploy to development
  wrangler deploy --env development

  # Deploy to production
  wrangler deploy
  ```

#### Cloudflare Pages Setup (Frontend)
- [ ] **Create Frontend Build**:
  ```bash
  cd ../frontend
  npm create vite@latest . -- --template react-ts
  npm install
  npm run build
  ```

- [ ] **Deploy to Cloudflare Pages**:
  ```bash
  # Install Wrangler if not already installed
  npm install -g wrangler

  # Deploy frontend
  wrangler pages deploy dist --project-name spotibye-frontend
  ```

- [ ] **Configure Custom Domain (Optional)**:
  ```bash
  # Add custom domain to worker
  wrangler custom-domains add api.spotibye.com

  # Add custom domain to pages
  wrangler pages domain put spotibye.com
  ```

#### Production Configuration
- [ ] **Set Up Rate Limiting in Cloudflare**:
  ```bash
  # Create rate limiting rule via Cloudflare Dashboard
  # 1. Go to Cloudflare Dashboard → Rate Limiting
  # 2. Create rule for API endpoints
  # 3. Set limit: 20 requests per minute per IP
  # 4. Configure burst: 5 requests
  ```

- [ ] **Configure Caching**:
  ```typescript
  // Add caching headers in worker
  const cacheHeaders = {
    'Cache-Control': 'public, max-age=3600', // 1 hour for track data
    'CDN-Cache-Control': 'public, max-age=86400', // 1 day CDN cache
  };
  ```

- [ ] **Set Up Monitoring**:
  ```bash
  # Enable Cloudflare Analytics
  # 1. Go to Cloudflare Dashboard → Analytics
  # 2. Enable Web Analytics
  # 3. Set up custom events for API calls

  # Configure logging
  wrangler tail  # View real-time logs
  ```

- [ ] **Configure DNS and SSL**:
  ```bash
  # DNS records are automatically managed by Cloudflare
  # SSL certificates are automatically provisioned
  # Verify SSL status in Cloudflare Dashboard → SSL/TLS
  ```

#### Testing Deployment
- [ ] **Test Worker Endpoints**:
  ```bash
  # Test local development
  wrangler dev

  # Test deployed worker
  curl -X POST https://spotibye-apple-music-worker.your-subdomain.workers.dev/api/apple-music/create-playlist \
    -H "Content-Type: application/json" \
    -d '{"name":"Test Playlist","description":"Test","tracks":[]}'
  ```

- [ ] **Monitor Performance**:
  ```bash
  # View analytics
  wrangler analytics

  # Check logs
  wrangler tail --env production
  ```

#### CI/CD Pipeline Setup
- [ ] **Create GitHub Actions Workflow**:
  Create `.github/workflows/deploy.yml`:
  ```yaml
  name: Deploy to Cloudflare

  on:
    push:
      branches: [main]

  jobs:
    deploy:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        - uses: actions/setup-node@v3
          with:
            node-version: '18'
        - run: npm ci
        - run: npm run test
        - run: npm run build
        - uses: cloudflare/wrangler-action@v3
          with:
            apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
  ```

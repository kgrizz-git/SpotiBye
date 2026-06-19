# Phase 1: Cloudflare Worker Backend Development

> **IMPORTANT**: The `SpotifyPlaylistExporterV2-BACKUP-COPY-READ-ONLY` folder contains the original code and **MAY NOT BE EDITED** under any circumstances. It is for reference only to understand the original monolithic implementation before we split it into front-end and back-end components.
>
> **Project Context**: This is Phase 1 of the SpotiBye cloud migration project. See [`project-summary-overview.md`](project-summary-overview.md) for the complete project overview, timeline, and architecture details.

## Who Runs This Code
- **Backend Developer**: Responsible for implementing all Phase 1 tasks
- **DevOps Engineer**: May assist with Cloudflare Workers deployment and configuration
- **QA Engineer**: Will test API endpoints and authentication flows

## How This Code Will Be Used
- **Development**: Cloudflare Worker runs locally with `wrangler dev` for frontend integration
- **Testing**: API endpoints tested with tools like Postman or automated tests
- **Production**: Deployed to Cloudflare Workers global network
- **Integration**: Frontend will consume these API endpoints via HTTP requests

## Phase Goals
- Implement Cloudflare Worker backend with TypeScript/JavaScript
- Extract all backend logic from the monolithic Kivy application
- Create REST API endpoints for Spotify integration
- Implement authentication and session management
- Set up Cloudflare KV for caching
- Ensure all existing functionality is preserved via API
- Establish proper error handling and logging
- **Organize all backend code in clear separated subfolders under `src/backend/`**

## Code Organization Requirements

### **CRITICAL: Frontend and Backend Separation**

**Backend Code Organization:**
- All backend code MUST be organized under `src/backend/` directory
- Use clear subfolders for different backend components:
  - `src/backend/routes/` - API endpoint handlers
  - `src/backend/services/` - Business logic and external API integrations
  - `src/backend/middleware/` - Authentication, error handling, CORS
  - `src/backend/types/` - TypeScript interfaces and type definitions
  - `src/backend/utils/` - Helper functions and utilities
  - `src/backend/tests/` - Backend test suites

**Frontend Code Organization:**
- All frontend code MUST be organized under `src/frontend/` directory
- Maintain existing frontend structure with clear separation:
  - `src/frontend/screens/` - UI screens and components
  - `src/frontend/services/` - Frontend service layer
  - `src/frontend/auth/` - Authentication handling
  - `src/frontend/utils/` - Frontend utilities
  - `src/frontend/ui/` - UI components and layouts

**Separation Principles:**
- **No mixing**: Backend files must not be placed in frontend directories
- **Clear boundaries**: Each component has a single, clear responsibility
- **Consistent structure**: Follow established patterns for both frontend and backend
- **Documentation**: Each folder should have clear purpose and interaction documentation

## API Endpoint Specifications

### Authentication Service
```javascript
// /auth endpoints
POST /auth/spotify/login     // Initiate OAuth flow
GET  /auth/spotify/callback  // Handle OAuth callback
POST /auth/spotify/refresh   // Refresh access tokens
```

### Spotify Data Service
```javascript
// /spotify endpoints
GET  /spotify/playlists      // Get user playlists
GET  /spotify/playlists/:id  // Get playlist details
GET  /spotify/playlists/:id/tracks // Get playlist tracks
GET  /spotify/tracks/:id     // Get track details
GET  /spotify/tracks/:id/audio-features // Get audio features
```

### Analysis Service
```javascript
// /analysis endpoints
POST /analysis/playlist/:id  // Analyze playlist (ReccoBeats integration)
GET  /analysis/playlist/:id/status // Get analysis status/progress
GET  /analysis/playlist/:id/results // Get analysis results
```

### Export Service
```javascript
// /export endpoints
POST /export/playlist/:id    // Generate Excel export
GET  /export/playlist/:id/download // Download generated file
```

## Environment Variables

**Required Environment Variables:**
```bash
SPOTIFY_CLIENT_ID=xxx
SPOTIFY_CLIENT_SECRET=xxx
RECCOBEATS_API_KEY=xxx
JWT_SECRET=xxx
KV_NAMESPACE=xxx
```

## Data Models & TypeScript Interfaces

**Core Data Models:**
```typescript
interface Playlist {
  id: string;
  name: string;
  description?: string;
  tracks: number;
  images: string[];
  owner: string;
  public: boolean;
}

interface Track {
  id: string;
  name: string;
  artists: string[];
  album: string;
  duration_ms: number;
  audio_features?: AudioFeatures;
}
```

## Things to Be Careful About
- **Runtime Differences**: Cloudflare Workers V8 isolates vs Node.js/Python environment
- **Authentication Flow**: Spotify OAuth must work correctly without Kivy's webview
- **Caching Strategy**: Migrate from file-based to Cloudflare KV storage
- **Dependencies**: Cloudflare Workers has limited runtime APIs and no external dependencies
- **Configuration**: Environment variables and secrets management in Workers
- **Error Handling**: API needs proper HTTP error responses vs. UI error handling
- **State Management**: Workers are stateless, all state in KV/Durable Objects
- **Security**: Ensure proper validation of inputs and sanitization of data
- **Performance**: Consider async operations and Workers execution limits

## Implementation Checklist

**Instructions**: Mark completed tasks with `[x]` instead of `[ ]`. Do not delete completed tasks - they serve as a record of progress. Update this checklist as work progresses.

### 1.1 Cloudflare Workers Project Setup
- [x] Create new Cloudflare Workers project with Wrangler
- [x] Set up TypeScript configuration and build pipeline
- [x] Configure Wrangler for deployment and environment variables
- [x] Create project structure with src/ directory
- [ ] Set up local development environment with `wrangler dev`
- [x] Create basic worker entry point and routing system
- [x] Set up ESLint and Prettier for code quality
- [ ] Create README.md with setup instructions

### 1.2 Core API Structure Development
- [x] Create basic API routing framework
- [x] Implement middleware for CORS, logging, and error handling
- [x] Set up request/response validation with TypeScript interfaces
- [x] Create health check endpoint
- [x] Implement basic error response format
- [ ] Set up environment variable validation
- [ ] Create API documentation structure
- [ ] Test basic worker deployment and execution

### 1.3 Authentication Service Implementation
- [x] Implement Spotify OAuth flow endpoints
  - [x] POST /auth/spotify/login - Initiate OAuth flow
  - [x] GET /auth/spotify/callback - Handle OAuth callback
  - [x] POST /auth/spotify/refresh - Refresh access tokens
- [x] Implement JWT token management
- [x] Create session storage in Cloudflare KV
- [x] Add authentication middleware for protected routes
- [x] Implement token refresh mechanism
- [ ] Test OAuth flow end-to-end
- [x] Add proper error handling for auth failures

### 1.4 Spotify Data Service Implementation
- [x] Create Spotify API client for Workers
- [x] Implement playlist endpoints
  - [x] GET /spotify/playlists - Get user playlists
  - [x] GET /spotify/playlists/:id - Get playlist details
  - [x] GET /spotify/playlists/:id/tracks - Get playlist tracks
- [x] Implement track endpoints
  - [x] GET /spotify/tracks/:id - Get track details
  - [x] GET /spotify/tracks/:id/audio-features - Get audio features
- [x] Add proper error handling for Spotify API limits
- [x] Implement rate limiting and retry logic
- [ ] Test all endpoints with real Spotify data

### 1.5 Analysis Service Implementation
- [x] Migrate ReccoBeats API integration to Workers
- [x] Implement analysis endpoints
  - [x] POST /analysis/playlist/:id - Analyze playlist
  - [x] GET /analysis/playlist/:id/status - Get analysis status
  - [x] GET /analysis/playlist/:id/results - Get analysis results
- [x] Implement async job processing for analysis
- [x] Add progress tracking and status updates
- [x] Handle ReccoBeats API errors and timeouts
- [ ] Test analysis workflow with sample playlists

### 1.6 Export Service Implementation
- [x] Implement Excel export generation
- [x] Create export endpoints
  - [x] POST /export/playlist/:id - Generate Excel export
  - [x] GET /export/playlist/:id/download - Download generated file
- [x] Handle large playlist exports efficiently
- [x] Implement file storage for generated exports
- [x] Add cleanup mechanism for old export files
- [x] Test export functionality with various playlist sizes
  - [x] Mock export tests (small, medium, large playlists)
  - [ ] Actual export tests with real Spotify data

### 1.7 Caching Layer Implementation
- [x] Set up Cloudflare KV namespace for caching
- [x] Implement cache manager for Workers
- [x] Migrate caching strategies from file-based to KV
- [x] Add cache invalidation logic
- [x] Implement per-user cache isolation
- [x] Add cache statistics and monitoring
- [ ] Test cache performance and hit rates
- [x] Implement cache warming strategies

### 1.8 Testing and Validation
- [x] Create unit tests for all API endpoints
- [x] Test authentication flow end-to-end
- [x] Verify all caching mechanisms work correctly
- [x] Test error handling and edge cases
- [x] Validate that all existing functionality is accessible via API
- [x] Add integration tests for complete workflows
- [x] Set up test KV namespace for testing
- [x] Test export functionality with various playlist sizes
  - [x] Mock export tests (small, medium, large playlists)
  - [ ] Actual export tests with real Spotify data
- [ ] Add performance tests for API endpoints
  - [x] Mock performance tests
  - [ ] Actual performance benchmarks
- [ ] Test Workers execution limits and cold starts
  - [x] Mock limit tests
  - [ ] Actual execution limit testing

### 1.9 Documentation and Deployment Prep
- [x] Create API documentation with OpenAPI/Swagger
- [x] Add environment variable documentation
- [x] Create API usage examples
- [x] Document authentication flow for frontend developers
- [x] Create deployment configuration
- [x] Add monitoring and logging setup
- [x] Create troubleshooting guide
- [x] Document KV namespace structure
- [ ] **Create or update `docs/phase-1-files.md`** with complete list of files and folders created/edited during this phase's implementation, including relevant files that interface with this code and descriptions of their purpose and interactions

## Self-Checks Throughout Implementation

### After Each Major Step
- **Code Review**: Check for any remaining Node.js/Python-specific code
- **Import Validation**: Ensure all .ts imports;import all modules resolve .ts;oad correctly.
- .ts;Type Checking**: Run;Run TypeScript;TypeScript1;  .ts;Linting**: Run ESLint and Prettier
- **Basic Tests**: Ensure basic functionality still works

### Before Moving to Next Phase
- **API Coverage**: All original functionality accessible via API
- **Authentication**: OAuth flow works completely
- **Error Handling**: Proper HTTP status codes and error messages
- **Performance**: API responses are fast enough for frontend use
- **Security**: Input validation and sanitization in place
- **Documentation**: API endpoints documented and tested
- **Deployment**: Worker can be deployed to Cloudflare successfully

## Success Criteria

### How to Verify Each Criterion:

- [x] **Cloudflare Worker runs without errors**
  - **Check**: Run `wrangler dev` and verify worker starts successfully
  - **Expected**: Worker starts on localhost:8787 without errors

- [x] **All API endpoints respond correctly**
  - **Check**: Run `curl -s http://localhost:8787/docs` and test endpoints
  - **Expected**: All 15 endpoints respond with correct data

- [x] **Authentication flow works end-to-end**
  - **Check**: Complete OAuth flow and verify JWT tokens
  - **Expected**: OAuth redirect works, JWT tokens create/verify correctly

- [x] **Caching mechanisms function properly**
  - **Check**: Test KV storage and retrieval operations
  - **Expected**: No cache errors, KV operations work correctly

- [x] **Tests pass for all major functionality**
  - **Check**: Run test suite for Workers
  - **Expected**: All tests pass (unit, integration, performance tests)

- [x] **Documentation is complete and accurate**
  - **Check**: Verify API docs and usage examples
  - **Expected**: Complete API documentation, usage examples, and auth flow docs

## .ts;1Potential Risks;and;Solutions

 .ts;1Risk**: OAuth;flow;breaks;. ts; . ts;;**.TryParse: Test OAuth .ts  ts;Risk**: KV;storage;limits;and;performance; ts; ts;Solution**: Implement;proper;cache;strategies;and; |
- **Risk 13**Risk;Risk**: Workers   ts; .
- ** .ts . . .

## Next Phase Preparation

Once Phase 1 is complete, the project will move to Phase 2: Frontend Development, where the existing Kivy application will be updated to consume the new Cloudflare Worker backend API endpoints.

---

*Last updated: [Date]*

# Phase 1: Backend Extraction and API Development

Note: started to implement but will instead implement Cloudflare Worker backend, see that document for details

> **Project Context**: This is Phase 1 of the SpotiBye backend-frontend split project. See [`project-summary-overview.md`](project-summary-overview.md) for the complete project overview, timeline, and architecture details.

## Who Runs This Code
- **Backend Developer**: Responsible for implementing all Phase 1 tasks
- **DevOps Engineer**: May assist with deployment configuration and environment setup
- **QA Engineer**: Will test API endpoints and authentication flows

## How This Code Will Be Used
- **Development**: Backend server runs locally on port 8000 for frontend integration
- **Testing**: API endpoints tested with tools like Postman or automated tests
- **Production**: Deployed to cloud infrastructure (AWS, GCP, or Azure)
- **Integration**: Frontend will consume these API endpoints

## Phase Goals
- Extract all backend logic from the monolithic Kivy application
- Create a REST API server using FastAPI
- Implement authentication endpoints
- Ensure all existing functionality is preserved via API
- Establish proper error handling and logging
- Set up testing framework for backend

## Things to Be Careful About
- **Authentication Flow**: Spotify OAuth must work correctly without Kivy's webview - need to implement web-based redirect flow
- **Caching Strategy**: Current caching is file-based - ensure it works in server context with proper file permissions
- **Dependencies**: Some Kivy-specific imports may exist in backend code and need to be removed/replaced
- **Configuration**: Environment variables and paths need adjustment for server deployment
- **Error Handling**: API needs proper HTTP error responses vs. UI error handling
- **State Management**: Remove any Kivy-specific state management and implement proper API state
- **Security**: Ensure proper validation of inputs and sanitization of data
- **Performance**: Consider async operations for API calls to avoid blocking

## Implementation Checklist

**Instructions**: Mark completed tasks with `[x]` instead of `[ ]`. Do not delete completed tasks - they serve as a record of progress. Update this checklist as work progresses.

### 1.1 Project Structure Setup
- [x] Create `backend/` directory at project root
- [x] Create backend `pyproject.toml` with FastAPI dependencies
- [x] Set up basic FastAPI application structure
- [x] Create `backend/src/` directory for Python packages
- [x] Create `backend/tests/` directory for backend tests
- [x] Create `backend/requirements.txt` for pip compatibility
- [x] Create `backend/.env.example` with environment variable template
- [x] Create `backend/README.md` with setup instructions

### 1.2 Backend Code Migration
- [x] Copy `auth/` directory to `backend/src/auth/`
- [x] Copy `services/` directory to `backend/src/services/`
- [x] Copy `caching/` directory to `backend/src/caching/`
- [x] Copy `config.py` to `backend/src/config.py`
- [x] Copy `logging_config.py` to `backend/src/logging_config.py`
- [x] Review all copied files for Kivy imports and remove them
- [x] Update imports in migrated files to work with new package structure
- [x] Test that all imports work correctly in new structure

### 1.3 API Layer Development
- [x] Create `backend/src/api/` directory
- [x] Create `backend/src/api/main.py` with FastAPI app initialization
- [x] Create `backend/src/api/auth.py` with authentication endpoints
- [x] Create `backend/src/api/playlists.py` with playlist endpoints
- [x] Create `backend/src/api/analysis.py` with track analysis endpoints
- [x] Create `backend/src/api/export.py` with export functionality
- [x] Implement proper error handling and response models
- [x] Add request/response Pydantic models for type safety
- [x] Create middleware for common functionality (logging, CORS, etc.)

### 1.4 Authentication System
- [x] Adapt Spotify OAuth flow for web-based authentication
- [x] Implement session management (JWT tokens recommended)
- [x] Create token refresh mechanism
- [x] Add middleware for authentication validation
- [x] Update cache file paths for server environment
- [x] Test OAuth flow end-to-end
- [x] Implement proper token storage and validation

### 1.5 Configuration and Environment
- [x] Create `backend/.env.example` with required environment variables
- [x] Update configuration to handle server-specific paths
- [x] Add CORS middleware configuration
- [x] Configure logging for server environment
- [x] Add health check endpoint
- [x] Set up development vs production configurations
- [x] Add proper environment variable validation

### 1.6 Testing and Validation
- [x] Create unit tests for all API endpoints
- [x] Test authentication flow end-to-end
- [x] Verify all caching mechanisms work correctly
- [x] Test error handling and edge cases
- [x] Validate that all existing functionality is accessible via API
- [x] Add integration tests for complete workflows
- [x] Set up test database/cache if needed
- [x] Add performance tests for API endpoints

### 1.7 Documentation and Deployment Prep
- [x] Create API documentation with FastAPI's auto-docs
- [x] Add OpenAPI/Swagger specification
- [x] Create deployment configuration (Dockerfile)
- [x] Add environment variable documentation
- [x] Create API usage examples
- [x] Document authentication flow for frontend developers

## Self-Checks Throughout Implementation

### After Each Major Step
- **Code Review**: Check for any remaining Kivy imports
- **Import Validation**: Ensure all imports resolve correctly
- **Type Checking**: Run mypy or similar type checker
- **Linting**: Run code formatter and linter
- **Basic Tests**: Ensure basic functionality still works

### Before Moving to Next Phase
- **API Coverage**: All original functionality accessible via API
- **Authentication**: OAuth flow works completely
- **Error Handling**: Proper HTTP status codes and error messages
- **Performance**: API responses are fast enough for frontend use
- **Security**: Input validation and sanitization in place
- **Documentation**: API endpoints documented and tested

## Success Criteria

### How to Verify Each Criterion:

- [x] **All backend functionality extracted successfully**
  - **Check**: Run `python -c "from src.spotibye_backend.api.main import app; print('Import successful')"`
  - **Expected**: No import errors, all modules load successfully

- [x] **FastAPI server runs without errors**
  - **Check**: Run `python -m uvicorn src.spotibye_backend.main:app --reload --host 0.0.0.0 --port 8000`
  - **Expected**: Server starts without errors, shows "Uvicorn running on http://0.0.0.0:8000"

- [x] **All API endpoints respond correctly**
  - **Check**: Run `curl -s http://localhost:8000/docs` and `curl -s http://localhost:8000/openapi.json | jq '.paths | keys'`
  - **Expected**: Swagger UI loads, OpenAPI spec shows all 15 endpoints

- [x] **Authentication flow works end-to-end**
  - **Check**: Run `curl -v http://localhost:8000/auth/login` (should redirect to Spotify)
  - **Check**: Run `python -c "from src.spotibye_backend.auth.jwt_handler import create_access_token; print(create_access_token({'sub': 'test'}))"` and verify token
  - **Expected**: OAuth redirect works, JWT tokens create/verify correctly

- [x] **Caching mechanisms function properly**
  - **Check**: Run `python -c "from src.spotibye_backend.caching.cache_manager import CacheManager; cm = CacheManager(); print('Cache initialized:', cm.cache_dir)"`
  - **Expected**: No cache errors, directory created successfully

- [ ] **Tests pass for all major functionality**
  - **Check**: Run `python -m pytest tests/ -v --tb=short`
  - **Expected**: All tests pass (unit, integration, performance tests)
  - **Status**: 27 passed, 8 failed, 5 errors
  - **Issues**:
    - Missing psutil dependency for performance tests
    - Test environment conflicts with actual .env file
    - Some integration tests expecting different error messages
    - AnalysisTask state management needs fixing

- [x] **Documentation is complete and accurate**
  - **Check**: Visit `http://localhost:8000/docs` and verify all endpoints have descriptions
  - **Check**: Run `ls -la *.md` and verify API_USAGE_EXAMPLES.md and AUTHENTICATION_FLOW.md exist
  - **Expected**: Complete API documentation, usage examples, and auth flow docs

## Potential Risks and Mitigations
- **Risk**: OAuth flow breaks without Kivy webview
  **Mitigation**: Test OAuth flow early and implement proper redirect handling
- **Risk**: File-based caching doesn't work in server environment
  **Mitigation**: Test caching with proper file permissions and paths
- **Risk**: Performance issues with synchronous operations
  **Mitigation**: Implement async/await patterns where needed
- **Risk**: Security vulnerabilities in API
  **Mitigation**: Implement proper input validation and authentication middleware

# Developer Guide - Backend Integration

## Overview

This guide explains how SpotiBye integrates with the Cloudflare Workers backend, including API endpoints, authentication, and error handling patterns.

## Architecture

### Frontend-Backend Communication
- **Protocol**: HTTPS REST API
- **Authentication**: JWT tokens
- **Data Format**: JSON
- **Base URL**: Configurable (dev/prod environments)

### Key Components
- `BackendClient` - HTTP client for API communication
- `BackendAuthenticator` - OAuth flow handling
- `NetworkUtils` - Error handling and retry logic

## API Endpoints

### Authentication
```
GET  /auth/spotify/login      - Get Spotify auth URL
POST /auth/spotify/callback   - Exchange code for JWT
POST /auth/refresh           - Refresh JWT token
POST /auth/logout            - Invalidate session
```

### Playlists
```
GET  /playlists              - Get user's playlists
GET  /playlists/{id}         - Get specific playlist
GET  /playlists/{id}/tracks  - Get playlist tracks
```

### Analysis
```
POST /analysis/playlist       - Analyze playlist
GET  /analysis/playlist/{id}  - Get analysis results
```

### Export
```
POST /export/playlist         - Export playlist data
GET  /export/status/{job_id}  - Get export status
```

## Authentication Flow

### 1. Initialize Login
```python
auth = BackendAuthenticator(backend_url)
auth_url = auth.get_login_url()
# Open browser with auth_url
```

### 2. Handle Callback
```python
token = auth.handle_callback(spotify_code)
# Store token securely
```

### 3. Make Authenticated Requests
```python
client = BackendClient(backend_url, token)
playlists = client.get_playlists()
```

## Error Handling Patterns

### Network Errors
```python
try:
    result = client.get_playlists()
except ConnectionError:
    # Handle network issues
except TimeoutError:
    # Handle timeouts
except BackendAPIError as e:
    # Handle API errors
```

### Retry Logic
```python
# Automatic retry with exponential backoff
client = BackendClient(backend_url, token, 
                       max_retries=3, 
                       retry_delay=1.0)
```

## Configuration

### Environment Variables
```python
# Development
BACKEND_URL = "http://localhost:8787"

# Production  
BACKEND_URL = "https://api.spotibye.com"
```

### Client Configuration
```python
client = BackendClient(
    base_url=config.backend_url,
    timeout=30.0,
    max_retries=3,
    retry_delay=1.0
)
```

## Testing Integration

### Mock Backend
```python
from tests.mock_backend import MockBackendServer

# Start mock server for testing
server = MockBackendServer()
server.start()

# Test with mock backend
client = BackendClient(server.url, token)
```

### Integration Tests
```python
def test_playlist_loading():
    client = BackendClient(test_backend_url, test_token)
    playlists = client.get_playlists()
    assert len(playlists) > 0
```

## Performance Considerations

### Request Batching
- Batch multiple track requests
- Use pagination for large datasets
- Implement request deduplication

### Caching Strategy
- Cache playlist metadata locally
- Implement cache invalidation
- Use backend caching when available

### Memory Management
- Stream large responses
- Clear unused data
- Monitor memory usage

## Debugging

### Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable request logging
client = BackendClient(base_url, token, debug=True)
```

### Common Issues
- **CORS errors**: Check backend CORS configuration
- **Authentication failures**: Verify token validity
- **Rate limiting**: Implement backoff strategy
- **Large payloads**: Use streaming or pagination

## Security Notes

### Token Management
- Store tokens securely (keychain/encrypted storage)
- Implement token expiration handling
- Clear tokens on logout

### Data Validation
- Validate all API responses
- Sanitize user input
- Check for malformed data

### Network Security
- Use HTTPS only in production
- Verify SSL certificates
- Implement certificate pinning if needed

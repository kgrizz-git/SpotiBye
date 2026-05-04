# API Usage Examples

This document provides examples of how to use the SpotiBye Backend API endpoints.

## Base URL
- Development: `http://localhost:8000`
- Production: `https://your-api-domain.com`

## Authentication

All API endpoints (except `/health` and `/auth/login`) require JWT authentication.

### 1. Login with Spotify OAuth

```bash
# Start OAuth flow - this will redirect to Spotify
curl -X GET "http://localhost:8000/auth/login"
```

### 2. Get Access Token

After completing the OAuth flow, you'll receive an access token. Use it in subsequent requests:

```bash
# Example with Bearer token
curl -X GET "http://localhost:8000/api/playlists" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. Refresh Access Token

```bash
curl -X POST "http://localhost:8000/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

### 4. Verify Authentication

```bash
curl -X GET "http://localhost:8000/auth/verify" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Logout

```bash
curl -X POST "http://localhost:8000/auth/logout" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## API Endpoints

### User Profile

```bash
# Get current user profile
curl -X GET "http://localhost:8000/api/user/profile" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Playlists

```bash
# Get user's playlists
curl -X GET "http://localhost:8000/api/playlists" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get specific playlist
curl -X GET "http://localhost:8000/api/playlists/PLAYLIST_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get playlist tracks (with pagination)
curl -X GET "http://localhost:8000/api/playlists/PLAYLIST_ID/tracks?offset=0&limit=50" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Analysis

```bash
# Start playlist analysis
curl -X POST "http://localhost:8000/api/analysis/start" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"playlist_id": "PLAYLIST_ID", "include_reccobeats": true}'

# Check analysis status
curl -X GET "http://localhost:8000/api/analysis/PLAYLIST_ID/status" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get analysis results
curl -X GET "http://localhost:8000/api/analysis/PLAYLIST_ID/results" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Cancel analysis
curl -X DELETE "http://localhost:8000/api/analysis/PLAYLIST_ID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get track audio features
curl -X GET "http://localhost:8000/api/tracks/TRACK_ID/audio-features" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Export

```bash
# Immediate export (synchronous)
curl -X GET "http://localhost:8000/api/export/playlist/PLAYLIST_ID/immediate?format=xlsx&include_audio_features=true" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  --output playlist_export.xlsx

# Start background export
curl -X POST "http://localhost:8000/api/export/start" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"playlist_id": "PLAYLIST_ID", "format": "xlsx", "include_audio_features": true}'

# Download exported file
curl -X GET "http://localhost:8000/api/export/EXPORT_ID/download" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  --output exported_playlist.xlsx
```

## Response Formats

### Success Response (200 OK)
```json
{
  "data": {
    // Response data here
  },
  "message": "Success"
}
```

### Error Response (4xx/5xx)
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Rate Limiting

- API endpoints are rate limited to prevent abuse
- Standard limit: 100 requests per minute per user
- Export endpoints: 10 requests per minute per user

## WebSocket Support (Future)

Real-time updates for analysis progress will be available via WebSocket connections:

```javascript
// Example WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws/analysis/PLAYLIST_ID');
ws.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Analysis progress:', data);
};
```

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid or missing token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Server issue |

## Testing with Postman

Import the following environment variables:

```json
{
  "name": "SpotiBye API",
  "values": [
    {
      "key": "base_url",
      "value": "http://localhost:8000",
      "enabled": true
    },
    {
      "key": "access_token",
      "value": "",
      "enabled": true
    }
  ]
}
```

Then use the collection examples provided in the `postman_collection.json` file.

## SDK Examples

### Python

```python
import requests

class SpotiByeAPI:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def get_playlists(self):
        response = requests.get(f"{self.base_url}/api/playlists", headers=self.headers)
        return response.json()

    def start_analysis(self, playlist_id):
        data = {"playlist_id": playlist_id, "include_reccobeats": True}
        response = requests.post(f"{self.base_url}/api/analysis/start",
                               headers=self.headers, json=data)
        return response.json()

# Usage
api = SpotiByeAPI("http://localhost:8000", "your_access_token")
playlists = api.get_playlists()
```

### JavaScript

```javascript
class SpotiByeAPI {
    constructor(baseUrl, accessToken) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
        };
    }

    async getPlaylists() {
        const response = await fetch(`${this.baseUrl}/api/playlists`, {
            headers: this.headers
        });
        return response.json();
    }

    async startAnalysis(playlistId) {
        const response = await fetch(`${this.baseUrl}/api/analysis/start`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                playlist_id: playlistId,
                include_reccobeats: true
            })
        });
        return response.json();
    }
}

// Usage
const api = new SpotiByeAPI('http://localhost:8000', 'your_access_token');
api.getPlaylists().then(playlists => console.log(playlists));
```

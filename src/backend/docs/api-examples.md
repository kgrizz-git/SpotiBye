# API Usage Examples

This document provides practical examples of how to use the SpotiBye API endpoints. Each example includes request/response formats, error handling, and best practices.

## Table of Contents

- [Authentication Flow](#authentication-flow)
- [Spotify Data](#spotify-data)
- [Playlist Analysis](#playlist-analysis)
- [Export Functionality](#export-functionality)
- [Error Handling](#error-handling)
- [Complete Examples](#complete-examples)

## Authentication Flow

### Step 1: Initiate Spotify OAuth

```javascript
// Request
const response = await fetch('https://spotibye-api.workers.dev/auth/spotify/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    redirect_uri: 'http://localhost:3000/callback',
    state: 'random-state-string-123'
  })
});

// Response (200 OK)
{
  "data": {
    "auth_url": "https://accounts.spotify.com/authorize?response_type=code&client_id=your-client-id&scope=user-read-private%20user-read-email%20playlist-read-private%20playlist-read-collaborative&redirect_uri=http://localhost:3000/callback&state=random-state-string-123",
    "state": "random-state-string-123"
  }
}
```

### Step 2: Handle OAuth Callback

```javascript
// After user authorizes, Spotify redirects to your callback URL
// Extract code and state from URL parameters
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state');

// Exchange code for JWT tokens
const response = await fetch('https://spotibye-api.workers.dev/auth/spotify/callback', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  }
});

// Response (200 OK)
{
  "data": {
    "access_token": "[JWT_TOKEN]",
    "refresh_token": "refresh-token-string",
    "expires_in": 3600,
    "user": {
      "id": "user-123",
      "display_name": "Test User",
      "email": "test@example.com"
    }
  }
}
```

### Step 3: Use JWT Token

```javascript
// Store token securely (e.g., in httpOnly cookie or secure storage)
localStorage.setItem('spotibye_token', accessToken);

// Include token in subsequent requests
const response = await fetch('https://spotibye-api.workers.dev/spotify/playlists', {
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});
```

## Spotify Data

### Get User Playlists

```javascript
// Basic request
const response = await fetch('https://spotibye-api.workers.dev/spotify/playlists', {
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});

// Response (200 OK)
{
  "data": {
    "playlists": [
      {
        "id": "playlist-123",
        "name": "My Favorite Songs",
        "description": "All my favorite tracks",
        "tracks_count": 100,
        "owner": "Test User",
        "followers": 42,
        "public": true,
        "collaborative": false,
        "images": [
          {
            "url": "https://i.scdn.co/image/ab67616d0000b2736e9c5b3b3b3b3b3b3b3b3b3b",
            "height": 300,
            "width": 300
          }
        ]
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
}
```

### Get Playlist Details

```javascript
const playlistId = 'playlist-123';
const response = await fetch(`https://spotibye-api.workers.dev/spotify/playlists/${playlistId}`, {
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});

// Response (200 OK)
{
  "data": {
    "playlist": {
      "id": "playlist-123",
      "name": "My Favorite Songs",
      "description": "All my favorite tracks",
      "tracks_count": 100,
      "owner": "Test User",
      "followers": 42,
      "public": true,
      "collaborative": false,
      "images": [
        {
          "url": "https://i.scdn.co/image/ab67616d0000b2736e9c5b3b3b3b3b3b3b3b3b3b",
          "height": 300,
          "width": 300
        }
      ]
    }
  }
}
```

### Get Playlist Tracks (with Pagination)

```javascript
const playlistId = 'playlist-123';
const limit = 50;
const offset = 0;

const response = await fetch(
  `https://spotibye-api.workers.dev/spotify/playlists/${playlistId}/tracks?limit=${limit}&offset=${offset}`,
  {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    }
  }
);

// Response (200 OK)
{
  "data": {
    "tracks": [
      {
        "id": "track-123",
        "name": "Example Song",
        "artists": [
          {
            "id": "artist-123",
            "name": "Example Artist"
          }
        ],
        "album": {
          "id": "album-123",
          "name": "Example Album"
        },
        "duration_ms": 180000,
        "track_number": 1,
        "explicit": false,
        "preview_url": "https://p.scdn.co/mp3-preview/abcdef123456",
        "external_urls": {
          "spotify": "https://open.spotify.com/track/track-123"
        }
      }
    ],
    "total": 100,
    "limit": 50,
    "offset": 0
  }
}
```

## Playlist Analysis

Analysis is asynchronous: POST starts (or resumes) a job and returns a status record; poll `GET .../status` until `status` is `completed`, then fetch `GET .../results`. The request body is currently ignored.

### Step 1: Start Analysis

```javascript
const playlistId = 'playlist-123';
const response = await fetch(`https://spotibye-api.workers.dev/analysis/playlist/${playlistId}`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});

// Response (200 OK) — job just queued, or the status of an existing job
{
  "data": {
    "job_id": "job-123",
    "playlist_id": "playlist-123",
    "user_id": "user-123",
    "status": "queued",
    "queued_at": "2026-07-07T12:00:00.000Z",
    "progress": 0
  },
  "meta": { "timestamp": "2026-07-07T12:00:00.000Z" }
}
```

### Step 2: Poll Status

```javascript
const statusResponse = await fetch(`https://spotibye-api.workers.dev/analysis/playlist/${playlistId}/status`, {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});

// Response (200 OK) while running
{
  "data": {
    "job_id": "job-123",
    "playlist_id": "playlist-123",
    "user_id": "user-123",
    "status": "processing",
    "progress": 65
  },
  "meta": { "timestamp": "2026-07-07T12:00:05.000Z" }
}
```

`status` progresses through `queued` → `processing` (possibly `retrying`) → `completed` or `failed`. `progress` moves 20 → 50 → 65 → 70 → 85 → 95 → 100.

### Step 3: Fetch Results

```javascript
const resultsResponse = await fetch(`https://spotibye-api.workers.dev/analysis/playlist/${playlistId}/results`, {
  headers: { 'Authorization': `Bearer ${accessToken}` }
});

// Response (200 OK)
{
  "data": {
    "job_id": "job-123",
    "playlist_id": "playlist-123",
    "user_id": "user-123",
    "status": "completed",
    "computed_at": "2026-07-07T12:00:00.000Z",
    "completed_at": "2026-07-07T12:00:10.000Z",
    "overview": {
      "total_tracks": 100,
      "total_duration_ms": 21600000,
      "average_duration_ms": 216000,
      "formatted_duration": "6h 0m 0s"
    },
    "artists": {
      "unique_artists": 42,
      "top_artists": [
        { "artist": "Artist One", "count": 8 },
        { "artist": "Artist Two", "count": 5 }
      ],
      "diversity": 0.42
    },
    "genre_distribution": {
      "Pop": { "count": 30, "percentage": 30.0 },
      "Electronic": { "count": 20, "percentage": 20.0 }
    },
    "audio_features": {
      "track_count": 100,
      "averages": {
        "acousticness": 0.25,
        "danceability": 0.82,
        "energy": 0.75,
        "instrumentalness": 0.15,
        "liveness": 0.2,
        "loudness": -6.0,
        "speechiness": 0.05,
        "tempo": 128.5,
        "valence": 0.68
      },
      "key_mode_distribution": {
        "key_percentages": { "C": 42.0, "G": 30.0 },
        "dominant_key": "C",
        "dominant_key_percentage": 42.0,
        "mode_percentages": { "major": 70.0, "minor": 30.0 },
        "dominant_mode": "major"
      }
    },
    "insights": ["Top genres: Pop, Electronic."],
    "reccobeats_metadata": {
      "isrc_available": 95,
      "popularity_min": 20,
      "popularity_max": 90,
      "retrieved_at": "2026-07-07T12:00:09.000Z"
    },
    "errors": [],
    "unique_track_count": 100,
    "audio_features_resolved_count": 100,
    "track_metadata_resolved_count": 98,
    "enrichment_resolved_track_count": 98,
    "schema_version": "1.1"
  },
  "meta": { "timestamp": "2026-07-07T12:00:11.000Z" }
}
```

`audio_features` and `reccobeats_metadata` come from ReccoBeats and are best-effort: `errors` is always present (empty on full success) and lists any partial failures (e.g. `{"source": "reccobeats:track-metadata", "message": "..."}"`) instead of failing the whole analysis. Completeness counts compare unique playlist track IDs to hits plus per-endpoint absent sentinels (not `audio_features.track_count` alone). If cached results predate the current `schema_version`, `GET .../results` returns `404 ANALYSIS_RESULTS_NOT_FOUND` and a subsequent POST enqueues a fresh job.

## Export Functionality

### Generate CSV Export

```javascript
const playlistId = 'playlist-123';
const response = await fetch(`https://spotibye-api.workers.dev/export/playlist/${playlistId}`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    format: 'csv',
    include_audio_features: true,
    include_analysis: false
  })
});

// Response (200 OK)
{
  "data": {
    "export_id": "export-123",
    "format": "csv",
    "estimated_size": 1024000,
    "expires_at": "2023-12-13T23:00:00Z",
    "download_url": "/export/playlist/playlist-123/download?export_id=export-123"
  }
}
```

### Generate JSON Export

```javascript
const response = await fetch(`https://spotibye-api.workers.dev/export/playlist/${playlistId}`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    format: 'json',
    include_audio_features: true,
    include_analysis: true
  })
});

// Response (200 OK)
{
  "data": {
    "export_id": "export-456",
    "format": "json",
    "estimated_size": 2048000,
    "expires_at": "2023-12-13T23:00:00Z",
    "download_url": "/export/playlist/playlist-123/download?export_id=export-456"
  }
}
```

### Download Export File

```javascript
const exportId = 'export-123';
const playlistId = 'playlist-123';

const response = await fetch(
  `https://spotibye-api.workers.dev/export/playlist/${playlistId}/download?export_id=${exportId}`,
  {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  }
);

// For CSV export
if (response.ok) {
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'playlist-export.csv';
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

// For JSON export
if (response.ok) {
  const data = await response.json();
  console.log('Export data:', data);
}
```

## Error Handling

### Authentication Errors

```javascript
try {
  const response = await fetch('https://spotibye-api.workers.dev/spotify/playlists', {
    headers: {
      'Authorization': `Bearer ${invalidToken}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    const error = await response.json();

    switch (response.status) {
      case 401:
        console.error('Unauthorized - please log in again');
        // Redirect to login
        break;
      case 429:
        console.error('Rate limit exceeded - please try again later');
        // Show rate limit message
        break;
      case 500:
        console.error('Server error - please try again later');
        // Show server error message
        break;
      default:
        console.error('Error:', error.error.message);
    }
    return;
  }

  const data = await response.json();
  // Process successful response
} catch (error) {
  console.error('Network error:', error);
  // Handle network errors
}
```

### Validation Errors

```javascript
const response = await fetch('https://spotibye-api.workers.dev/auth/spotify/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    // Missing required redirect_uri
    state: 'random-state'
  })
});

if (!response.ok) {
  const error = await response.json();
  console.error('Validation error:', error.error.message);
  // Output: "Validation error: redirect_uri is required"
}

// Response (400 Bad Request)
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "redirect_uri is required",
    "details": {
      "field": "redirect_uri",
      "value": null
    }
  }
}
```

## Complete Examples

### Complete Authentication and Data Flow

```javascript
class SpotiByeAPI {
  constructor(baseURL = 'https://spotibye-api.workers.dev') {
    this.baseURL = baseURL;
    this.token = null;
  }

  // Authentication flow
  async authenticate(redirectUri) {
    // Step 1: Get auth URL
    const state = this.generateState();
    const loginResponse = await fetch(`${this.baseURL}/auth/spotify/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ redirect_uri: redirectUri, state })
    });

    const { data } = await loginResponse.json();

    // Redirect user to Spotify
    window.location.href = data.auth_url;
  }

  // Handle callback and get token
  async handleCallback(code, state) {
    const callbackResponse = await fetch(
      `${this.baseURL}/auth/spotify/callback?code=${code}&state=${state}`
    );

    const { data } = await callbackResponse.json();
    this.token = data.access_token;

    // Store token
    localStorage.setItem('spotibye_token', this.token);

    return data.user;
  }

  // Get user playlists
  async getPlaylists(limit = 50, offset = 0) {
    const response = await fetch(
      `${this.baseURL}/spotify/playlists?limit=${limit}&offset=${offset}`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch playlists: ${response.status}`);
    }

    const { data } = await response.json();
    return data.playlists;
  }

  // Analyze playlist: start (or resume) the job, poll status, return results.
  // The request body is ignored by the backend.
  async analyzePlaylist(playlistId, { pollIntervalMs = 2000, maxWaitMs = 120000 } = {}) {
    const start = await fetch(`${this.baseURL}/analysis/playlist/${playlistId}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      }
    });
    if (!start.ok) {
      throw new Error(`Failed to start playlist analysis: ${start.status}`);
    }

    const deadline = Date.now() + maxWaitMs;
    while (Date.now() < deadline) {
      const statusResponse = await fetch(`${this.baseURL}/analysis/playlist/${playlistId}/status`, {
        headers: { 'Authorization': `Bearer ${this.token}` }
      });
      if (!statusResponse.ok) {
        throw new Error(`Failed to get analysis status: ${statusResponse.status}`);
      }
      const { data: status } = await statusResponse.json();

      if (status.status === 'completed') {
        const resultsResponse = await fetch(`${this.baseURL}/analysis/playlist/${playlistId}/results`, {
          headers: { 'Authorization': `Bearer ${this.token}` }
        });
        if (!resultsResponse.ok) {
          throw new Error(`Failed to get analysis results: ${resultsResponse.status}`);
        }
        const { data: results } = await resultsResponse.json();
        return results;
      }
      if (status.status === 'failed') {
        throw new Error(`Analysis failed: ${status.error ?? 'unknown error'}`);
      }

      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    }
    throw new Error('Analysis timed out');
  }

  // Export playlist
  async exportPlaylist(playlistId, format = 'csv', options = {}) {
    const response = await fetch(`${this.baseURL}/export/playlist/${playlistId}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        format,
        include_audio_features: true,
        include_analysis: false,
        ...options
      })
    });

    if (!response.ok) {
      throw new Error(`Failed to export playlist: ${response.status}`);
    }

    const { data } = await response.json();
    return data;
  }

  // Download export
  async downloadExport(playlistId, exportId) {
    const response = await fetch(
      `${this.baseURL}/export/playlist/${playlistId}/download?export_id=${exportId}`,
      {
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to download export: ${response.status}`);
    }

    return response.blob();
  }

  // Utility methods
  generateState() {
    return Math.random().toString(36).substring(2, 15);
  }

  // Check if authenticated
  isAuthenticated() {
    return !!this.token;
  }

  // Load token from storage
  loadToken() {
    this.token = localStorage.getItem('spotibye_token');
  }

  // Clear token
  logout() {
    this.token = null;
    localStorage.removeItem('spotibye_token');
  }
}

// Usage example
const api = new SpotiByeAPI();

// Check if already authenticated
api.loadToken();

if (!api.isAuthenticated()) {
  // Start authentication flow
  await api.authenticate('http://localhost:3000/callback');
} else {
  // User is already authenticated, fetch data
  try {
    const playlists = await api.getPlaylists();
    console.log('User playlists:', playlists);

    if (playlists.length > 0) {
      const firstPlaylist = playlists[0];

      // Analyze the first playlist (starts the job, polls, returns results)
      const analysis = await api.analyzePlaylist(firstPlaylist.id);
      console.log('Playlist analysis:', analysis);

      // Export the playlist
      const exportData = await api.exportPlaylist(firstPlaylist.id, 'csv');
      console.log('Export ready:', exportData);

      // Download the export
      const blob = await api.downloadExport(firstPlaylist.id, exportData.export_id);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${firstPlaylist.name.replace(/[^a-z0-9]/gi, '_')}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }
  } catch (error) {
    console.error('API Error:', error);

    // Handle expired token
    if (error.message.includes('401')) {
      api.logout();
      await api.authenticate('http://localhost:3000/callback');
    }
  }
}
```

### React Hook Example

```javascript
import { useState, useEffect, useCallback } from 'react';

function useSpotiByeAPI() {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Initialize token from localStorage
  useEffect(() => {
    const savedToken = localStorage.getItem('spotibye_token');
    if (savedToken) {
      setToken(savedToken);
    }
  }, []);

  // Login function
  const login = useCallback(async (redirectUri) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('https://spotibye-api.workers.dev/auth/spotify/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ redirect_uri: redirectUri })
      });

      const { data } = await response.json();
      window.location.href = data.auth_url;
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  }, []);

  // Handle callback
  const handleCallback = useCallback(async (code, state) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `https://spotibye-api.workers.dev/auth/spotify/callback?code=${code}&state=${state}`
      );

      const { data } = await response.json();
      setToken(data.access_token);
      setUser(data.user);
      localStorage.setItem('spotibye_token', data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Get playlists
  const getPlaylists = useCallback(async (limit = 50, offset = 0) => {
    if (!token) throw new Error('Not authenticated');

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `https://spotibye-api.workers.dev/spotify/playlists?limit=${limit}&offset=${offset}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch playlists: ${response.status}`);
      }

      const { data } = await response.json();
      return data.playlists;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Logout
  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('spotibye_token');
  }, []);

  return {
    token,
    user,
    loading,
    error,
    isAuthenticated: !!token,
    login,
    handleCallback,
    getPlaylists,
    logout
  };
}

// Component usage
function PlaylistManager() {
  const { isAuthenticated, user, loading, error, login, getPlaylists, logout } = useSpotiByeAPI();
  const [playlists, setPlaylists] = useState([]);

  useEffect(() => {
    if (isAuthenticated) {
      getPlaylists().then(setPlaylists).catch(console.error);
    }
  }, [isAuthenticated, getPlaylists]);

  if (!isAuthenticated) {
    return (
      <div>
        <h2>SpotiBye - Login Required</h2>
        <button onClick={() => login('http://localhost:3000/callback')}>
          Login with Spotify
        </button>
      </div>
    );
  }

  return (
    <div>
      <h2>Welcome, {user.display_name}!</h2>
      <button onClick={logout}>Logout</button>

      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}

      <h3>Your Playlists</h3>
      <ul>
        {playlists.map(playlist => (
          <li key={playlist.id}>
            {playlist.name} ({playlist.tracks_count} tracks)
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## Best Practices

### Token Management
- Store tokens securely (httpOnly cookies recommended)
- Implement token refresh logic
- Handle token expiration gracefully
- Clear tokens on logout

### Error Handling
- Always check response.ok before processing
- Implement retry logic for network errors
- Show user-friendly error messages
- Log errors for debugging

### Performance
- Use pagination for large datasets
- Implement caching where appropriate
- Cancel requests when component unmounts
- Use loading states for better UX

### Security
- Never expose tokens in client-side code
- Use HTTPS in production
- Validate all user inputs
- Implement rate limiting on client side

## Testing Examples

### Mock API for Testing

```javascript
// Mock API for testing
class MockSpotiByeAPI extends SpotiByeAPI {
  async getPlaylists() {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));

    return [
      {
        id: 'mock-playlist-1',
        name: 'Mock Playlist 1',
        tracks_count: 25,
        owner: 'Test User'
      },
      {
        id: 'mock-playlist-2',
        name: 'Mock Playlist 2',
        tracks_count: 50,
        owner: 'Test User'
      }
    ];
  }

  async analyzePlaylist(playlistId) {
    await new Promise(resolve => setTimeout(resolve, 2000));

    return {
      job_id: 'mock-job-1',
      playlist_id: playlistId,
      status: 'completed',
      overview: { total_tracks: 25 },
      audio_features: { track_count: 25, averages: { tempo: 120, energy: 0.75 } },
      genre_distribution: { Pop: { count: 15, percentage: 60 }, Rock: { count: 10, percentage: 40 } },
      errors: [],
      unique_track_count: 25,
      audio_features_resolved_count: 25,
      track_metadata_resolved_count: 25,
      enrichment_resolved_track_count: 25,
      schema_version: '1.1'
    };
  }
}

// Usage in tests
const mockAPI = new MockSpotiByeAPI();
const playlists = await mockAPI.getPlaylists();
console.log('Mock playlists:', playlists);
```

This comprehensive guide provides practical examples for integrating with the SpotiBye API, from basic authentication to complete workflow implementations.

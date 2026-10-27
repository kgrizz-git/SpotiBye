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

All examples use one base URL. Replace the placeholder with your Worker's URL.
They use the development Worker, because its `ALLOWED_REDIRECT_URIS` includes the
`http://localhost:3000/callback` redirect used below. Production's allowlist does not.

```javascript
const API_BASE = 'https://spotibye-backend-development.<your-subdomain>.workers.dev';
```

### Step 1: Initiate Spotify OAuth

`redirect_uri` must exactly match an entry in the Worker's `ALLOWED_REDIRECT_URIS`. The backend generates `state` and the PKCE verifier itself and keeps them in KV for 10 minutes.

```javascript
// Request
const response = await fetch(`${API_BASE}/auth/spotify/login`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    redirect_uri: 'http://localhost:3000/callback'
  })
});
const { data } = await response.json();

// Save the backend's state so the callback can be checked against it.
sessionStorage.setItem('spotibye_oauth_state', data.state);
window.location.href = data.auth_url;

// Response (200 OK)
{
  "data": {
    "auth_url": "https://accounts.spotify.com/authorize?response_type=code&client_id=your-client-id&scope=user-read-private+user-read-email+playlist-read-private+playlist-read-collaborative&redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fcallback&state=<uuid>&code_challenge_method=S256&code_challenge=<challenge>",
    "state": "<uuid>"
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

// Reject a callback from any login this page did not start. The backend only
// checks that the state exists, not that this client created it.
const expectedState = sessionStorage.getItem('spotibye_oauth_state');
if (!state || !expectedState || state !== expectedState) {
  throw new Error('OAuth state mismatch: restart login');
}
// Consume the saved state only on a match, so a forged callback cannot
// spend it before the real one arrives.
sessionStorage.removeItem('spotibye_oauth_state');

// Exchange code for a SpotiBye JWT
const response = await fetch(
  `${API_BASE}/auth/spotify/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
);
const { data } = await response.json();
const token = data.token;

// Response (200 OK)
{
  "data": {
    "token": "[JWT_TOKEN]",
    "user": {
      "id": "user-123",
      "display_name": "Test User",
      "email": "test@example.com",
      "images": []
    },
    "expires_in": 2592000,
    "spotify_access_expires_in": 3600
  }
}
```

`user` is the Spotify profile. `expires_in` is the JWT and session lifetime (30 days). The Spotify refresh token stays server-side, and the auth middleware refreshes the Spotify access token transparently. `POST /auth/spotify/refresh` (with the current Bearer token) issues a new JWT as `data.access_token`.

### Step 3: Use JWT Token

Keep the JWT out of `localStorage` and `sessionStorage`. Any script on the page
can read them, so one XSS bug leaks a 30-day bearer token. Safer options:

- **Desktop or mobile client:** store it in the OS keychain or credential store.
- **Browser app:** keep it in memory only, and log in again after a reload. For
  persistence, put a small backend-for-frontend in front of SpotiBye that holds
  the JWT and gives the browser an `HttpOnly`, `Secure`, `SameSite` session
  cookie. The SpotiBye backend does not set cookies itself.

The examples below keep the token in a variable.

```javascript
// Send it as a Bearer token on every authenticated request
const response = await fetch(`${API_BASE}/spotify/playlists`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
```

Other auth routes: `GET /auth/me` returns the JWT's user claims, and `POST /auth/logout` deletes the session.

## Spotify Data

Spotify routes return Spotify objects as `data`, plus `meta.timestamp`. Cached responses also carry `meta.cached: true`. Pass `force_refresh=true` to skip the cache on playlist details and items.

### Get User Playlists

The backend aggregates every page of the user's playlists and caches the list for 5 minutes. The route takes no pagination parameters.

```javascript
const response = await fetch(`${API_BASE}/spotify/playlists`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

// Response (200 OK) — `data` is an array of Spotify playlist objects
{
  "data": [
    {
      "id": "playlist-123",
      "name": "My Favorite Songs",
      "description": "All my favorite tracks",
      "snapshot_id": "snapshot-abc",
      "public": true,
      "collaborative": false,
      "owner": { "id": "user-123", "display_name": "Test User" },
      "items": { "href": "https://api.spotify.com/v1/playlists/playlist-123/items", "total": 100 },
      "images": [
        {
          "url": "https://i.scdn.co/image/ab67616d0000b2736e9c5b3b3b3b3b3b3b3b3b3b",
          "height": 300,
          "width": 300
        }
      ],
      "external_urls": { "spotify": "https://open.spotify.com/playlist/playlist-123" },
      "uri": "spotify:playlist:playlist-123"
    }
  ],
  "meta": { "timestamp": "2026-07-07T12:00:00.000Z" }
}
```

### Get Playlist Details

```javascript
const playlistId = 'playlist-123';
const response = await fetch(`${API_BASE}/spotify/playlists/${playlistId}`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

// Response (200 OK) — `data` is the Spotify playlist object (cached for 10 minutes)
{
  "data": {
    "id": "playlist-123",
    "name": "My Favorite Songs",
    "description": "All my favorite tracks",
    "public": true,
    "collaborative": false,
    "owner": { "id": "user-123", "display_name": "Test User" },
    "followers": { "total": 42 },
    "images": [],
    "external_urls": { "spotify": "https://open.spotify.com/playlist/playlist-123" },
    "uri": "spotify:playlist:playlist-123"
  },
  "meta": { "timestamp": "2026-07-07T12:00:00.000Z", "cached": false }
}
```

### Get Playlist Items (with Pagination)

`GET /spotify/playlists/:id/items` is the primary route. `/tracks` is a backward-compatible alias. `limit` is 1–50 (default 50) and `offset` defaults to 0.

```javascript
const playlistId = 'playlist-123';
const limit = 50;
const offset = 0;

const response = await fetch(
  `${API_BASE}/spotify/playlists/${playlistId}/items?limit=${limit}&offset=${offset}`,
  {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  }
);

// Response (200 OK)
{
  "data": {
    "href": "https://api.spotify.com/v1/playlists/playlist-123/items?offset=0&limit=50",
    "total": 100,
    "rawCount": 50,
    "items": [
      {
        "added_at": "2026-01-01T00:00:00Z",
        "added_by": { "id": "user-123" },
        "track": {
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
          "explicit": false,
          "preview_url": null,
          "external_urls": {
            "spotify": "https://open.spotify.com/track/track-123"
          },
          "uri": "spotify:track:track-123"
        }
      }
    ]
  },
  "meta": { "timestamp": "2026-07-07T12:00:00.000Z", "cached": false }
}
```

Items without a track ID (local or unavailable tracks) are dropped from `items`. Advance `offset` by `rawCount`, not by `items.length`.

## Playlist Analysis

Analysis is asynchronous: POST starts (or resumes) a job and returns a status record; poll `GET .../status` until `status` is `completed`, then fetch `GET .../results`. The optional JSON body (or query string) accepts `force_enrichment: true`, which clears cached status and results before re-running, and `refresh: true`, which re-runs while reusing per-track cache. Without either flag, POST returns the existing status if a job is queued, processing, or completed with current-schema results.

### Step 1: Start Analysis

```javascript
const playlistId = 'playlist-123';
const response = await fetch(`${API_BASE}/analysis/playlist/${playlistId}`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
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
const statusResponse = await fetch(`${API_BASE}/analysis/playlist/${playlistId}/status`, {
  headers: { 'Authorization': `Bearer ${token}` }
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

`status` progresses through `queued` → `processing` (possibly `retrying`) → `completed` or `failed`. `progress` is a 0–100 percentage that only increases. A failed job carries an `error` string. `GET .../status` returns `404 ANALYSIS_NOT_FOUND` when no job exists. `DELETE /analysis/playlist/:id` clears status and results.

### Step 3: Fetch Results

```javascript
const resultsResponse = await fetch(`${API_BASE}/analysis/playlist/${playlistId}/results`, {
  headers: { 'Authorization': `Bearer ${token}` }
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

`POST /export/playlist/:id` builds the export synchronously and returns the completed status record. `format` is `csv`, `json`, or `xlsx`, and any other value falls back to `xlsx`. `include_audio_features: true` adds ReccoBeats per-track enrichment columns. The status, export data, and file bytes are cached for 1 hour. A repeat POST with the same format and enrichment flag returns the cached record.

### Generate CSV Export

```javascript
const playlistId = 'playlist-123';
const response = await fetch(`${API_BASE}/export/playlist/${playlistId}`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    format: 'csv',
    include_audio_features: true
  })
});

// Response (200 OK)
{
  "data": {
    "job_id": "job-123",
    "playlist_id": "playlist-123",
    "user_id": "user-123",
    "status": "completed",
    "started_at": "2026-07-07T12:00:00.000Z",
    "completed_at": "2026-07-07T12:00:04.000Z",
    "progress": 100,
    "file_url": "/export/playlist/playlist-123/download",
    "file_format": "csv",
    "include_audio_features": true,
    "file_size": 1024000,
    "track_count": 100
  },
  "meta": { "timestamp": "2026-07-07T12:00:04.000Z", "request_id": "<uuid>" }
}
```

`GET /export/playlist/:id/status` returns the same record, or `404 EXPORT_NOT_FOUND`. `DELETE /export/playlist/:id` clears the cached export.

### Download Export File

The download route serves the most recent export for the playlist. It takes no export ID. The response is the file itself with a `Content-Disposition: attachment` header, or `404 EXPORT_DATA_NOT_FOUND` if nothing is cached.

```javascript
const playlistId = 'playlist-123';

const response = await fetch(`${API_BASE}/export/playlist/${playlistId}/download`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

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
```

## Error Handling

Errors use the envelope `{ "error": { "code", "message", ... } }`. Middleware errors also include `timestamp`, `request_id`, and `details: { path, method }`.

### Authentication Errors

A missing, invalid, or expired JWT returns `401` with code `UNAUTHORIZED`. A Spotify refresh token that Spotify rejects returns `401 AUTH_REQUIRED`, and the user must log in again.

```javascript
try {
  const response = await fetch(`${API_BASE}/spotify/playlists`, {
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
        // SPOTIFY_RATE_LIMITED: Spotify kept rate limiting after the backend's retries
        console.error('Spotify rate limit hit - please try again later');
        break;
      case 500:
        console.error('Server error - please try again later');
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
const response = await fetch(`${API_BASE}/auth/spotify/login`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    redirect_uri: ''
  })
});

if (!response.ok) {
  const error = await response.json();
  console.error('Validation error:', error.error.message);
  // Output: "Validation error: redirect_uri: redirect_uri is required"
}

// Response (400 Bad Request)
{
  "error": {
    "code": "MISSING_REDIRECT_URI",
    "message": "redirect_uri: redirect_uri is required"
  }
}
```

Request validation failures return `400` with a route-specific code or `VALIDATION_ERROR`. A `redirect_uri` outside the allowlist returns `400 DISALLOWED_REDIRECT_URI`.

## Complete Examples

### Complete Authentication and Data Flow

```javascript
class SpotiByeAPI {
  constructor(baseURL = API_BASE) {
    this.baseURL = baseURL;
    this.token = null;
  }

  // Authentication flow
  async authenticate(redirectUri) {
    // Step 1: Get auth URL (the backend generates state)
    const loginResponse = await fetch(`${this.baseURL}/auth/spotify/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ redirect_uri: redirectUri })
    });

    const { data } = await loginResponse.json();

    // Save the state to check on callback, then redirect user to Spotify
    sessionStorage.setItem('spotibye_oauth_state', data.state);
    window.location.href = data.auth_url;
  }

  // Handle callback and get token
  async handleCallback(code, state) {
    const expectedState = sessionStorage.getItem('spotibye_oauth_state');
    if (!state || !expectedState || state !== expectedState) {
      throw new Error('OAuth state mismatch: restart login');
    }
    // Consume the saved state only on a match, so a forged callback cannot
    // spend it before the real one arrives.
    sessionStorage.removeItem('spotibye_oauth_state');

    const callbackResponse = await fetch(
      `${this.baseURL}/auth/spotify/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
    );

    const { data } = await callbackResponse.json();
    // Kept in memory only; see "Step 3: Use JWT Token" for storage trade-offs.
    this.token = data.token;

    return data.user;
  }

  // Get user playlists (the backend returns every page in one array)
  async getPlaylists() {
    const response = await fetch(`${this.baseURL}/spotify/playlists`, {
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch playlists: ${response.status}`);
    }

    const { data } = await response.json();
    return data;
  }

  // Analyze playlist: start (or resume) the job, poll status, return results.
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
        ...options
      })
    });

    if (!response.ok) {
      throw new Error(`Failed to export playlist: ${response.status}`);
    }

    const { data } = await response.json();
    return data;
  }

  // Download the most recent export
  async downloadExport(playlistId) {
    const response = await fetch(`${this.baseURL}/export/playlist/${playlistId}/download`, {
      headers: {
        'Authorization': `Bearer ${this.token}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to download export: ${response.status}`);
    }

    return response.blob();
  }

  // Check if authenticated
  isAuthenticated() {
    return !!this.token;
  }

  // Clear token
  logout() {
    this.token = null;
  }
}

// Usage example
const api = new SpotiByeAPI();

// Finish a login if Spotify just redirected back here
const params = new URLSearchParams(window.location.search);
const clearCallbackParams = () =>
  history.replaceState(null, '', window.location.pathname + window.location.hash);
let loginFailed = false;

if (params.has('error')) {
  // The user denied access, or Spotify failed. There is no code to exchange.
  console.error('Spotify login failed:', params.get('error'));
  loginFailed = true;
  clearCallbackParams();
} else if (params.has('code')) {
  try {
    await api.handleCallback(params.get('code'), params.get('state'));
  } catch (error) {
    console.error('Login failed:', error);
    loginFailed = true;
  } finally {
    // Drop code and state so a reload does not replay a consumed callback.
    clearCallbackParams();
  }
}

if (loginFailed) {
  // Show a "Log in with Spotify" button here. Redirecting straight back to
  // Spotify after a denial would loop.
} else if (!api.isAuthenticated()) {
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
      const blob = await api.downloadExport(firstPlaylist.id);

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

  // The token lives in React state only; see "Step 3: Use JWT Token".

  // Login function
  const login = useCallback(async (redirectUri) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/auth/spotify/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ redirect_uri: redirectUri })
      });

      const { data } = await response.json();
      sessionStorage.setItem('spotibye_oauth_state', data.state);
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
      const expectedState = sessionStorage.getItem('spotibye_oauth_state');
      if (!state || !expectedState || state !== expectedState) {
        throw new Error('OAuth state mismatch: restart login');
      }
      // Consume the saved state only on a match, so a forged callback cannot
      // spend it before the real one arrives.
      sessionStorage.removeItem('spotibye_oauth_state');

      const response = await fetch(
        `${API_BASE}/auth/spotify/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`
      );

      const { data } = await response.json();
      setToken(data.token);
      setUser(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Get playlists
  const getPlaylists = useCallback(async () => {
    if (!token) throw new Error('Not authenticated');

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/spotify/playlists`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch playlists: ${response.status}`);
      }

      const { data } = await response.json();
      return data;
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
      <h2>Welcome{user ? `, ${user.display_name}` : ''}!</h2>
      <button onClick={logout}>Logout</button>

      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}

      <h3>Your Playlists</h3>
      <ul>
        {playlists.map(playlist => (
          <li key={playlist.id}>
            {playlist.name} ({(playlist.items ?? playlist.tracks)?.total ?? 0} tracks)
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## Best Practices

### Token Management
- Store tokens securely (the API reads only the `Authorization: Bearer` header, not cookies)
- Call `POST /auth/spotify/refresh` to renew the JWT before it expires
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
- Do not keep the JWT in `localStorage` or `sessionStorage`. Any script on the page can read them. See [Step 3](#step-3-use-jwt-token) for safer storage.
- Save the `state` from `POST /auth/spotify/login` and reject a callback whose `state` does not match
- Never log tokens or commit them to source
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
        items: { total: 25 },
        owner: { id: 'user-123', display_name: 'Test User' }
      },
      {
        id: 'mock-playlist-2',
        name: 'Mock Playlist 2',
        items: { total: 50 },
        owner: { id: 'user-123', display_name: 'Test User' }
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

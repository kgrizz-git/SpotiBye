# Authentication Flow Documentation

This document describes the complete authentication flow for the SpotiBye Backend API.

## Overview

The SpotiBye backend uses a two-layer authentication system:
1. **Spotify OAuth**: For accessing Spotify's API
2. **JWT Tokens**: For authenticating with our backend API

## Flow Diagram

```
User → Frontend → Backend API → Spotify → Backend API → Frontend → User
```

## Step-by-Step Authentication Flow

### 1. Initiate OAuth Flow

**Endpoint**: `GET /auth/login`

**Frontend Implementation**:
```javascript
// Redirect user to Spotify OAuth
window.location.href = 'http://localhost:8000/auth/login';
```

**Backend Process**:
1. Generate available port for callback (8080-8084)
2. Create Spotify OAuth URL with proper scopes
3. Redirect user to Spotify authorization page

### 2. User Authorizes Application

**User Action**: User clicks "Agree" on Spotify's authorization page

**Spotify Response**: Redirects to callback URL with authorization code
```
http://127.0.0.1:8080/callback?code=AQD...&state=...
```

### 3. Exchange Code for Tokens

**Endpoint**: `GET /auth/callback`

**Backend Process**:
1. Extract authorization code from callback
2. Exchange code with Spotify for access token and refresh token
3. Get user profile information from Spotify
4. Create JWT tokens for our API
5. Return tokens to user (via HTML response)

### 4. Store JWT Tokens

**Frontend Implementation**:
```javascript
// Store tokens securely
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);

// Set up automatic token refresh
setInterval(refreshToken, 25 * 60 * 1000); // Refresh every 25 minutes
```

### 5. Make Authenticated API Calls

**Frontend Implementation**:
```javascript
async function apiCall(endpoint, options = {}) {
    const token = localStorage.getItem('access_token');

    const response = await fetch(`http://localhost:8000${endpoint}`, {
        ...options,
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
            ...options.headers
        }
    });

    if (response.status === 401) {
        // Token expired, try refresh
        await refreshToken();
        // Retry with new token
        return apiCall(endpoint, options);
    }

    return response.json();
}
```

### 6. Token Refresh Flow

**Endpoint**: `POST /auth/refresh`

**Frontend Implementation**:
```javascript
async function refreshToken() {
    const refreshToken = localStorage.getItem('refresh_token');

    const response = await fetch('http://localhost:8000/auth/refresh', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ refresh_token: refreshToken })
    });

    if (response.ok) {
        const { access_token } = await response.json();
        localStorage.setItem('access_token', access_token);
    } else {
        // Refresh failed, redirect to login
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
    }
}
```

### 7. Logout Flow

**Endpoint**: `POST /auth/logout`

**Frontend Implementation**:
```javascript
async function logout() {
    const token = localStorage.getItem('access_token');

    await fetch('http://localhost:8000/auth/logout', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });

    // Clear local storage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');

    // Redirect to login
    window.location.href = '/login';
}
```

## Security Considerations

### Token Storage
- **Access Token**: Store in memory or localStorage (short-lived: 30 minutes)
- **Refresh Token**: Store in httpOnly cookie or secure storage (long-lived: 30 days)

### Token Validation
- Always validate tokens on the server side
- Check token expiration before each API call
- Implement automatic token refresh

### HTTPS Requirements
- **Production**: Always use HTTPS
- **Development**: HTTP is acceptable for local testing
- **Token Transmission**: Always use secure headers

### Scope Management
The following Spotify scopes are requested:
- `playlist-read-private` - Read user's private playlists
- `playlist-read-collaborative` - Read collaborative playlists
- `user-library-read` - Read user's saved tracks
- `user-read-email` - Read user's email
- `user-read-private` - Read user's private details

## Error Handling

### Common Authentication Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Invalid/expired token | Refresh token or re-authenticate |
| 403 Forbidden | Insufficient permissions | Check OAuth scopes |
| 429 Too Many Requests | Rate limit exceeded | Implement exponential backoff |
| 500 Server Error | Backend issue | Retry with exponential backoff |

### Error Response Format
```json
{
  "detail": "Authentication failed: Invalid token"
}
```

## Implementation Examples

### React Hook for Authentication

```javascript
import { useState, useEffect } from 'react';

function useAuth() {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = localStorage.getItem('access_token');

        if (token) {
            verifyToken(token).then(userData => {
                setUser(userData);
                setLoading(false);
            }).catch(() => {
                // Token invalid, clear and redirect
                logout();
            });
        } else {
            setLoading(false);
        }
    }, []);

    const login = () => {
        window.location.href = 'http://localhost:8000/auth/login';
    };

    const logout = () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setUser(null);
    };

    return { user, loading, login, logout };
}
```

### Axios Interceptor

```javascript
import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:8000/api'
});

// Request interceptor - add auth token
api.interceptors.request.use(config => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Response interceptor - handle token refresh
api.interceptors.response.use(
    response => response,
    async error => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            try {
                await refreshToken();
                const newToken = localStorage.getItem('access_token');
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
                return api(originalRequest);
            } catch (refreshError) {
                logout();
                return Promise.reject(refreshError);
            }
        }

        return Promise.reject(error);
    }
);
```

## Testing Authentication

### Unit Tests

```python
def test_jwt_token_creation():
    data = {"sub": "test_user", "username": "testuser"}
    token = create_access_token(data)

    payload = verify_token(token)
    assert payload["sub"] == "test_user"
    assert payload["username"] == "testuser"

def test_token_refresh():
    refresh_token = create_refresh_token("test_user")
    user_id = verify_refresh_token(refresh_token)
    assert user_id == "test_user"
```

### Integration Tests

```python
def test_oauth_flow():
    # Test login redirect
    response = client.get("/auth/login")
    assert response.status_code == 302

    # Test callback with code (mock)
    with patch('spotipy.SpotifyOAuth') as mock_oauth:
        mock_oauth.return_value.get_access_token.return_value = {
            'access_token': 'test_token',
            'refresh_token': 'test_refresh'
        }

        response = client.get("/auth/callback?code=test_code")
        assert response.status_code == 200
```

## Production Considerations

### Environment Variables
```bash
# Required
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SECRET_KEY=your_jwt_secret_key

# Optional
SPOTIPY_REDIRECT_URI=https://yourdomain.com/auth/callback
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALLOWED_ORIGINS=https://yourdomain.com
```

### Rate Limiting
- Implement per-user rate limiting
- Use Redis or similar for distributed rate limiting
- Consider API keys for high-volume users

### Monitoring
- Track authentication success/failure rates
- Monitor token refresh patterns
- Alert on unusual authentication activity

## Troubleshooting

### Common Issues

1. **"Invalid redirect URI"**
   - Check Spotify app dashboard for allowed redirect URIs
   - Ensure port matches (8080-8084 for development)

2. **"Token expired"**
   - Implement automatic token refresh
   - Check token expiration time

3. **"CORS errors"**
   - Verify ALLOWED_ORIGINS configuration
   - Check frontend is making requests to correct domain

4. **"Scope insufficient"**
   - Verify all required scopes are requested
   - Check user has granted necessary permissions

### Debug Tools

```bash
# Check token contents
echo "YOUR_JWT_TOKEN" | cut -d'.' -f2 | base64 -d | jq .

# Test API with curl
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/auth/verify

# Check Spotify token
curl -H "Authorization: Bearer SPOTIFY_TOKEN" https://api.spotify.com/v1/me
```

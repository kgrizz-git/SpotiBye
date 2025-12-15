# Authentication Flow Guide for Frontend Developers

This guide provides detailed instructions for implementing the SpotiBye authentication flow in frontend applications. The authentication uses Spotify OAuth 2.0 with JWT tokens for session management.

## Overview

The authentication flow consists of three main steps:
1. **Initiate OAuth** - Redirect user to Spotify for authorization
2. **Handle Callback** - Exchange authorization code for JWT tokens
3. **Maintain Session** - Use JWT token for authenticated requests

## Prerequisites

Before implementing authentication, ensure you have:
- Registered your application with Spotify Developer Dashboard
- Configured redirect URIs in Spotify app settings
- Access to the SpotiBye API endpoints
- Understanding of OAuth 2.0 and JWT concepts

## Step 1: Initiate OAuth Flow

### API Endpoint
```
POST /auth/spotify/login
```

### Request Format
```javascript
const initiateAuth = async (redirectUri) => {
  try {
    const response = await fetch('https://spotibye-api.workers.dev/auth/spotify/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        redirect_uri: redirectUri,
        state: generateSecureState()
      })
    });

    if (!response.ok) {
      throw new Error(`Authentication initiation failed: ${response.status}`);
    }

    const data = await response.json();
    return data.data;
  } catch (error) {
    console.error('Auth initiation error:', error);
    throw error;
  }
};
```

### Parameters
- `redirect_uri` (required): URL where Spotify will redirect after authorization
- `state` (optional): CSRF protection token (recommended)

### Response
```json
{
  "data": {
    "auth_url": "https://accounts.spotify.com/authorize?response_type=ilateral=code&Arr=client_id.
    "yez=client_iduts=client Sub=client_id&redirect_uri=...&state=...",
    "state": "random-state-string"
  }
}
```

### Implementation Example
```javascript
// Generate secure state token
function generateSecureState() {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

// Store state in session storage for verification
function storeState(state) {
  sessionStorage.setItem('spotify_auth_state', state);
}

// Verify state on callback
function verifyState(receivedState) {
  const storedState = sessionStorage.getItem('spotify_auth_state');
  sessionStorage.removeItem('spotify_auth_state');
  return storedState === receivedState;
}

// Complete login function
async function login() {
  const redirectUri = `${window.location.origin}/callback`;
  const state = generateSecureState();
  
  storeState(state);
  
  try {
    const authData = await initiateAuth(redirectUri);
    // Redirect user to Spotify
    window.location.href = authData.auth_url;
  } catch (error) {
    // Handle error (show user message)
    showError('Failed to start authentication. Please try again.');
  }
}
```

## Step 2: Handle OAuth Callback

### Callback URL Setup
Configure your Spotify app with the callback URL:
```
https://your-app-domain.com/callback
```

### Extract Callback Parameters
```javascript
// In your callback page/component
function handleCallback() {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  const state = urlParams.get('state');
  const error = urlParams.get('error');

  // Handle OAuth error
  if (error) {
    console.error('OAuth error:', error);
    // Redirect to login with error message
    window.location.href = '/login?error=' + encodeURIComponent(error);
    return;
  }

  // Verify state for CSRF protection
  if (!verifyState(state)) {
    console.error('State verification failed');
    window.location.href = '/login?error=state_mismatch';
    return;
  }

  // Exchange code for tokens
  exchangeCodeForTokens(code);
}
```

### Exchange Code for Tokens
```javascript
async function exchangeCodeForTokens(code) {
  try {
    const response = await fetch(
      `https://spotibye-api.workers.dev/auth/spotify/callback?code=${code}&state=${state}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Token exchange failed: ${response.status}`);
    }

    const data = await response.json();
    const { access_token, refresh_token, expires_in, user } = data.data;
    
    // Store authentication data
    storeAuthData(access_token, refresh_token, expires_in, user);
    
    // Redirect to authenticated area
    window.location.href = '/dashboard';
  } catch (error) {
    console.error('Token exchange error:', error);
    window.location.href = '/login?error=token_exchange_failed';
  }
}
```

### Response Format
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
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

## Step 3: Token Management

### Secure Token Storage
```javascript
// Recommended: Use httpOnly cookies for production
// For development: localStorage with caution

function storeAuthData(accessToken, refreshToken, expiresIn, user) {
  const expiresAt = Date.now() + (expiresIn * 1000);
  
  const authData = {
    accessToken,
    refreshToken,
    expiresAt,
    user
  };
  
  // Store in localStorage (development only)
  localStorage.setItem('spotibye_auth', JSON.stringify(authData));
  
  // Set up token refresh timer
  setupTokenRefresh(expiresIn);
}

function getAuthData() {
  const stored = localStorage.getItem('spotibye_auth');
  if (!stored) return null;
  
  const authData = JSON.parse(stored);
  
  // Check if token is expired
  if (Date.now() > authData.expiresAt) {
    clearAuthData();
    return null;
  }
  
  return authData;
}

function clearAuthData() {
  localStorage.removeItem('spotibye_auth');
  // Clear any refresh timers
  if (window.refreshTimer) {
    clearTimeout(window.refreshTimer);
  }
}
```

### Token Refresh
```javascript
async function refreshToken() {
  const authData = getAuthData();
  if (!authData?.refreshToken) {
    throw new Error('No refresh token available');
  }

  try {
    const response = await fetch('https://spotibye-api.workers.dev/auth/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        refresh_token: authData.refreshToken
      })
    });

    if (!response.ok) {
      throw new Error(`Token refresh failed: ${response.status}`);
    }

    const data = await response.json();
    const { access_token, expires_in } = data.data;
    
    // Update stored auth data
    authData.accessToken = access_token;
    authData.expiresAt = Date.now() + (expires_in * 1000);
    localStorage.setItem('spotibye_auth', JSON.stringify(authData));
    
    return access_token;
  } catch (error) {
    console.error('Token refresh error:', error);
    // Clear auth data and redirect to login
    clearAuthData();
    window.location.href = '/login?error=session_expired';
    throw error;
  }
}

function setupTokenRefresh(expiresIn) {
  // Refresh 5 minutes before expiration
  const refreshTime = (expiresIn - 300) * 1000;
  
  window.refreshTimer = setTimeout(() => {
    refreshToken().catch(console.error);
  }, refreshTime);
}
```

## Step 4: Authenticated API Requests

### Request Interceptor
```javascript
// Create API client with authentication
class SpotiByeAPI {
  constructor(baseURL = 'https://spotibye-api.workers.dev') {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const authData = getAuthData();
    
    if (!authData) {
      throw new Error('Not authenticated');
    }

    // Check if token needs refresh
    if (Date.now() > authData.expiresAt - 60000) { // 1 minute buffer
      await refreshToken();
    }

    const config = {
      ...options,
      headers: {
        'Authorization': `Bearer ${authData.accessToken}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    };

    const response = await fetch(`${this.baseURL}${endpoint}`, config);

    if (response.status === 401) {
      // Token might be expired, try refresh
      try {
        await refreshToken();
        // Retry request with new token
        const newAuthData = getAuthData();
        config.headers.Authorization = `Bearer ${newAuthData.accessToken}`;
        return fetch(`${this.baseURL}${endpoint}`, config);
      } catch (refreshError) {
        // Refresh failed, clear auth and redirect
        clearAuthData();
        window.location.href = '/login?error=session_expired';
        throw refreshError;
      }
    }

    return response;
  }

  // Example authenticated methods
  async getPlaylists() {
    const response = await this.request('/spotify/playlists');
    return response.json();
  }

  async analyzePlaylist(playlistId, options = {}) {
    const response = await this.request(`/analysis/playlist/${playlistId}`, {
      method: 'POST',
      body: JSON.stringify(options)
    });
    return response.json();
  }
}
```

## React Implementation

### Custom Hook
```javascript
import { useState, useEffect, useCallback } from 'react';

function useAuthentication() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check authentication status on mount
  useEffect(() => {
    const authData = getAuthData();
    if (authData) {
      setUser(authData.user);
    }
    setLoading(false);
  }, []);

  const login = useCallback(async () => {
    try {
      await initiateLogin();
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const logout = useCallback(() => {
    clearAuthData();
    setUser(null);
    window.location.href = '/login';
  }, []);

  const handleCallback = useCallback(async (code, state) => {
    try {
      await exchangeCodeForTokens(code, state);
      const authData = getAuthData();
      setUser(authData.user);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  return {
    user,
    loading,
    error,
    isAuthenticated: !!user,
    login,
    logout,
    handleCallback
  };
}

// Usage in component
function AuthenticatedApp() {
  const { user, isAuthenticated, loading, login, logout } = useAuthentication();

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <LoginPage onLogin={login} />;
  }

  return (
    <div>
      <header>
        <h1>Welcome, {user.display_name}!</h1>
        <button onClick={logout}>Logout</button>
      </header>
      <main>
        {/* Your authenticated content */}
      </main>
    </div>
  );
}
```

### Callback Component
```javascript
function CallbackPage() {
  const { handleCallback } = useAuthentication();
  const [status, setStatus] = useState('processing');

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');
    const error = urlParams.get('error');

    if (error) {
      setStatus('error');
      setTimeout(() => {
        window.location.href = '/login?error=' + encodeURIComponent(error);
      }, 3000);
      return;
    }

    if (code && state) {
      handleCallback(code, state)
        .then(() => setStatus('success'))
        .catch(() => setStatus('error'));
    } else {
      setStatus('error');
    }
  }, [handleCallback]);

  return (
    <div className="callback-container">
      {status === 'processing' && (
        <div>
          <h2>Authenticating...</h2>
          <p>Please wait while we complete your login.</p>
        </div>
      )}
      {status === 'success' && (
        <div>
          <h2>Login Successful!</h2>
          <p>Redirecting you to your dashboard...</p>
        </div>
      )}
      {status === 'error' && (
        <div>
          <h2>Login Failed</h2>
          <p>There was an error during authentication. Redirecting...</p>
        </div>
      )}
    </div>
  );
}
```

## Security Best Practices

### State Management
- Always use cryptographically secure random state tokens
- Store state in session storage (cleared on tab close)
- Verify state on callback to prevent CSRF attacks

### Token Storage
- **Production**: Use httpOnly, secure cookies
- **Development**: localStorage with caution
- Never store tokens in URL or localStorage without encryption

### Error Handling
- Never expose detailed error messages to users
- Log errors securely for debugging
- Implement graceful degradation

### Token Refresh
- Refresh tokens before expiration
- Handle refresh failures gracefully
- Clear auth data on refresh failure

### Redirect Handling
- Validate redirect URIs in Spotify app settings
- Use HTTPS for all redirect URIs
- Limit redirect URIs to your domain

## Common Issues and Solutions

### State Mismatch Error
**Problem**: State verification fails
**Solution**: Ensure state is stored in session storage and not modified

### Token Expired
**Problem**: API calls return 401 errors
**Solution**: Implement automatic token refresh before making requests

### CORS Issues
**Problem**: Cross-origin requests blocked
**Solution**: Ensure API allows your domain in CORS headers

### Redirect Loop
**Problem**: Continuous redirect between login and callback
**Solution**: Check authentication status before redirecting

### Safari/Privacy Issues
**Problem**: Third-party cookies blocked in Safari
**Solution**: Use localStorage or implement token-based auth

## Testing Authentication

### Mock Authentication
```javascript
// For testing without Spotify
class MockAuthAPI extends SpotiByeAPI {
  async initiateAuth() {
    return {
      auth_url: 'http://localhost:3000/mock-auth',
      state: 'mock-state'
    };
  }

  async exchangeCodeForTokens(code, state) {
    return {
      access_token: 'mock-token',
      refresh_token: 'mock-refresh',
      expires_in: 3600,
      user: {
        id: 'mock-user',
        display_name: 'Test User',
        email: 'test@example.com'
      }
    };
  }
}
```

### Integration Testing
```javascript
// Test authentication flow
describe('Authentication Flow', () => {
  test('should initiate OAuth flow', async () => {
    const authData = await initiateAuth('http://localhost:3000/callback');
    expect(authData.auth_url).toContain('accounts.spotify.com');
    expect(authData.state).toBeDefined();
  });

  test('should handle callback correctly', async () => {
    const mockCode = 'test-auth-code';
    const mockState = 'test-state';
    
    const userData = await exchangeCodeForTokens(mockCode, mockState);
    expect(userData.access_token).toBeDefined();
    expect(userData.user).toBeDefined();
  });
});
```

## Production Considerations

### Environment Configuration
```javascript
const config = {
  development: {
    apiURL: 'http://localhost:8787',
    redirectURI: 'http://localhost:3000/callback'
  },
  staging: {
    apiURL: 'https://spotibye-api-dev.workers.dev',
    redirectURI: 'https://staging.spotibye.com/callback'
  },
  production: {
    apiURL: 'https://spotibye-api.workers.dev',
    redirectURI: 'https://app.spotibye.com/callback'
  }
};

const currentConfig = config[process.env.NODE_ENV] || config.development;
```

### Monitoring and Analytics
```javascript
// Track authentication events
function trackAuthEvent(event, properties = {}) {
  if (typeof gtag !== 'undefined') {
    gtag('event', event, {
      category: 'Authentication',
      ...properties
    });
  }
}

// Usage in auth flow
trackAuthEvent('login_initiated');
trackAuthEvent('login_completed', { user_id: user.id });
trackAuthEvent('login_failed', { error: error.message });
```

This comprehensive guide provides everything frontend developers need to implement secure, robust authentication with the SpotiBye API.

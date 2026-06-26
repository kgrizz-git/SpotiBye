# SpotiBye Authentication Flow

## Overview

SpotiBye uses OAuth 2.0 to authenticate with Spotify through our secure cloud backend. Your Spotify credentials are never stored or transmitted to our servers.

## How It Works

### Step 1: Initiate Login
1. Click "Login with Spotify" in SpotiBye
2. App requests authentication URL from backend
3. Backend generates secure Spotify authorization URL

### Step 2: Spotify Authorization
1. Your browser opens to Spotify's authorization page
2. You log in with your Spotify credentials
3. You approve SpotiBye's requested permissions

### Step 3: Callback Handling
1. Spotify redirects back to our backend with authorization code
2. Backend exchanges code for access token
3. Backend creates JWT token for your session
4. Token is returned to SpotiBye application

### Step 4: Authenticated Session
1. SpotiBye stores JWT token securely
2. All API calls include this token
3. Backend validates token for each request
4. Token automatically refreshes when needed

## Security Features

- **No Credential Storage**: Your Spotify password never leaves your browser
- **Token Security**: JWT tokens are cryptographically signed
- **Limited Permissions**: Only requests necessary playlist access
- **Auto-Expiration**: Tokens expire automatically for security
- **Secure Transmission**: All communication uses HTTPS

## Session Management

### Login Duration
- Sessions remain active for 1 hour of inactivity
- Tokens automatically refresh when used
- Manual logout available anytime

### Logout Process
1. Click "Logout" in SpotiBye
2. Local token is immediately deleted
3. Backend session is invalidated
4. Must login again to use app

## Troubleshooting

### Login Fails
- Check internet connection
- Ensure Spotify account is active
- Try clearing browser cache
- Restart SpotiBye application

### Session Expires
- Normal behavior after 1 hour inactivity
- Simply login again to continue
- Your data is preserved between sessions

### Permission Issues
- Ensure you approved all requested permissions
- Re-authorize if permissions were denied
- Contact support if issues persist

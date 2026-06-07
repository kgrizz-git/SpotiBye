# Spotify OAuth 2.0 PKCE Flow

## Overview
SpotiBye uses the OAuth 2.0 Authorization Code Flow with PKCE (Proof Key for Code Exchange) for Spotify authentication.

## Flow Steps

1. **Generate PKCE Code Verifier and Challenge**
   - Create a random code verifier (43-128 characters)
   - Generate code challenge by SHA256 hashing the verifier
   - Store verifier in session for later token exchange

2. **Redirect to Spotify Authorization**
   - Redirect user to `https://accounts.spotify.com/authorize`
   - Include: `client_id`, `response_type=code`, `redirect_uri`, `code_challenge`, `code_challenge_method=S256`

3. **User Authorizes**
   - User logs in and grants permissions
   - Spotify redirects back with `code` parameter

4. **Exchange Code for Tokens**
   - Backend receives authorization code
   - POST to `https://accounts.spotify.com/api/token`
   - Include: `grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`, `code_verifier`

5. **Store Tokens**
   - Backend stores access token and refresh token
   - Access token expires in 1 hour
   - Refresh token used to get new access tokens

## Key Implementation Details

- All token management happens in backend (`src/backend/services/auth.ts`)
- Frontend never sees access tokens
- Refresh tokens are stored securely in backend KV
- Token refresh happens automatically when access token expires

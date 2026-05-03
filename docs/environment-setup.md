# Environment Variables Setup Guide

This guide explains how to properly configure environment variables for the SpotiBye project.

## Quick Start

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file** with your actual values (never commit this file)

3. **Restart your application** to load the new environment variables

## Required Variables

### Spotify API Credentials

Get these from the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard):

```bash
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
```

**Steps:**
1. Go to Spotify Developer Dashboard
2. Create a new app or select existing one
3. Copy the Client ID and generate a Client Secret
4. Add your redirect URI (e.g., `http://localhost:8080/callback`)

### JWT Secret

Generate a secure random string for JWT signing:

```bash
# Generate a secure JWT secret
openssl rand -base64 32
```

```bash
JWT_SECRET=your_generated_secret_here_minimum_32_characters
```

## Optional Variables

### Backend URLs

Configure different backend environments:

```bash
# Development backend
SPOTIBYE_BACKEND_URL=https://your-dev-backend.workers.dev

# Production backend  
SPOTIBYE_PRODUCTION_BACKEND_URL=https://your-prod-backend.workers.dev

# Local development
SPOTIBYE_LOCALHOST_BACKEND_URL=http://localhost:8787
```

### Feature Flags

Control application behavior:

```bash
# Enable/disable features
SPOTIBYE_ENABLE_ANALYSIS=true
SPOTIBYE_ENABLE_EXPORT=true
SPOTIBYE_ENABLE_CACHING=true
SPOTIBYE_ENABLE_OFFLINE=false

# Debug mode
SPOTIBYE_DEBUG_NETWORK=false
SPOTIBYE_DEBUG_AUTH=false
```

### Performance Settings

Fine-tune application performance:

```bash
# Request handling
SPOTIBYE_BATCH_SIZE=50
SPOTIBYE_MAX_CONCURRENT=3
SPOTIBYE_MAX_RETRIES=3
SPOTIBYE_RETRY_BACKOFF=1.0

# Timeouts (seconds)
SPOTIBYE_API_TIMEOUT=30
SPOTIBYE_ANALYSIS_TIMEOUT=300
SPOTIBYE_OAUTH_TIMEOUT=300
```

## Environment-Specific Files

For different environments, you can create:

- `.env.development` - Development settings
- `.env.production` - Production settings  
- `.env.local` - Local overrides (gitignored)

The application will automatically load `.env` first, then environment-specific files.

## Security Best Practices

### ✅ Do

- Keep `.env` files out of version control
- Use strong, randomly generated secrets
- Rotate secrets periodically
- Use different secrets for different environments
- Limit access to production secrets

### ❌ Don't

- Commit `.env` files to git
- Share secrets via email, chat, or code comments
- Use weak or predictable secrets
- Reuse secrets across different applications
- Hard-code secrets in application code

## Loading Environment Variables

### Python (Frontend)

The frontend configuration automatically loads environment variables using `os.environ.get()`:

```python
# Example from src/frontend/config/backend_config.py
BACKEND_URL = os.environ.get("SPOTIBYE_BACKEND_URL", "https://default-url.com")
```

### Node.js/TypeScript (Backend)

The backend (Cloudflare Workers) accesses environment variables through the `Env` binding:

```typescript
// Example from src/backend/routes/auth.ts
const spotifyAuth = new SpotifyAuthService(c.env.SPOTIFY_CLIENT_ID, c.env.SPOTIFY_CLIENT_SECRET);
```

## Cloudflare Workers Configuration

For the backend, ensure your `wrangler.toml` includes the necessary environment variable bindings:

```toml
[env.production.vars]
SPOTIFY_CLIENT_ID = "your_production_client_id"
SPOTIFY_CLIENT_SECRET = "your_production_client_secret"
JWT_SECRET = "your_production_jwt_secret"

[env.development.vars]
SPOTIFY_CLIENT_ID = "your_dev_client_id"
SPOTIFY_CLIENT_SECRET = "your_dev_client_secret"
JWT_SECRET = "your_dev_jwt_secret"
```

## Troubleshooting

### Common Issues

1. **"Missing environment variable" error**
   - Ensure the variable is set in `.env`
   - Restart the application after changing `.env`

2. **Spotify OAuth errors**
   - Verify redirect URI matches in Spotify Dashboard
   - Check Client ID and Secret are correct

3. **JWT errors**
   - Ensure JWT_SECRET is at least 32 characters
   - Check for typos in the secret

### Debug Mode

Enable debug logging to troubleshoot:

```bash
SPOTIBYE_DEBUG_NETWORK=true
SPOTIBYE_DEBUG_AUTH=true
LOG_LEVEL=debug
```

## Template for New Variables

When adding new environment variables:

1. Add to `.env.example` with a descriptive comment
2. Update this documentation
3. Add loading code in appropriate config files
4. Test with different values

```bash
# New feature flag
NEW_FEATURE_ENABLED=false

# API configuration
NEW_API_TIMEOUT=30
```

## Support

If you encounter issues with environment variable setup:

1. Check this documentation first
2. Verify your `.env` file format (no spaces around `=`)
3. Ensure required variables are set
4. Check application logs for specific error messages

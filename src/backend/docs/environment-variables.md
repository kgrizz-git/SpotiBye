# Environment Variables Documentation

This document describes all environment variables and secrets required for the SpotiBye Cloudflare Workers backend.

## Overview

The SpotiBye backend uses environment variables for configuration, API keys, and secrets. These are managed through Cloudflare Workers' environment variable system.

## Environment Variables

### Core Configuration

#### `ENVIRONMENT`
- **Type**: String
- **Required**: Yes
- **Values**: `development`, `staging`, `production`
- **Description**: Current deployment environment
- **Example**: `ENVIRONMENT=production`
- **Notes**: Affects logging levels, error reporting, and feature flags

#### `JWT_SECRET`
- **Type**: String (Secret)
- **Required**: Yes
- **Description**: Secret key for JWT token signing and verification
- **Example**: `JWT_SECRET=your-super-secret-jwt-key-here`
- **Security**: Must be kept confidential, use a strong random string
- **Generation**: Use `openssl rand -base64 64` to generate a secure secret

### Spotify Integration

#### `SPOTIFY_CLIENT_ID`
- **Type**: String (Secret)
- **Required**: Yes
- **Description**: Spotify application client ID from Spotify Developer Dashboard
- **Example**: `SPOTIFY_CLIENT_ID=1234567890abcdef1234567890abcdef`
- **Source**: Spotify Developer Console → Your App → Client ID
- **Security**: Should be treated as sensitive information

#### `SPOTIFY_CLIENT_SECRET`
- **Type**: String (Secret)
- **Required**: Yes
- **Description**: Spotify application client secret from Spotify Developer Dashboard
- **Example**: `SPOTIFY_CLIENT_SECRET=[YOUR_SPOTIFY_CLIENT_SECRET]`
- **Source**: Spotify Developer Console → Your App → Client Secret
- **Security**: Must be kept confidential, never expose in client-side code

### External Services

#### `RECOCOBEATS_API_KEY`
- **Type**: String (Secret)
- **Required**: Optional
- **Description**: API key for ReccoBeats music analysis service
- **Example**: `RECOCOBEATS_API_KEY=rbc-1234567890abcdef`
- **Purpose**: Enhanced playlist analysis and recommendations
- **Notes**: Optional - if not provided, basic analysis features will still work

### KV Namespace Bindings

#### `CACHE_KV`
- **Type**: KV Namespace Binding
- **Required**: Yes
- **Description**: KV namespace for caching Spotify API responses and analysis results
- **Binding Name**: `CACHE_KV`
- **TTL**: Default 1 hour, configurable per cache entry
- **Usage**: Reduces API calls to Spotify, improves response times
- **Setup**: Create KV namespace in Cloudflare Dashboard and bind to worker

#### `SESSIONS_KV`
- **Type**: KV Namespace Binding
- **Required**: Yes
- **Description**: KV namespace for storing user sessions and OAuth state
- **Binding Name**: `SESSIONS_KV`
- **TTL**: Default 24 hours for sessions, 10 minutes for OAuth state
- **Usage**: Manages user authentication state and OAuth flow
- **Setup**: Create KV namespace in Cloudflare Dashboard and bind to worker

## Configuration Files

### `wrangler.toml`
The main configuration file for Cloudflare Workers:

```toml
name = "spotibye-api"
main = "src/index.ts"
compatibility_date = "2023-12-01"

[env.production]
name = "spotibye-api"
vars = { ENVIRONMENT = "production" }

[env.development]
name = "spotibye-api-dev"
vars = { ENVIRONMENT = "development" }

[[kv_namespaces]]
binding = "CACHE_KV"
id = "your-cache-kv-namespace-id"
preview_id = "your-cache-kv-preview-id"

[[kv_namespaces]]
binding = "SESSIONS_KV"
id = "your-sessions-kv-namespace-id"
preview_id = "your-sessions-kv-preview-id"

[secrets]
SPOTIFY_CLIENT_ID = ""
SPOTIFY_CLIENT_SECRET = ""
JWT_SECRET = ""
RECOCOBEATS_API_KEY = ""
```

## Environment Setup

### Local Development

1. **Create `.dev.vars` file** (for local development):
   ```bash
   # .dev.vars
   ENVIRONMENT=development
   SPOTIFY_CLIENT_ID=your-spotify-client-id
   SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
   JWT_SECRET=your-jwt-secret
   RECOCOBEATS_API_KEY=your-reccobeats-api-key
   ```

2. **Set up KV namespaces**:
   ```bash
   # Create KV namespaces
   wrangler kv:namespace create "CACHE_KV"
   wrangler kv:namespace create "SESSIONS_KV"

   # Create preview namespaces
   wrangler kv:namespace create "CACHE_KV" --preview
   wrangler kv:namespace create "SESSIONS_KV" --preview
   ```

3. **Update `wrangler.toml`** with the namespace IDs from the commands above

### Production Deployment

1. **Set secrets via Wrangler CLI**:
   ```bash
   wrangler secret put SPOTIFY_CLIENT_ID
   wrangler secret put SPOTIFY_CLIENT_SECRET
   wrangler secret put JWT_SECRET
   wrangler secret put RECOCOBEATS_API_KEY
   ```

2. **Set environment variables**:
   ```bash
   wrangler secret put ENVIRONMENT
   # Enter "production" when prompted
   ```

3. **Deploy with environment**:
   ```bash
   wrangler deploy --env production
   ```

### Staging Deployment

```bash
wrangler deploy --env staging
```

## Security Considerations

### Secret Management
- **Never commit secrets to version control**
- **Use Wrangler secrets for production**
- **Rotate secrets regularly**
- **Use different secrets for each environment**

### Environment Isolation
- **Separate KV namespaces per environment**
- **Different Spotify apps per environment**
- **Unique JWT secrets per environment**

### Access Control
- **Limit access to Spotify Developer Dashboard**
- **Restrict Wrangler CLI access to authorized team members**
- **Monitor secret usage and rotation**

## Variable Validation

### Required Variables Check
The application validates required variables on startup:

```typescript
// Required environment variables
const requiredVars = [
  'ENVIRONMENT',
  'SPOTIFY_CLIENT_ID',
  'SPOTIFY_CLIENT_SECRET',
  'JWT_SECRET'
];

// Missing variables will cause startup failure
```

### Variable Format Validation
- `ENVIRONMENT`: Must be one of `development`, `staging`, `production`
- `JWT_SECRET`: Must be at least 32 characters long
- `SPOTIFY_CLIENT_ID`: Must match Spotify client ID format
- `SPOTIFY_CLIENT_SECRET`: Must be non-empty string

## Troubleshooting

### Common Issues

#### Missing Environment Variables
- **Error**: `Missing required environment variable: SPOTIFY_CLIENT_ID`
- **Solution**: Set the missing variable using `wrangler secret put`

#### Invalid JWT Secret
- **Error**: `JWT_SECRET must be at least 32 characters`
- **Solution**: Generate a new secret with `openssl rand -base64 64`

#### KV Namespace Not Bound
- **Error**: `KV binding not found: CACHE_KV`
- **Solution**: Create and bind KV namespace in `wrangler.toml`

#### Spotify API Credentials Invalid
- **Error**: `Invalid Spotify client credentials`
- **Solution**: Verify Spotify app credentials and regenerate if necessary

### Debug Mode
Enable debug logging by setting:
```bash
ENVIRONMENT=development
```

This will:
- Log all environment variable loading
- Show KV namespace binding status
- Display Spotify API authentication status
- Enable verbose error messages

## Best Practices

### Development
1. **Use `.dev.vars` for local development**
2. **Never commit secrets to Git**
3. **Use environment-specific Spotify apps**
4. **Test with different environment configurations**

### Production
1. **Use Wrangler secrets for all sensitive data**
2. **Rotate secrets quarterly**
3. **Monitor environment variable usage**
4. **Have backup secrets ready**

### Monitoring
1. **Track secret rotation dates**
2. **Monitor Spotify API quota usage**
3. **Watch KV namespace storage limits**
4. **Log environment variable access patterns**

## Migration Guide

### Updating Environment Variables
1. **Test changes in development first**
2. **Update staging environment**
3. **Plan production deployment during low-traffic periods**
4. **Have rollback plan ready**

### Adding New Variables
1. **Update type definitions in `types/env.ts`**
2. **Add validation logic**
3. **Update documentation**
4. **Test in all environments**

### Removing Variables
1. **Check for usage in codebase**
2. **Update dependent services**
3. **Clean up from all environments**
4. **Update documentation**

## Support

For environment variable issues:
1. Check this documentation first
2. Verify variable formats and values
3. Test with development environment
4. Contact the development team for assistance

## Related Documentation

- [Cloudflare Workers Environment Variables](https://developers.cloudflare.com/workers/wrangler/configuration/#environment-variables)
- [Cloudflare Workers Secrets](https://developers.cloudflare.com/workers/wrangler/configuration/#secrets)
- [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- [KV Namespaces Documentation](https://developers.cloudflare.com/workers/learning/how-kv-works/)

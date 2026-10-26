# Environment Variables Documentation

> **Configuration source and precedence:** Read the canonical
> [`dev-docs/guides/environment-setup.md`](../../../dev-docs/guides/environment-setup.md)
> before configuring this Worker. In particular, keep sensitive values out of
> `wrangler.toml`; use `.dev.vars` locally and Cloudflare Worker secrets when deployed.

This document describes all environment variables and secrets required for the SpotiBye Cloudflare Workers backend.

## Overview

The SpotiBye backend uses environment variables for configuration, API keys, and secrets. These are managed through Cloudflare Workers' environment variable system.

## Environment Variables

### Core Configuration

#### `ENVIRONMENT`
- **Type**: String
- **Required**: Yes
- **Values**: `development`, `production` (set in `wrangler.toml` `[env.<name>.vars]`)
- **Description**: Current deployment environment
- **Example**: `ENVIRONMENT=production`
- **Notes**: Reported in the `/health` response. It does not change logging or behavior.

#### `ALLOWED_REDIRECT_URIS`
- **Type**: String (comma-separated)
- **Required**: Yes (may be empty, but then every login is rejected)
- **Description**: Exact-match allowlist of `redirect_uri` values accepted by `POST /auth/spotify/login`
- **Example**: `ALLOWED_REDIRECT_URIS=http://localhost:3000,http://127.0.0.1:8080/callback`
- **Notes**: Set per environment in `wrangler.toml`. A URI not in the list returns `400 DISALLOWED_REDIRECT_URI`.

#### `ANALYSIS_RESULTS_TTL_SECONDS`
- **Type**: String (positive integer)
- **Required**: No
- **Description**: TTL for cached analysis results
- **Default**: `86400` (from `utils/constants.ts`) when unset or not a positive number

#### `RELEASE_SHA`, `RELEASE_VERSION`, `DEPLOYED_AT`
- **Type**: String
- **Required**: No
- **Description**: Deployment metadata injected by `scripts/deploy-with-metadata.sh` and the deploy workflows
- **Notes**: Reported in `/health`. Each falls back to `unknown` when unset.

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

### KV Namespace Bindings

#### `CACHE_KV`
- **Type**: KV Namespace Binding
- **Required**: Yes
- **Description**: KV namespace for cached Spotify responses, export jobs and files, analysis results, and OAuth state
- **Binding Name**: `CACHE_KV`
- **TTL**: Set per entry. Examples: playlists 5 minutes, export data 1 hour, analysis results 24 hours, OAuth state 10 minutes.
- **Usage**: Reduces API calls to Spotify, improves response times
- **Setup**: Create KV namespace in Cloudflare Dashboard and bind to worker

#### `SESSIONS_KV`
- **Type**: KV Namespace Binding
- **Required**: Yes
- **Description**: KV namespace for user sessions (Spotify tokens keyed by session ID)
- **Binding Name**: `SESSIONS_KV`
- **TTL**: 30 days for sessions. A 60-second marker blocks repeated failed token refreshes.
- **Usage**: Manages user authentication state
- **Setup**: Create KV namespace in Cloudflare Dashboard and bind to worker

### Other Bindings

- `ANALYSIS_STATUS`: Durable Object namespace (`AnalysisStatusObject`) that tracks analysis job status.
- `ANALYSIS_QUEUE`: Queue producer for analysis jobs. The Worker also consumes the queue (`spotibye-analysis-dev` in development, `spotibye-analysis` in production).

## Configuration Files

### `wrangler.toml`
The main configuration file for Cloudflare Workers:

The file defines `development` and `production` environments. Wrangler names
the Workers `spotibye-backend-development` and `spotibye-backend-production`.
See `src/backend/wrangler.toml` for the bindings. Do not put secrets in that
file. Set them with `wrangler secret put`.

## Environment Setup

### Local Development

1. **Create `.dev.vars` file** (for local development):
   ```bash
   # .dev.vars
   ENVIRONMENT=development
   SPOTIFY_CLIENT_ID=your-spotify-client-id
   SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
   JWT_SECRET=your-jwt-secret
   ```

2. **Set up KV namespaces**:
   ```bash
   # Create KV namespaces
   npx wrangler kv namespace create "CACHE_KV"
   npx wrangler kv namespace create "SESSIONS_KV"

   # Create preview namespaces
   npx wrangler kv namespace create "CACHE_KV" --preview
   npx wrangler kv namespace create "SESSIONS_KV" --preview
   ```

3. **Update `wrangler.toml`** with the namespace IDs from the commands above

### Production Deployment

1. **Set secrets via Wrangler CLI**:
   ```bash
   npx wrangler secret put SPOTIFY_CLIENT_ID --env production
   npx wrangler secret put SPOTIFY_CLIENT_SECRET --env production
   npx wrangler secret put JWT_SECRET --env production
   ```

2. **Set non-secret environment variables** in `wrangler.toml` under the
   appropriate `[env.<name>.vars]` section. This project already defines
   `ENVIRONMENT` and `ALLOWED_REDIRECT_URIS` there.

3. **Deploy with environment**:
   ```bash
   npm run deploy:prod   # or deploy:dev
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

`middleware/env.ts` validates string bindings once per isolate, on the first
request, using `validation/schemas/env.ts`:

- `ENVIRONMENT`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `JWT_SECRET` must be non-empty strings.
- `ALLOWED_REDIRECT_URIS` must be a string. An empty string is accepted.
- No format or length rules are enforced. Use a long random `JWT_SECRET` anyway.

KV, Durable Object, and Queue bindings are not checked.

## Troubleshooting

### Common Issues

#### Missing Environment Variables
- **Symptom**: Every request, including `/health`, returns `500` with code `INTERNAL_ERROR`
- **Log**: `Invalid Worker environment bindings: JWT_SECRET: ...` in `wrangler tail --env <env>`
- **Solution**: Set the missing variable using `wrangler secret put <NAME> --env <environment>`

#### KV Namespace Not Bound
- **Symptom**: Routes that touch KV fail with `500`
- **Solution**: Check the `kv_namespaces` entries for that environment in `wrangler.toml`

#### Spotify API Credentials Invalid
- **Symptom**: `/auth/spotify/callback` returns `OAUTH_CALLBACK_FAILED` or `OAUTH_BAD_REQUEST`
- **Log**: `Failed to exchange code for tokens: ...`
- **Solution**: Verify Spotify app credentials and regenerate if necessary

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

## Migration Guide

### Updating Environment Variables
1. **Test changes in development first**
2. **Plan production deployment during low-traffic periods**
3. **Have rollback plan ready**

### Adding New Variables
1. **Update type definitions in `types/env.ts`**
2. **Add validation logic** in `validation/schemas/env.ts`
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

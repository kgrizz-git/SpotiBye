# Deployment Configuration

This guide covers deployment configuration for the SpotiBye Cloudflare Workers backend across different environments.

## Environments

### Development
- **URL**: `https://spotibye-api-dev.workers.dev`
- **Purpose**: Development and testing
- **Features**: Debug logging, relaxed rate limits

### Staging
- **URL**: `https://spotibye-api-staging.workers.dev`
- **Purpose**: Pre-production testing
- **Features**: Production-like configuration

### Production
- **URL**: `https://spotibye-api.workers.dev`
- **Purpose**: Live production traffic
- **Features**: Full security, monitoring, logging

## Wrangler Configuration

### `wrangler.toml`
```toml
name = "spotibye-api"
main = "src/index.ts"
compatibility_date = "2023-12-01"

# Development environment
[env.development]
name = "spotibye-api-dev"
vars = { ENVIRONMENT = "development" }

# Staging environment
[env.staging]
name = "spotibye-api-staging"
vars = { ENVIRONMENT = "staging" }

# Production environment
[env.production]
name = "spotibye-api"
vars = { ENVIRONMENT = "production" }

# KV namespaces
[[kv_namespaces]]
binding = "CACHE_KV"
id = "your-cache-kv-id"
preview_id = "your-cache-kv-preview-id"

[[kv_namespaces]]
binding = "SESSIONS_KV"
id = "your-sessions-kv-id"
preview_id = "your-sessions-kv-preview-id"
```

## Environment Variables

### Required Secrets
```bash
# Set secrets for production
wrangler secret put SPOTIFY_CLIENT_ID --env production
wrangler secret put SPOTIFY_CLIENT_SECRET --env production
wrangler secret put JWT_SECRET --env production

# Set secrets for staging
wrangler secret put SPOTIFY_CLIENT_ID --env staging
wrangler secret put SPOTIFY_CLIENT_SECRET --env staging
wrangler secret put JWT_SECRET --env staging
```

### Local Development
Create `.dev.vars` file:
```bash
ENVIRONMENT=development
SPOTIFY_CLIENT_ID=your-dev-client-id
SPOTIFY_CLIENT_SECRET=your-dev-client-secret
JWT_SECRET=your-dev-jwt-secret
```

## Deployment Commands

### Development
```bash
# Deploy to development
wrangler deploy --env development

# Preview deployment
wrangler dev
```

### Staging
```bash
# Deploy to staging
wrangler deploy --env staging

# Test staging deployment
curl https://spotibye-api-staging.workers.dev/health
```

### Production
```bash
# Deploy to production
wrangler deploy --env production

# Verify production deployment
curl https://spotibye-api.workers.dev/health
```

## KV Namespace Setup

### Create Namespaces
```bash
# Production namespaces
wrangler kv:namespace create "CACHE_KV"
wrangler kv:namespace create "SESSIONS_KV"

# Staging namespaces
wrangler kv:namespace create "CACHE_KV" --env staging
wrangler kv:namespace create "SESSIONS_KV" --env staging

# Preview namespaces
wrangler kv:namespace create "CACHE_KV" --preview
wrangler kv:namespace create "SESSIONS_KV" --preview
```

### Update wrangler.toml
Replace placeholder IDs with actual namespace IDs from the commands above.

## Analysis Queue

Playlist analysis uses Cloudflare Queues in production so large playlists can retry outside the initial HTTP request. The Worker module exports both `fetch` and `queue`; no separate Worker entry point is required.

Required queues:

```bash
cd src/backend
npx wrangler queues create spotibye-analysis-dev
npx wrangler queues create spotibye-analysis-dev-dlq
npx wrangler queues create spotibye-analysis
npx wrangler queues create spotibye-analysis-dlq
```

The producer and consumer binding name is `ANALYSIS_QUEUE`. Queue messages contain `job_id`, `playlist_id`, `user_id`, `session_id`, `enqueued_at`, and `attempt`; they never contain Spotify access tokens. The consumer loads the session from `SESSIONS_KV` and refreshes the Spotify token when needed.

## Domain Configuration

### Custom Domains
```bash
# Add custom domain for production
wrangler custom-domains add spotibye-api.workers.dev

# Add custom domain for staging
wrangler custom-domains add spotibye-api-staging.workers.dev --env staging
```

### SSL Certificates
Cloudflare automatically manages SSL certificates for custom domains.

## CI/CD Pipeline

### GitHub Actions Example
```yaml
name: Deploy SpotiBye API

on:
  push:
    branches: [main, develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Run tests
        run: npm test

      - name: Deploy to staging
        if: github.ref == 'refs/heads/develop'
        run: wrangler deploy --env staging
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}

      - name: Deploy to production
        if: github.ref == 'refs/heads/main'
        run: wrangler deploy --env production
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```

## Monitoring Setup

### Cloudflare Analytics
- Enable in Cloudflare Dashboard
- Monitor request patterns and performance
- Set up alerts for error rates

### Custom Metrics
```typescript
// Add to your worker
export interface Env {
  // ... other bindings
  ANALYTICS: AnalyticsEngineDataset;
}

// Usage in handlers
env.ANALYTICS.writeDataPoint({
  blobs: [endpoint, method],
  doubles: [responseTime],
  indexes: [statusCode]
});
```

## Security Configuration

### Rate Limiting
```typescript
// Configure rate limits per environment
const RATE_LIMITS = {
  development: 1000, // per hour
  staging: 500,
  production: 100
};
```

### CORS Settings
```typescript
// Configure CORS for your frontend domains
const CORS_ORIGINS = {
  development: ['http://localhost:3000'],
  staging: ['https://staging.spotibye.com'],
  production: ['https://app.spotibye.com']
};
```

## Troubleshooting

### Common Issues
1. **KV namespace not found**: Check namespace IDs in wrangler.toml
2. **Secret not set**: Use `wrangler secret list` to verify
3. **Domain not working**: Verify DNS and SSL configuration
4. **Deployment fails**: Check for syntax errors and missing dependencies

### Debug Commands
```bash
# View deployment status
wrangler deployments list

# View logs
wrangler tail

# Test specific endpoint
curl -H "Authorization: Bearer $TOKEN" \
     https://spotibye-api.workers.dev/health
```

## Rollback Procedure

### Quick Rollback
```bash
# View previous deployments
wrangler deployments list

# Rollback to previous version
wrangler rollback --env production <deployment-id>
```

### Emergency Rollback
1. Disable custom domain in Cloudflare Dashboard
2. Point DNS to previous version or maintenance page
3. Investigate issue and redeploy when fixed

## Performance Optimization

### Caching Strategy
```typescript
// Configure cache TTLs
const CACHE_TTL = {
  development: 60, // 1 minute
  staging: 300,    // 5 minutes
  production: 3600 // 1 hour
};
```

### Worker Optimization
- Minimize bundle size with tree shaking
- Use edge caching for static responses
- Implement request deduplication
- Optimize KV access patterns

## Backup and Recovery

### KV Namespace Backup
```bash
# Export KV data
wrangler kv:key list --namespace-id your-kv-id
wrangler kv:key get --namespace-id your-kv-id key-name

# Restore KV data
wrangler kv:key put --namespace-id your-kv-id key-name value
```

### Configuration Backup
- Version control wrangler.toml
- Document all environment variables
- Keep backup of Spotify app credentials
- Store secrets in secure password manager

This configuration ensures reliable deployment across all environments with proper security, monitoring, and rollback capabilities.

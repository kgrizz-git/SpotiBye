# Cloudflare Worker Deployment Guide

## Prerequisites

- Node.js 18+
- Wrangler CLI (`npm install -g wrangler`)
- Cloudflare account with Workers enabled

## Deployment Steps

1. **Login to Cloudflare**
   ```bash
   wrangler login
   ```

2. **Configure Worker**
   - Edit `src/backend/wrangler.toml`
   - Set `name`, `account_id`, `route` patterns
   - Configure environment variables (KV namespaces, secrets)

3. **Build Worker**
   ```bash
   cd src/backend
   npm run build
   ```

4. **Deploy Worker**
   ```bash
   wrangler deploy
   ```

5. **Verify Deployment**
   - Check the deployed URL
   - Test health endpoint
   - Verify environment variables

## Environment Variables

Set secrets via wrangler:
```bash
wrangler secret put SPOTIFY_CLIENT_ID
wrangler secret put SPOTIFY_CLIENT_SECRET
```

## KV Namespaces

Create KV namespaces:
```bash
wrangler kv:namespace create "TOKENS"
wrangler kv:namespace create "EXPORT_CURSORS" --preview
```

Update `wrangler.toml` with namespace IDs.

## Common Issues

- **CORS errors:** Ensure routes handle OPTIONS requests
- **Secrets not available:** Verify secrets are set in production environment
- **KV access errors:** Check namespace bindings in wrangler.toml

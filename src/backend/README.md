# SpotiBye Backend - Cloudflare Workers

Cloudflare Workers backend for the SpotiBye Spotify Playlist Exporter application.

## Quick Start

### Prerequisites
- Node.js (v18 or higher)
- npm or yarn
- Cloudflare account (for deployment)

### Setup

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Set up environment variables**

   Create a `.dev.vars` file in the project root:
   ```bash
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   JWT_SECRET=your_jwt_secret
   ```

3. **Start local development**
   ```bash
   npm run dev
   ```

   The worker will start on `http://localhost:8787`

## Available Scripts

- `npm run dev` - Start local development server with Wrangler
- `npm run build` - Compile TypeScript to JavaScript
- `npm run deploy` - Deploy to Cloudflare Workers
- `npm run lint` - Run ESLint on TypeScript files
- `npm run format` - Format code with Prettier

## API Endpoints

### Authentication
- `POST /auth/spotify/login` - Initiate Spotify OAuth flow
- `GET /auth/spotify/callback` - Handle OAuth callback
- `POST /auth/spotify/refresh` - Refresh access tokens

### Spotify Data
- `GET /spotify/playlists` - Get user playlists
- `GET /spotify/playlists/:id` - Get playlist details
- `GET /spotify/playlists/:id/items` - Get playlist items
- `GET /spotify/playlists/:id/tracks` - Backward-compatible alias for playlist items
- `GET /spotify/tracks/:id` - Get track details

### Analysis
- `POST /analysis/playlist/:id` - Analyze playlist (ReccoBeats integration)
- `GET /analysis/playlist/:id/status` - Get analysis status
- `GET /analysis/playlist/:id/results` - Get analysis results

### Export
- `POST /export/playlist/:id` - Generate Excel export
- `GET /export/playlist/:id/download` - Download generated file

### System
- `GET /health` - Health check endpoint

## Environment Variables

### Required for Development
- `SPOTIFY_CLIENT_ID` - Spotify app client ID
- `SPOTIFY_CLIENT_SECRET` - Spotify app client secret
- `JWT_SECRET` - Secret for JWT token signing

ReccoBeats audio feature lookups use the public no-auth API and do not require a backend secret.

### Optional
- `ENVIRONMENT` - Set to "development" or "production" (defaults to development)

## KV Namespaces

The worker uses two KV namespaces:
- `CACHE_KV` - For caching Spotify API responses
- `SESSIONS_KV` - For storing user sessions

For local development, these use preview IDs. For production, you'll need to create actual KV namespaces in your Cloudflare account.

## Deployment

1. **Set up production secrets**
   ```bash
   wrangler secret put SPOTIFY_CLIENT_ID
   wrangler secret put SPOTIFY_CLIENT_SECRET
   wrangler secret put JWT_SECRET
   ```

2. **Create KV namespaces** (if not already created)
   ```bash
   wrangler kv:namespace create "CACHE_KV"
   wrangler kv:namespace create "SESSIONS_KV"
   ```

3. **Update wrangler.toml** with the actual KV namespace IDs

4. **Deploy**
   ```bash
   npm run deploy
   ```

## Development Tips

- Use `wrangler dev` for local development with hot reload
- Check the console output for API request logs
- Use the health check endpoint (`/health`) to verify the worker is running
- All API endpoints return JSON responses with proper error handling

## Troubleshooting

### Common Issues

1. **"wrangler command not found"**
   - Run `npm install` to install dependencies
   - Use `npx wrangler` instead of `wrangler`

2. **KV namespace errors**
   - Ensure KV namespaces are created in Cloudflare dashboard
   - Check that namespace IDs in `wrangler.toml` are correct

3. **Authentication failures**
   - Verify Spotify app credentials are correct
   - Check that redirect URIs match in Spotify developer dashboard

4. **CORS errors**
   - The worker includes CORS middleware for development
   - For production, ensure proper CORS configuration

## Architecture

- **Framework**: Hono.js for HTTP routing and middleware
- **Runtime**: Cloudflare Workers (V8 isolates)
- **Storage**: Cloudflare KV for caching and sessions
- **Authentication**: JWT tokens with Spotify OAuth
- **Language**: TypeScript

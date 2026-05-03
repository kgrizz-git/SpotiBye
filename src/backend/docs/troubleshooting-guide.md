# Troubleshooting Guide

This guide helps diagnose and resolve common issues with the SpotiBye Cloudflare Workers backend.

## Quick Diagnosis

### Health Check
```bash
curl https://spotibye-api.workers.dev/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2023-12-12T23:00:00Z",
  "version": "1.0.0"
}
```

### Log Monitoring
```bash
# View real-time logs
wrangler tail

# View specific deployment logs
wrangler tail --env production
```

## Common Issues

### Authentication Problems

#### 401 Unauthorized Errors
**Symptoms**: API calls return 401 status codes
**Causes**:
- Expired JWT token
- Invalid token format
- Missing Authorization header

**Solutions**:
```javascript
// Check token expiration
const token = localStorage.getItem('spotibye_token');
const payload = JSON.parse(atob(token.split('.')[1]));
const isExpired = payload.exp * 1000 < Date.now();

if (isExpired) {
  // Refresh token or re-authenticate
  await refreshToken();
}

// Verify token format
if (!token || !token.startsWith('Bearer ')) {
  throw new Error('Invalid token format');
}
```

#### OAuth Callback Failures
**Symptoms**: Redirect loop or error after Spotify authorization
**Causes**:
- State parameter mismatch
- Invalid redirect URI
- Spotify app configuration issues

**Solutions**:
```javascript
// Verify state parameter
const storedState = sessionStorage.getItem('spotify_auth_state');
const receivedState = urlParams.get('state');

if (storedState !== receivedState) {
  console.error('State mismatch - possible CSRF attack');
  // Restart authentication flow
}

// Check redirect URI configuration
const redirectUri = 'https://your-app-domain.com/callback';
// Ensure this matches Spotify Developer Dashboard settings
```

### API Performance Issues

#### Slow Response Times
**Symptoms**: Requests taking >2 seconds
**Causes**:
- Cold starts
- KV namespace latency
- Spotify API rate limits
- Large data processing

**Diagnostics**:
```javascript
// Measure response time
const start = Date.now();
const response = await fetch(url);
const duration = Date.now() - start;

if (duration > 2000) {
  console.warn(`Slow response: ${duration}ms`);
}
```

**Solutions**:
- Implement caching for frequently accessed data
- Use KV namespace optimization
- Add request deduplication
- Monitor Spotify API quota usage

#### Memory Issues
**Symptoms**: 500 errors or Worker crashes
**Causes**:
- Large playlist processing
- Memory leaks
- Excessive data storage

**Solutions**:
```typescript
// Process large playlists in chunks
async function processLargePlaylist(tracks: Track[]) {
  const CHUNK_SIZE = 100;
  const results = [];

  for (let i = 0; i < tracks.length; i += CHUNK_SIZE) {
    const chunk = tracks.slice(i, i + CHUNK_SIZE);
    const chunkResult = await processChunk(chunk);
    results.push(chunkResult);
  }

  return results;
}

// Clean up resources
function cleanup() {
  // Clear large objects
  largeDataArray = null;
  // Force garbage collection if available
  if (global.gc) global.gc();
}
```

### KV Namespace Issues

#### KV Connection Errors
**Symptoms**: KV operations failing
**Causes**:
- Incorrect namespace binding
- Namespace not created
- Permission issues

**Diagnostics**:
```bash
# Check KV namespace status
wrangler kv:namespace list

# Test KV connectivity
wrangler kv:key get --namespace-id your-namespace-id test-key
```

**Solutions**:
```typescript
// Add KV health check
async function checkKVHealth(env: Env): Promise<boolean> {
  try {
    await env.CACHE_KV.get('health-check');
    return true;
  } catch (error) {
    console.error('KV health check failed:', error);
    return false;
  }
}
```

#### Cache Invalidation Issues
**Symptoms**: Stale data being served
**Causes**:
- Incorrect TTL settings
- Cache key conflicts
- Missing cache updates

**Solutions**:
```typescript
// Implement proper cache keys
function getCacheKey(endpoint: string, params: any): string {
  const paramString = JSON.stringify(params);
  return `${endpoint}:${btoa(param-form-urlencoded(param Attacks
```

@@ -202,7 + + 202 Guest

### Spotify API Issuesaligned with voluntary
 congressional

####积极地
```O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

O

Ooma

O
### Spotify API читать

#### Rate Limitassociations
 Waters

**O

O

Oanto

### Spotify APIutar

#### Ratesert

#### Rate Limit Errors
**Symptoms**: 429 status codes
**Causes**:
- Exceeding Spotify API limits
- Concurrent requests
- Missing rate limiting implementation

**Solutions**:
```typescript
// Implement rate limiting
class RateLimiter {
  private requests: number = 0;
  private resetTime: number = 0;

  async checkLimit(): Promise<boolean> {
    const now = Date.now();

    if (now > this.resetTime) {
      this.requests = 0;
      this.resetTime = now + 60000; // 1 minute window
    }

    if (this.requests >= 100) { // Spotify limit
      const waitTime = this.resetTime - now;
      await new Promise(resolve => setTimeout(resolve, waitTime));
      return this.checkLimit();
    }

    this.requests++;
    return true;
  }
}
```

#### Invalid Spotify Credentials
**Symptoms**: 401 errors from Spotify API
**Causes**:
- Expired access token
- Invalid client credentials
- App permissions issues

**Solutions**:
```typescript
// Refresh Spotify token
async function refreshSpotifyToken(refreshToken: string): Promise<string> {
  const response = await fetch('https://accounts.spotify.com/api/token', {
    method: 'POST',
    headers: {
      'Authorization': `Basic ${btoa(`${SPOTIFY_CLIENT_ID}:${SPOTIFY_CLIENT_SECRET}`)}`,
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: 'grant_type=refresh_token&refresh_token=' + refreshToken
  });

  if (!response.ok) {
    throw new Error('Failed to refresh Spotify token');
  }

  const data = await response.json();
  return data.access_token;
}
```

### Export Issues

#### Export Generation Failures
**Symptoms**: 500 errors on export requests
**Causes**:
- Large playlist size
- Memory constraints
- File format issues

**Solutions**:
```typescript
// Implement streaming export
async function generateExportStream(playlist: Playlist) {
  const stream = new ReadableStream({
    async start(controller) {
      try {
        // Write header
        controller.write('Track Name,Artist,Album,Duration\n');

        // Stream tracks
        for (const track of playlist.tracks) {
          const row = `${track.name},${track.artist},${track.album},${track.duration}\n`;
          controller.write(row);
        }

        controller.close();
      } catch (error) {
        controller.error(error);
      }
    }
  });

  return stream;
}
```

#### Download Failures
**Symptoms**: 404 or 410 errors on download
**Causes**:
- Expired export files
- Incorrect export ID
- File cleanup issues

**Solutions**:
```typescript
// Check export validity
async function validateExport(env: Env, exportId: string): Promise<boolean> {
  const exportData = await env.EXPORT_KV.get(exportId);

  if (!exportData) {
    return false;
  }

  const { expiresAt } = JSON.parse(exportData);
  return Date.now() < expiresAt;
}
```

## Debugging Tools

### Local Development
```bash
# Start local development server
wrangler dev

# Enable debug logging
export LOG_LEVEL=debug

# Test with specific environment
wrangler dev --env development
```

### Remote Debugging
```bash
# View live logs
wrangler tail --format=pretty

# Filter logs by level
wrangler tail --log-level=error

# View specific function logs
wrangler tail --function-name=handleRequest
```

### Performance Analysis
```javascript
// Add performance monitoring
function withPerformanceMonitoring(fn: Function) {
  return async (...args: any[]) => {
    const start = performance.now();
    const result = await fn(...args);
    const duration = performance.now() - start;

    console.log(`Function ${fn.name} took ${duration.toFixed(2)}ms`);
    return result;
  };
}

// Usage
const monitoredHandler = withPerformanceMonitoring(handleRequest);
```

## Error Codes Reference

### HTTP Status Codes
- `200` - Success
- `400` - Bad Request (validation error)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error (unexpected error)
- `503` - Service Unavailable (dependency failure)

### Custom Error Codes
- `AUTH_001` - Invalid JWT token
- `AUTH_002` - Expired session
- `SPOTIFY_001` - Spotify API error
- `SPOTIFY_002` - Rate limit exceeded
- `KV_001` - KV namespace error
- `EXPORT_001` - Export generation failed
- `EXPORT_002` - Export file expired

## Recovery Procedures

### Emergency Rollback
```bash
# List recent deployments
wrangler deployments list

# Rollback to previous version
wrangler rollback --env production <deployment-id>

# Quick rollback to last known good
wrangler rollback --env production
```

### Data Recovery
```bash
# Backup KV data
wrangler kv:key list --namespace-id your-namespace-id > kv-backup.txt

# Restore KV data
while read key; do
  wrangler kv:key get --namespace-id your-namespace-id "$key" > "$key.backup"
done < kv-backup.txt
```

### Service Recovery
```bash
# Check service health
curl -f https://spotibye-api.workers.dev/health || echo "Service down"

# Restart service (deploy same version)
wrangler deploy --env production

# Clear problematic cache
wrangler kv:key delete --namespace-id your-cache-namespace "problematic-key"
```

## Prevention Strategies

### Monitoring Setup
- Set up alerts for error rates > 1%
- Monitor response times > 1 second
- Track KV operation failures
- Watch Spotify API quota usage

### Regular Maintenance
- Rotate secrets quarterly
- Clean up expired exports weekly
- Review logs for anomalies daily
- Update dependencies monthly

### Testing Practices
- Run integration tests before deployment
- Test with large playlists
- Verify error handling paths
- Validate rate limiting behavior

## Contact Support

When reporting issues, include:
- Environment (development/staging/production)
- Error messages and codes
- Request/response logs
- Steps to reproduce
- Browser/client information

### Support Channels
- **GitHub Issues**: Code and deployment problems
- **Email**: security and urgent issues
- **Slack**: real-time troubleshooting

This troubleshooting guide helps quickly identify and resolve common issues with the SpotiBye API backend.

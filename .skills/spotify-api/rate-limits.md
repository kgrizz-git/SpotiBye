# Spotify API Rate Limits

## Rate Limit Overview
Spotify Web API has rate limits to prevent abuse. Limits are based on OAuth tokens.

## Limits

- **Per application:** 10,000 requests per 30 seconds
- **Per user:** 30 requests per 30 seconds (for user-specific endpoints)

## Headers

Spotify returns rate limit headers in responses:
- `X-RateLimit-App`: Application limit (remaining, reset time)
- `X-RateLimit-App-Over`: Application limit exceeded count
- `Retry-After`: Seconds to wait before retry (429 response)

## Retry Strategy

When receiving 429 (Too Many Requests):
1. Parse `Retry-After` header
2. Wait specified seconds before retry
3. Use exponential backoff for subsequent retries

## Implementation

Rate limiting is handled in `src/backend/services/spotify.ts`:
- Automatic retry with exponential backoff
- Respect `Retry-After` header
- Log rate limit events for monitoring

## Best Practices

- Cache responses to reduce API calls
- Batch requests when possible
- Monitor rate limit usage
- Implement graceful degradation when limits hit

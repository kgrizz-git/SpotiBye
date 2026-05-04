# KV Namespace Structure Documentation

This document describes the structure and usage of KV namespaces in the SpotiBye Cloudflare Workers backend.

## Overview

The backend uses two primary KV namespaces:
- `CACHE_KV` - Caching Spotify API responses and computed data
- `SESSIONS_KV` - User session management and OAuth state

## Namespace Configuration

### CACHE_KV
- **Purpose**: Cache frequently accessed data to reduce Spotify API calls
- **TTL**: Variable (1 hour to 24 hours depending on data type)
- **Size Limit**: 1GB per namespace (Cloudflare limit)
- **Operations**: Read-heavy with occasional writes

### SESSIONS_KV
- **Purpose**: Store user sessions and OAuth state
- **TTL**: 24 hours for sessions, 10 minutes for OAuth state
- **Size Limit**: 1GB per namespace
- **Operations**: Balanced read/write operations

## Key Naming Conventions

### CACHE_KV Keys
```
# Spotify API responses
spotify:user:{userId}:playlists
spotify:playlist:{playlistId}
spotify:playlist:{playlistId}:tracks:{offset}:{limit}

# Analysis results
analysis:playlist:{playlistId}
analysis:playlist:{playlistId}:features
analysis:playlist:{playlistId}:recommendations

# Export data
export:{exportId}
export:playlist:{playlistId}:{format}

# Rate limiting
ratelimit:user:{userId}:global
ratelimit:user:{userId}:endpoint:{endpoint}
```

### SESSIONS_KV Keys
```
# User sessions
session:{sessionId}
session:user:{userId}

# OAuth state
oauth:state:{stateId}
oauth:code:{codeId}

# User preferences
prefs:user:{userId}
prefs:user:{userId}:theme
prefs:user:{userId}:settings
```

## Data Structures

### Spotify API Cache
```typescript
interface CachedPlaylist {
  id: string;
  name: string;
  description?: string;
  tracks_count: number;
  owner: string;
  followers: number;
  public: boolean;
  collaborative: boolean;
  images: Image[];
  cached_at: string;
  expires_at: string;
}

interface CachedTracks {
  tracks: Track[];
  total: number;
  limit: number;
  offset: number;
  cached_at: string;
  expires_at: string;
}
```

### Analysis Cache
```typescript
interface CachedAnalysis {
  playlist_id: string;
  total_tracks: number;
  duration_minutes: number;
  average_bpm: number;
  energy_score: number;
  danceability: number;
  valence: number;
  acousticness: number;
  instrumentalness: number;
  genres: string[];
  top_artists: TopArtist[];
  audio_features: AudioFeatures;
  recommendations?: Recommendations;
  cached_at: string;
  expires_at: string;
}
```

### Session Data
```typescript
interface UserSession {
  user_id: string;
  spotify_access_token: string;
  spotify_refresh_token: string;
  expires_at: string;
  created_at: string;
  last_accessed: string;
  preferences: UserPreferences;
}

interface OAuthState {
  state_id: string;
  redirect_uri: string;
  created_at: string;
  expires_at: string;
}
```

## Cache Management

### TTL Strategies
```typescript
const CACHE_TTL = {
  // Spotify data (changes rarely)
  'spotify:user:playlists': 3600, // 1 hour
  'spotify:playlist:': 1800,     // 30 minutes
  'spotify:playlist:tracks:': 900, // 15 minutes

  // Analysis results (computed data)
  'analysis:playlist:': 7200,    // 2 hours

  // Export data (temporary)
  'export:': 86400,              // 24 hours

  // Rate limiting (short-term)
  'ratelimit:': 60,              // 1 minute

  // Sessions (security)
  'session:': 86400,             // 24 hours
  'oauth:state:': 600             // 10 minutes
};
```

### Cache Invalidation
```typescript
// Invalidate user-specific cache
async function invalidateUserCache(env: Env, userId: string) {
  const pattern = `spotify:user:${userId}:*`;
  const keys = await env.CACHE_KV.list({ prefix: `spotify:user:${userId}:` });

  for (const key of keys.keys) {
    await env.CACHE_KV.delete(key.name);
  }
}

// Invalidate playlist cache
async function invalidatePlaylistCache(env: Env, playlistId: string) {
  const keysToDelete = [
    `spotify:playlist:${playlistId}`,
    `spotify:playlist:${playlistId}:tracks:`,
    `analysis:playlist:${playlistId}`
  ];

  for (const key of keysToDelete) {
    const keys = await env.CACHE_KV.list({ prefix: key });
    for (const k of keys.keys) {
      await env.CACHE_KV.delete(k.name);
    }
  }
}
```

## Performance Optimization

### Batch Operations
```typescript
// Batch write for multiple cache entries
async function batchCacheUpdate(env: Env, entries: Array<{key: string, value: any, ttl?: number}>) {
  const promises = entries.map(entry =>
    env.CACHE_KV.put(entry.key, JSON.stringify(entry.value), {
      expirationTtl: entry.ttl || 3600
    })
  );

  await Promise.all(promises);
}

// Batch read with fallback
async function batchCacheRead(env: Env, keys: string[]): Promise<Map<string, any>> {
  const results = new Map();
  const promises = keys.map(async key => {
    const value = await env.CACHE_KV.get(key);
    if (value) {
      results.set(key, JSON.parse(value));
    }
  });

  await Promise.all(promises);
  return results;
}
```

### Cache Warming
```typescript
// Pre-warm cache for popular playlists
async function warmPlaylistCache(env: Env, playlistIds: string[]) {
  for (const playlistId of playlistIds) {
    try {
      // Check if already cached
      const cached = await env.CACHE_KV.get(`spotify:playlist:${playlistId}`);
      if (!cached) {
        // Fetch from Spotify and cache
        const playlist = await fetchFromSpotify(`/playlists/${playlistId}`);
        await env.CACHE_KV.put(
          `spotify:playlist:${playlistId}`,
          JSON.stringify(playlist),
          { expirationTtl: 1800 }
        );
      }
    } catch (error) {
      console.error(`Failed to warm cache for playlist ${playlistId}:`, error);
    }
  }
}
```

## Data Migration

### Schema Versioning
```typescript
interface CacheEntry<T> {
  version: number;
  data: T;
  cached_at: string;
  expires_at: string;
}

// Version-aware cache operations
async function getVersionedCache<T>(env: Env, key: string, expectedVersion: number): Promise<T | null> {
  const raw = await env.CACHE_KV.get(key);
  if (!raw) return null;

  const entry: CacheEntry<T> = JSON.parse(raw);

  if (entry.version !== expectedVersion) {
    // Outdated version, invalidate and return null
    await env.CACHE_KV.delete(key);
    return null;
  }

  return entry.data;
}

async function setVersionedCache<T>(env: Env, key: string, data: T, ttl: number, version: number) {
  const entry: CacheEntry<T> = {
    version,
    data,
    cached_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + ttl * 1000).toISOString()
  };

  await env.CACHE_KV.put(key, JSON.stringify(entry), { expirationTtl: ttl });
}
```

### Migration Scripts
```typescript
// Migrate from v1 to v2 cache format
async function migrateCacheV1ToV2(env: Env) {
  const keys = await env.CACHE_KV.list();

  for (const key of keys.keys) {
    if (key.name.startsWith('spotify:')) {
      const raw = await env.CACHE_KV.get(key.name);
      if (raw) {
        try {
          const data = JSON.parse(raw);

          // Check if it's old format
          if (!data.version) {
            // Migrate to new format
            await setVersionedCache(env, key.name, data, 3600, 2);
            console.log(`Migrated key: ${key.name}`);
          }
        } catch (error) {
          console.error(`Failed to migrate key ${key.name}:`, error);
        }
      }
    }
  }
}
```

## Monitoring and Analytics

### Cache Performance Metrics
```typescript
interface CacheMetrics {
  hits: number;
  misses: number;
  sets: number;
  deletes: number;
  errors: number;
}

class CacheMonitor {
  private metrics: CacheMetrics = {
    hits: 0,
    misses: 0,
    sets: 0,
    deletes: 0,
    errors: 0
  };

  recordHit() { this.metrics.hits++; }
  recordMiss() { this.metrics.misses++; }
  recordSet() { this.metrics.sets++; }
  recordDelete() { this.metrics.deletes++; }
  recordError() { this.metrics.errors++; }

  getHitRate(): number {
    const total = this.metrics.hits + this.metrics.misses;
    return total > 0 ? this.metrics.hits / total : 0;
  }

  getMetrics(): CacheMetrics {
    return { ...this.metrics };
  }

  reset() {
    this.metrics = {
      hits: 0,
      misses: 0,
      sets: 0,
      deletes: 0,
      errors: 0
    };
  }
}
```

### Storage Analysis
```typescript
// Analyze KV storage usage
async function analyzeKVUsage(env: Env) {
  const cacheKeys = await env.CACHE_KV.list();
  const sessionKeys = await env.SESSIONS_KV.list();

  const analysis = {
    cache: {
      totalKeys: cacheKeys.keys.length,
      estimatedSize: 0, // KV doesn't provide size info
      oldestKey: null,
      newestKey: null
    },
    sessions: {
      totalKeys: sessionKeys.keys.length,
      estimatedSize: 0,
      activeSessions: 0
    }
  };

  // Sample keys for size estimation
  const sampleSize = Math.min(100, cacheKeys.keys.length);
  let totalSampleSize = 0;

  for (let i = 0; i < sampleSize; i++) {
    const key = cacheKeys.keys[i];
    const value = await env.CACHE_KV.get(key.name);
    if (value) {
      totalSampleSize += JSON.stringify(value).length;
    }
  }

  if (sampleSize > 0) {
    analysis.cache.estimatedSize = (totalSampleSize / sampleSize) * cacheKeys.keys.length;
  }

  return analysis;
}
```

## Security Considerations

### Data Sanitization
```typescript
// Sanitize data before caching
function sanitizeForCache(data: any): any {
  if (typeof data !== 'object' || data === null) {
    return data;
  }

  const sanitized = Array.isArray(data) ? [] : {};

  for (const [key, value] of Object.entries(data)) {
    // Remove sensitive fields
    if (key.includes('token') || key.includes('secret') || key.includes('password')) {
      continue;
    }

    // Recursively sanitize nested objects
    sanitized[key] = sanitizeForCache(value);
  }

  return sanitized;
}
```

### Access Control
```typescript
// Validate cache access permissions
async function canAccessCache(env: Env, userId: string, key: string): Promise<boolean> {
  // Users can only access their own cache entries
  if (key.includes(`user:${userId}`)) {
    return true;
  }

  // Public data access
  if (key.startsWith('spotify:playlist:') && !key.includes('user:')) {
    return true;
  }

  return false;
}
```

## Backup and Recovery

### Backup Strategy
```typescript
// Export KV data for backup
async function exportKVData(env: Env, namespace: 'CACHE_KV' | 'SESSIONS_KV'): Promise<string> {
  const kv = namespace === 'CACHE_KV' ? env.CACHE_KV : env.SESSIONS_KV;
  const keys = await kv.list();

  const backup = {
    namespace,
    exported_at: new Date().toISOString(),
    keys: []
  };

  for (const key of keys.keys) {
    const value = await kv.get(key.name);
    if (value) {
      backup.keys.push({
        key: key.name,
        value: value,
        expiration: key.expiration
      });
    }
  }

  return JSON.stringify(backup);
}

// Restore KV data from backup
async function restoreKVData(env: Env, backupData: string): Promise<void> {
  const backup = JSON.parse(backupData);
  const kv = backup.namespace === 'CACHE_KV' ? env.CACHE_KV : env.SESSIONS_KV;

  for (const entry of backup.keys) {
    await kv.put(entry.key, entry.value, {
      expirationTtl: entry.expiration
    });
  }
}
```

## Best Practices

### Key Design
- Use consistent naming conventions
- Include version numbers in keys for schema changes
- Use prefixes for logical grouping
- Keep keys reasonably short but descriptive

### TTL Management
- Set appropriate TTLs based on data volatility
- Use shorter TTLs for user-specific data
- Use longer TTLs for static reference data
- Implement cache invalidation for critical updates

### Performance
- Batch operations when possible
- Use list operations for bulk operations
- Monitor cache hit rates
- Implement cache warming for popular data

### Security
- Never cache sensitive tokens or passwords
- Implement access controls for user data
- Sanitize data before caching
- Use encryption for highly sensitive data

This KV namespace structure provides efficient data storage, caching, and session management for the SpotiBye backend while maintaining security and performance.

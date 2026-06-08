# Fix Playlist Analysis 403 Error — Spotify API February 2026 Migration

## Problem

Playlist analysis fails with HTTP 403 Forbidden error when analyzing playlists. The error occurs in the backend analysis service when fetching artist data.

**Error logs:**
```
[ERROR  ] [Playlist analysis failed] Analysis failed: HTTP 403: Forbidden
[ERROR  ] [Backend API error] Analysis failed: HTTP 403: Forbidden
```

## Root Cause

The Spotify Web API February 2026 migration removed the batch endpoint `GET /artists` (for fetching multiple artists at once) for Development Mode applications. This endpoint now returns 403 Forbidden.

**Affected code:**
- `src/backend/services/spotify.ts:109-121` — `getArtists()` method uses removed endpoint
- `src/backend/services/analysis.ts:76` — calls `spotifyService.getArtists([...artistIdSet])`

**Spotify changelog reference:**
- [REMOVED] Get Several Artists (GET /artists) – Get Spotify catalog information for several artists based on their Spotify IDs.

## Investigation Findings

### Available Endpoints (Still Working)
According to the Spotify API changelog, the following endpoint is still available:
- `GET /artists/{id}` – Retrieves detailed metadata for a single artist

### Current Implementation
The current `getArtists()` method:
1. Batches artist IDs in groups of 50
2. Calls `GET /artists?ids=id1,id2,...` (REMOVED endpoint)
3. Returns array of artist data

### Impact
- Playlist analysis cannot fetch artist genre data
- Genre distribution and artist insights are unavailable
- Analysis job fails completely instead of degrading gracefully

## Solution Approach

Replace the batch `GET /artists` endpoint with individual calls to `GET /artists/{id}` for each artist ID.

### Trade-offs
- **Pros**: Restores artist genre data functionality
- **Cons**: More API calls (1 per artist instead of 1 per 50 artists), increased latency
- **Mitigation**: Implement rate limiting and parallel requests with concurrency control

## Implementation Plan

### Phase 1: Update SpotifyService

**File: `src/backend/services/spotify.ts`**

1. Replace `getArtists()` implementation:
   ```typescript
   async getArtists(artistIds: string[]): Promise<SpotifyArtistFull[]> {
     // Replace batch endpoint with individual calls
     // Use Promise.all with concurrency limit (e.g., 10 concurrent requests)
     // Implement rate limiting to avoid 429 errors
   }
   ```

2. Add concurrency control helper:
   ```typescript
   private async fetchWithConcurrency<T>(
     items: string[],
     fetchFn: (id: string) => Promise<T>,
     concurrency: number = 10
   ): Promise<T[]>
   ```

### Phase 2: Add Graceful Degradation

**File: `src/backend/services/analysis.ts`**

1. Wrap artist fetching in try-catch:
   ```typescript
   let artistData: SpotifyArtistFull[] = [];
   try {
     artistData = await spotifyService.getArtists([...artistIdSet]);
   } catch (error) {
     console.warn('Failed to fetch artist data, continuing without genre insights:', error);
     artistData = [];
   }
   ```

2. Ensure analysis continues even if artist fetch fails:
   - Genre distribution will be empty
   - Other insights (duration, artist counts) still work

### Phase 3: Update Tests

**File: `src/backend/tests/spotify.test.ts`**

1. Update mocks for individual artist endpoint calls
2. Add test for graceful degradation when artist fetch fails
3. Test rate limiting behavior

### Phase 4: Documentation Updates

1. Update `docs/february-2026-spotify-migration-findings.md` with this fix
2. Add note about rate limiting considerations in backend docs

## Implementation Steps

1. Update `SpotifyService.getArtists()` to use individual `GET /artists/{id}` calls
2. Add concurrency control to prevent overwhelming Spotify API
3. Add error handling in `AnalysisService.analyzePlaylist()` for graceful degradation
4. Update unit tests to match new implementation
5. Test with real playlist analysis
6. Update documentation

## Testing Checklist

- [ ] Unit tests pass for updated `getArtists()` method
- [ ] Analysis completes successfully with artist data
- [ ] Analysis completes successfully even if artist fetch fails (graceful degradation)
- [ ] No 429 rate limit errors under normal load
- [ ] Performance acceptable (analysis completes in reasonable time)
- [ ] Genre distribution populates correctly when artist data available

## References

- [Spotify Web API Changelog - February 2026](https://developer.spotify.com/documentation/web-api/references/changes/february-2026)
- [February 2026 Migration Guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
- Existing migration findings: `docs/february-2026-spotify-migration-findings.md`

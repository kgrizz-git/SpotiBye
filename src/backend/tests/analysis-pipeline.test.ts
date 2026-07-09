import { afterEach, describe, expect, it, vi } from 'vitest';
import { AnalysisJobService } from '../services/analysis-job';
import { SpotifyService } from '../services/spotify';
import { kvNamespace, envWithKv } from './helpers/kv';
import type { AnalysisQueueMessage } from '../types/analysis-queue';
import type { AnalysisResult } from '../types/analysis';
import type { SpotifyTrack, SpotifyArtistFull } from '../types/spotify';

const track = (id: string, artistId: string, artistName: string): SpotifyTrack => ({
  id,
  name: `Track ${id}`,
  artists: [
    {
      id: artistId,
      name: artistName,
      external_urls: { spotify: `https://open.spotify.com/artist/${artistId}` },
      uri: `spotify:artist:${artistId}`,
    },
  ],
  album: {
    id: `album-${id}`,
    name: `Album ${id}`,
    artists: [],
    images: [],
    release_date: '2026-01-01',
    total_tracks: 1,
    external_urls: { spotify: `https://open.spotify.com/album/${id}` },
    uri: `spotify:album:${id}`,
  },
  duration_ms: 200000,
  explicit: false,
  popularity: 50,
  external_urls: { spotify: `https://open.spotify.com/track/${id}` },
  uri: `spotify:track:${id}`,
  preview_url: null,
});

const artist = (id: string, name: string): SpotifyArtistFull => ({
  id,
  name,
  genres: ['pop'],
  popularity: 60,
  external_urls: { spotify: `https://open.spotify.com/artist/${id}` },
  uri: `spotify:artist:${id}`,
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('AnalysisJobService end-to-end pipeline', () => {
  it('populates KV with a full AnalysisResult including ReccoBeats enrichment', async () => {
    vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks').mockResolvedValue({
      total: 2,
      rawCount: 2,
      items: [
        { added_by: null, track: track('track1', 'artist1', 'Artist 1') },
        { added_by: null, track: track('track2', 'artist2', 'Artist 2') },
      ],
    });
    vi.spyOn(SpotifyService.prototype, 'getArtists').mockResolvedValue([
      artist('artist1', 'Artist 1'),
      artist('artist2', 'Artist 2'),
    ]);

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input));
      if (url.pathname === '/v1/track') {
        return new Response(
          JSON.stringify({
            content: [
              {
                id: 'm1', trackTitle: 'Track 1',
                artists: [{ id: 'a1', name: 'Artist 1', href: 'https://open.spotify.com/artist/artist1' }],
                durationMs: 200000, isrc: 'ISRC1', popularity: 55,
              },
              {
                id: 'm2', trackTitle: 'Track 2',
                artists: [{ id: 'a2', name: 'Artist 2', href: 'https://open.spotify.com/artist/artist2' }],
                durationMs: 200000, popularity: 75,
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }
      return new Response(
        JSON.stringify({
          content: [
            {
              id: 'r1', href: 'https://open.spotify.com/track/track1',
              acousticness: 0.1, danceability: 0.2, energy: 0.3, instrumentalness: 0.1,
              liveness: 0.1, loudness: -5, speechiness: 0.1, tempo: 100, valence: 0.4,
              key: 0, mode: 1, isrc: 'ISRC1',
            },
            {
              id: 'r2', href: 'https://open.spotify.com/track/track2',
              acousticness: 0.2, danceability: 0.3, energy: 0.4, instrumentalness: 0.2,
              liveness: 0.2, loudness: -6, speechiness: 0.2, tempo: 110, valence: 0.5,
              key: 0, mode: 1,
            },
          ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    });
    vi.stubGlobal('fetch', fetchMock);

    const statusKey = 'analysis:playlist1:user1:status';
    const resultsKey = 'analysis:playlist1:user1:results';
    const cacheKv = kvNamespace({
      [statusKey]: {
        job_id: 'job1',
        playlist_id: 'playlist1',
        user_id: 'user1',
        status: 'queued',
        progress: 0,
      },
    });
    const sessionsKv = kvNamespace({
      session1: {
        user_id: 'user1',
        access_token: 'token',
        refresh_token: 'refresh',
        expires_at: Date.now() + 3_600_000,
      },
    });

    const message: AnalysisQueueMessage = {
      job_id: 'job1',
      playlist_id: 'playlist1',
      user_id: 'user1',
      session_id: 'session1',
      enqueued_at: new Date().toISOString(),
      attempt: 0,
    };

    const service = new AnalysisJobService(envWithKv(cacheKv, sessionsKv));
    const outcome = await service.process(message);

    expect(outcome).toEqual({ acknowledged: true, reason: 'completed' });

    const resultsRaw = await cacheKv.get(resultsKey);
    expect(resultsRaw).not.toBeNull();
    const result = JSON.parse(resultsRaw as string) as AnalysisResult;

    expect(result.schema_version).toBe('1.0');
    expect(result.errors).toEqual([]);
    expect(result.overview?.total_tracks).toBe(2);
    expect(result.audio_features?.track_count).toBe(2);
    expect(result.audio_features?.key_mode_distribution).toEqual({
      key_percentages: { C: 100 },
      dominant_key: 'C',
      dominant_key_percentage: 100,
      mode_percentages: { major: 100, minor: 0 },
      dominant_mode: 'major',
    });
    expect(result.reccobeats_metadata).toMatchObject({
      isrc_available: 1,
      popularity_min: 55,
      popularity_max: 75,
    });

    const statusRaw = await cacheKv.get(statusKey);
    const status = JSON.parse(statusRaw as string) as { status: string; progress: number };
    expect(status.status).toBe('completed');
    expect(status.progress).toBe(100);
  });
});

import { SpotifyService } from './spotify';
import type { SpotifyArtistFull, SpotifyTrack, SpotifyPlaylistTrackItem } from '../types/spotify';

interface AnalysisResult {
  job_id: string;
  playlist_id: string;
  user_id: string;
  status: string;
  computed_at: string;
  completed_at: string;
  overview?: {
    total_tracks: number;
    total_duration_ms: number;
    average_duration_ms: number;
    formatted_duration: string;
  };
  artists?: {
    unique_artists: number;
    top_artists: Array<{ artist: string; count: number }>;
    diversity: number;
  };
  genre_distribution?: Record<string, { count: number; percentage: number }>;
  insights?: string[];
}

interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  started_at: string;
}

interface PlaylistInsights {
  overview: {
    total_tracks: number;
    total_duration_ms: number;
    average_duration_ms: number;
    formatted_duration: string;
  };
  artists: {
    unique_artists: number;
    top_artists: Array<{ artist: string; count: number }>;
    diversity: number;
  };
  genre_distribution: Record<string, { count: number; percentage: number }>;
  insights: string[];
}

export class AnalysisService {
  private accessToken: string;
  private reccoBeatsUrl = 'https://api.recocbeats.com/v1';

  constructor(accessToken: string) {
    this.accessToken = accessToken;
  }

  async analyzePlaylist(playlistId: string, userId: string, jobId: string): Promise<AnalysisResult> {
    try {
      const spotifyService = new SpotifyService(this.accessToken);

      // Get all playlist tracks, paginating by raw page size to correctly
      // advance offsets past local/unavailable items.
      const allItems: typeof tracksData.items = [];
      let offset = 0;
      const limit = 100;
      let tracksData: Awaited<ReturnType<typeof spotifyService.getPlaylistTracks>>;
      do {
        tracksData = await spotifyService.getPlaylistTracks(playlistId, limit, offset);
        allItems.push(...tracksData.items);
        offset += limit;
      } while (tracksData.rawCount === limit && offset < tracksData.total);

      // Normalize items: handle both .track (old) and .item (Feb-2026 shape)
      const tracks = allItems
        .map((item: SpotifyPlaylistTrackItem) => item.track ?? item.item)
        .filter((t): t is SpotifyTrack => t?.id !== undefined);

      // Collect unique artist IDs and fetch full artist objects (for genre data)
      const artistIdSet = new Set<string>();
      for (const track of tracks) {
        for (const artist of (track.artists ?? [])) {
          if (artist.id) artistIdSet.add(artist.id);
        }
      }
      let artistData: SpotifyArtistFull[] = [];
      try {
        artistData = await spotifyService.getArtists([...artistIdSet]);
      } catch (error) {
        console.warn('Failed to fetch Spotify artist metadata; continuing without genre insights', {
          playlistId,
          artistCount: artistIdSet.size,
          error: error instanceof Error ? error.message : String(error),
        });
      }

      // NOTE: Spotify /audio-features was removed in the Feb 2026 API migration and
      // returns HTTP 403. Insights are built from track metadata + artist genres only.
      const spotifyInsights = await this.generatePlaylistInsights(tracks, artistData);

      return {
        job_id: jobId,
        playlist_id: playlistId,
        user_id: userId,
        status: 'completed',
        computed_at: new Date().toISOString(),
        ...spotifyInsights,
        completed_at: new Date().toISOString()
      };
    } catch (error) {
      console.error('Analysis error:', error);
      throw error;
    }
  }

  private async callReccoBeatsAPI(data: unknown): Promise<unknown> {
    const response = await fetch(`${this.reccoBeatsUrl}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`ReccoBeats API error: ${error}`);
    }

    return await response.json();
  }

  async getAnalysisJobStatus(jobId: string): Promise<JobStatus> {
    // This would typically query a Durable Object or database for job status
    // For now, we'll return a placeholder
    return {
      job_id: jobId,
      status: 'processing',
      progress: 50,
      started_at: new Date().toISOString()
    };
  }

  async generatePlaylistInsights(tracks: SpotifyTrack[], artistData: SpotifyArtistFull[] = []): Promise<PlaylistInsights> {
    const totalTracks = tracks.length;
    if (totalTracks === 0) {
      return {
        overview: { total_tracks: 0, total_duration_ms: 0, average_duration_ms: 0, formatted_duration: '0s' },
        artists: { unique_artists: 0, top_artists: [], diversity: 0 },
        genre_distribution: {},
        insights: []
      };
    }

    const totalDuration = tracks.reduce((sum, track) => sum + (track.duration_ms ?? 0), 0);
    const avgDuration = totalDuration / totalTracks;

    const artistCounts = this.countArtists(tracks);
    const topArtists = Object.entries(artistCounts)
      .sort(([, a], [, b]) => (b as number) - (a as number))
      .slice(0, 10)
      .map(([artist, count]) => ({ artist, count }));

    const genreDistribution = this.aggregateGenres(artistData);
    const insights = this.generateInsightsFromMetadata(tracks, genreDistribution);

    return {
      overview: {
        total_tracks: totalTracks,
        total_duration_ms: totalDuration,
        average_duration_ms: avgDuration,
        formatted_duration: this.formatDuration(totalDuration)
      },
      artists: {
        unique_artists: Object.keys(artistCounts).length,
        top_artists: topArtists,
        diversity: Object.keys(artistCounts).length / totalTracks,
      },
      genre_distribution: genreDistribution,
      insights
    };
  }

  private aggregateGenres(artists: SpotifyArtistFull[]): Record<string, { count: number; percentage: number }> {
    const raw: Record<string, number> = {};
    for (const artist of artists) {
      for (const genre of (artist.genres ?? [])) {
        raw[genre] = (raw[genre] ?? 0) + 1;
      }
    }
    const total = Object.values(raw).reduce((s, n) => s + n, 0);
    if (total === 0) return {};

    return Object.fromEntries(
      Object.entries(raw)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 15)
        .map(([genre, count]) => [genre, { count, percentage: Math.round((count / total) * 1000) / 10 }])
    );
  }

  private calculateAverageAudioFeatures(features: Record<string, number>[]): Record<string, number> {
    if (features.length === 0) return {};

    const sums = features.reduce((acc, feature) => {
      Object.keys(feature).forEach(key => {
        if (typeof feature[key] === 'number') {
          acc[key] = (acc[key] || 0) + feature[key];
        }
      });
      return acc;
    }, {});

    const count = features.length;
    const averages: Record<string, number> = {};

    Object.keys(sums).forEach(key => {
      averages[key] = sums[key] / count;
    });

    return averages;
  }

  private countArtists(tracks: SpotifyTrack[]): Record<string, number> {
    return tracks.reduce((acc: Record<string, number>, track) => {
      track.artists.forEach((artist) => {
        acc[artist.name] = (acc[artist.name] || 0) + 1;
      });
      return acc;
    }, {});
  }

  private calculateDistribution(values: number[]): { low: number; medium: number; high: number } {
    const total = values.length;
    const low = values.filter(v => v < 0.33).length;
    const medium = values.filter(v => v >= 0.33 && v < 0.67).length;
    const high = values.filter(v => v >= 0.67).length;

    return {
      low: (low / total) * 100,
      medium: (medium / total) * 100,
      high: (high / total) * 100
    };
  }

  private generateInsightsFromMetadata(
    tracks: SpotifyTrack[],
    genreDistribution: Record<string, { count: number; percentage: number }>
  ): string[] {
    const insights: string[] = [];
    const total = tracks.length;
    if (total === 0) return insights;

    // Duration-based insight
    const avgDurationMin = tracks.reduce((s, t) => s + (t.duration_ms ?? 0), 0) / total / 60_000;
    if (avgDurationMin > 5) {
      insights.push('This playlist features longer tracks — great for immersive listening.');
    } else if (avgDurationMin < 2.5) {
      insights.push('Short, punchy tracks — this playlist keeps things moving fast.');
    }

    // Genre diversity
    const topGenres = Object.entries(genreDistribution)
      .sort(([, a], [, b]) => b.count - a.count)
      .slice(0, 3)
      .map(([g]) => g);
    if (topGenres.length > 0) {
      insights.push(`Top genres: ${topGenres.join(', ')}.`);
    }
    if (Object.keys(genreDistribution).length > 10) {
      insights.push('This playlist spans a wide variety of genres.');
    }

    return insights;
  }

  private formatDuration(ms: number): string {
    const hours = Math.floor(ms / (1000 * 60 * 60));
    const minutes = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((ms % (1000 * 60)) / 1000);

    if (hours > 0) {
      return `${hours}h ${minutes}m ${seconds}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  }
}

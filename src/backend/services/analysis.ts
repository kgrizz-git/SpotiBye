import { SpotifyService } from './spotify';
import { CacheService } from './cache';
import type { Env } from '../types/env';

export class AnalysisService {
  private reccoBeatsApiKey: string;
  private accessToken: string;
  private reccoBeatsUrl = 'https://api.recocbeats.com/v1';
  
  constructor(reccoBeatsApiKey: string, accessToken: string) {
    this.reccoBeatsApiKey = reccoBeatsApiKey;
    this.accessToken = accessToken;
  }
  
  async analyzePlaylist(playlistId: string, userId: string, jobId: string): Promise<any> {
    try {
      // This would typically run in a Durable Object or background job
      // For now, we'll implement it as a synchronous process
      
      const spotifyService = new SpotifyService(this.accessToken);
      
      // Get playlist details and tracks
      const playlist = await spotifyService.getPlaylist(playlistId);
      const tracksData = await spotifyService.getPlaylistTracks(playlistId, 100, 0);
      
      // Extract track IDs
      const trackIds = tracksData.items
        .filter((item: any) => item.track && item.track.id)
        .map((item: any) => item.track.id);
      
      // Get audio features for all tracks
      const audioFeatures = await spotifyService.getMultipleAudioFeatures(trackIds);
      
      // Prepare data for ReccoBeats analysis
      const analysisData = {
        playlist_id: playlistId,
        playlist_name: playlist.name,
        tracks: tracksData.items.map((item: any, index: number) => ({
          id: item.track.id,
          name: item.track.name,
          artists: item.track.artists.map((artist: any) => artist.name),
          album: item.track.album.name,
          duration_ms: item.track.duration_ms,
          popularity: item.track.popularity ?? 0,
          audio_features: audioFeatures[index] || null
        }))
      };
      
      // Call ReccoBeats API
      const analysisResults = await this.callReccoBeatsAPI(analysisData);
      
      // Store results (this would be done via the cache service passed in)
      // For now, we'll just return the results
      
      return {
        job_id: jobId,
        playlist_id: playlistId,
        user_id: userId,
        status: 'completed',
        results: analysisResults,
        completed_at: new Date().toISOString()
      };
    } catch (error) {
      console.error('Analysis error:', error);
      throw error;
    }
  }
  
  private async callReccoBeatsAPI(data: any): Promise<any> {
    const response = await fetch(`${this.reccoBeatsUrl}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.reccoBeatsApiKey}`
      },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      const error = await response.text();
      throw new Error(`ReccoBeats API error: ${error}`);
    }
    
    return await response.json();
  }
  
  async getAnalysisJobStatus(jobId: string): Promise<any> {
    // This would typically query a Durable Object or database for job status
    // For now, we'll return a placeholder
    return {
      job_id: jobId,
      status: 'processing',
      progress: 50,
      started_at: new Date().toISOString()
    };
  }
  
  async generatePlaylistInsights(tracks: any[], audioFeatures: any[]): Promise<any> {
    // Calculate various metrics
    const totalTracks = tracks.length;
    const totalDuration = tracks.reduce((sum, track) => sum + track.duration_ms, 0);
    const avgDuration = totalDuration / totalTracks;
    
    // Audio feature averages
    const avgFeatures = this.calculateAverageAudioFeatures(audioFeatures);
    
    // Genre analysis (simplified - would need Spotify API for genres)
    const artistCounts = this.countArtists(tracks);
    const topArtists = Object.entries(artistCounts)
      .sort(([,a], [,b]) => (b as number) - (a as number))
      .slice(0, 10)
      .map(([artist, count]) => ({ artist, count }));
    
    // Energy and danceability distribution
    const energyDistribution = this.calculateDistribution(audioFeatures.map(f => f.energy));
    const danceabilityDistribution = this.calculateDistribution(audioFeatures.map(f => f.danceability));
    
    return {
      overview: {
        total_tracks: totalTracks,
        total_duration_ms: totalDuration,
        average_duration_ms: avgDuration,
        formatted_duration: this.formatDuration(totalDuration)
      },
      audio_features: {
        averages: avgFeatures,
        distributions: {
          energy: energyDistribution,
          danceability: danceabilityDistribution
        }
      },
      artists: {
        unique_artists: Object.keys(artistCounts).length,
        top_artists: topArtists
      },
      insights: this.generateInsights(avgFeatures, energyDistribution, danceabilityDistribution)
    };
  }
  
  private calculateAverageAudioFeatures(features: any[]): any {
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
    const averages: any = {};
    
    Object.keys(sums).forEach(key => {
      averages[key] = sums[key] / count;
    });
    
    return averages;
  }
  
  private countArtists(tracks: any[]): Record<string, number> {
    return tracks.reduce((acc, track) => {
      track.artists.forEach((artist: any) => {
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
  
  private generateInsights(avgFeatures: any, energyDist: any, danceabilityDist: any): string[] {
    const insights: string[] = [];
    
    if (avgFeatures.energy > 0.7) {
      insights.push('This playlist has high energy - great for workouts or parties!');
    } else if (avgFeatures.energy < 0.3) {
      insights.push('This playlist is quite relaxing - perfect for studying or background music.');
    }
    
    if (avgFeatures.danceability > 0.7) {
      insights.push('Very danceable tracks - this playlist will get people moving!');
    }
    
    if (avgFeatures.valence > 0.7) {
      insights.push('This playlist has a very positive and happy mood.');
    } else if (avgFeatures.valence < 0.3) {
      insights.push('This playlist has a more melancholic or serious tone.');
    }
    
    if (energyDist.high > 60) {
      insights.push('Most tracks are high energy - this is an intense playlist!');
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

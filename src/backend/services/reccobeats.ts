/**
 * Reccobeats integration — STUB / MOCK.
 *
 * This file appears to be a placeholder for a future Reccobeats API integration.
 * The real integration has NOT been implemented. All methods return mock data.
 *
 * Tech debt: docs/tech-debt-tracker.md item #9
 * Do not add api.spotify.com calls here — use services/spotify.ts instead.
 *
 * Before implementing the real integration, clarify:
 *   1. Is Reccobeats still the intended third-party service?
 *   2. What does the real API response shape look like?
 *   3. Should this merge with or replace the audio features from Spotify?
 */
// Mock Reccobeats service for testing
export interface ReccobeatsFeatures {
  tempo?: number;
  key?: number;
  mode?: number;
  danceability?: number;
  energy?: number;
  valence?: number;
  acousticness?: number;
  instrumentalness?: number;
  liveness?: number;
  speechiness?: number;
  loudness?: number;
  time_signature?: number;
}

export class ReccoBeatsService {
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async getTrackFeatures(_trackId: string): Promise<ReccobeatsFeatures> {
    // Mock implementation for testing
    if (process.env.ENVIRONMENT === 'test') {
      return {
        tempo: 120.0,
        key: 0,
        mode: 1,
        danceability: 0.8,
        energy: 0.7,
        valence: 0.6,
        acousticness: 0.2,
        instrumentalness: 0.1,
        liveness: 0.3,
        speechiness: 0.1,
        loudness: -8.0,
        time_signature: 4
      };
    }

    // Real implementation would call Reccobeats API
    throw new Error('Reccobeats API not implemented in test environment');
  }

  async getMultipleTrackFeatures(trackIds: string[]): Promise<Map<string, ReccobeatsFeatures>> {
    const features = new Map<string, ReccobeatsFeatures>();

    for (const trackId of trackIds) {
      const trackFeatures = await this.getTrackFeatures(trackId);
      features.set(trackId, trackFeatures);
    }

    return features;
  }
}

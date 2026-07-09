export interface AudioFeatureAverages {
  acousticness: number;
  danceability: number;
  energy: number;
  instrumentalness: number;
  liveness: number;
  loudness: number;
  speechiness: number;
  tempo: number;
  valence: number;
}

export interface ReccoBeatsAudioFeature extends AudioFeatureAverages {
  /** ReccoBeats UUID — not the Spotify track ID (Spotify ID is in `href`). */
  id: string;
  href: string;
  isrc?: string | null;
  key?: number;
  mode?: number;
}

export interface ReccoBeatsAudioFeaturesResponse {
  content: ReccoBeatsAudioFeature[];
}

export interface KeyModeDistribution {
  /** Bare pitch-class labels: `"C"`, `"C#"`, … `"B"` (not `"C major"`). ReccoBeats `key` 0–11 = Spotify pitch class (0 = C). */
  key_percentages: Record<string, number>;
  dominant_key: string;
  dominant_key_percentage: number;
  mode_percentages: { major: number; minor: number };
  dominant_mode: 'major' | 'minor';
}

export interface AudioFeatureSummary {
  track_count: number;
  averages: AudioFeatureAverages;
  key_mode_distribution?: KeyModeDistribution;
}

export interface PlaylistInsights {
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
  audio_features?: AudioFeatureSummary;
  insights: string[];
  reccobeats_metadata?: {
    isrc_available: number;
    popularity_min?: number;
    popularity_max?: number;
    retrieved_at: string;
  };
}

export interface AnalysisResult {
  job_id: string;
  playlist_id: string;
  user_id: string;
  status: string;
  computed_at: string;
  completed_at: string;
  overview?: PlaylistInsights['overview'];
  artists?: PlaylistInsights['artists'];
  genre_distribution?: PlaylistInsights['genre_distribution'];
  audio_features?: AudioFeatureSummary;
  insights?: string[];
  reccobeats_metadata?: PlaylistInsights['reccobeats_metadata'];
  errors: Array<{ source: string; message: string }>;
  schema_version: string;
}

export interface ReccoBeatsTrackMetadata {
  /** ReccoBeats UUID — not the Spotify track ID (Spotify ID is in `href` if present). */
  id: string;
  trackTitle: string;
  artists: Array<{ id: string; name: string; href: string }>;
  durationMs: number;
  isrc?: string;
  popularity?: number;
}

export interface ReccoBeatsTrackMetadataResponse {
  content: ReccoBeatsTrackMetadata[];
}

export interface CachedRawEnrichment {
  audio_features: ReccoBeatsAudioFeature[];
  track_metadata: ReccoBeatsTrackMetadata[];
  schema_version: string;
  cached_at: string;
  track_count: number;
}

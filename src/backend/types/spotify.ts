export interface SpotifyUser {
  id: string;
  display_name: string;
  email?: string;
  country?: string;
  images: SpotifyImage[];
}

export interface SpotifyImage {
  url: string;
  height: number | null;
  width: number | null;
}

export interface SpotifyPlaylist {
  id: string;
  name: string;
  description: string | null;
  public: boolean;
  collaborative: boolean;
  owner: SpotifyUser;
  tracks?: SpotifyPlaylistTracks;
  items?: SpotifyPlaylistItems;
  images: SpotifyImage[];
  external_urls: { spotify: string };
  uri: string;
}

export interface SpotifyPlaylistTracks {
  href: string;
  total: number;
  items: SpotifyPlaylistTrackItem[];
}

export interface SpotifyPlaylistItems {
  href?: string;
  total: number;
  items: SpotifyPlaylistTrackItem[];
}

export interface SpotifyPlaylistTrackItem {
  added_at?: string;
  added_by: SpotifyUser | null;
  track?: SpotifyTrack;
  item?: SpotifyTrack;
}

export interface SpotifyTrack {
  id: string;
  name: string;
  artists: SpotifyArtist[];
  album: SpotifyAlbum;
  duration_ms: number;
  explicit: boolean;
  popularity?: number;
  external_urls: { spotify: string };
  uri: string;
  preview_url: string | null;
}

export interface SpotifyArtist {
  id: string;
  name: string;
  external_urls: { spotify: string };
  uri: string;
}

export interface SpotifyAlbum {
  id: string;
  name: string;
  artists: SpotifyArtist[];
  images: SpotifyImage[];
  release_date: string;
  total_tracks: number;
  external_urls: { spotify: string };
  uri: string;
}

export interface SpotifyAudioFeatures {
  id: string;
  acousticness: number;
  danceability: number;
  energy: number;
  instrumentalness: number;
  liveness: number;
  loudness: number;
  speechiness: number;
  valence: number;
  tempo: number;
  mode: number;
  key: number;
  time_signature: number;
}

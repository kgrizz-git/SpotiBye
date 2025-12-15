"""Cache Explorer window for viewing and managing cached data."""

from __future__ import annotations

import time
import threading
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from spotify_playlist_exporter_v2.caching.persistent_cache import PersistentCache
from spotify_playlist_exporter_v2.caching.track_cache import get_cached_spotify_track
from spotify_playlist_exporter_v2.logging_config import logger


class CacheExplorerPopup(Popup):
    """Popup window for exploring cache contents with column-based navigation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = 'Cache Explorer'
        self.size_hint = (0.9, 0.9)
        self.auto_dismiss = False
        
        self.cache_data = {}
        self.filter_text = ""
        
        # Navigation state
        self.selected_playlist = None
        self.selected_track = None
        
        # Column widgets
        self.playlists_column = None
        self.tracks_column = None
        self.details_column = None
        self.features_column = None
        
        self.build_ui()
        self.load_cache_data()

    def build_ui(self) -> None:
        """Build the column-based cache explorer UI."""
        main_layout = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        # Header with search and controls
        header = self._create_header()
        main_layout.add_widget(header)
        
        # Columns container (grid layout for fixed column positions)
        self.columns_container = GridLayout(cols=4, spacing=dp(5), size_hint_y=1)
        
        # Create all 4 columns (some initially invisible)
        self.playlists_column = self._create_playlists_column()
        self.tracks_column = self._create_tracks_column()
        self.details_column = self._create_details_column()
        self.features_column = self._create_features_column()
        
        # Initially only show playlists column
        self.tracks_column.opacity = 0
        self.details_column.opacity = 0
        self.features_column.opacity = 0
        # Don't clear widgets here - they contain the essential content containers
        
        # Add all columns to maintain fixed positions
        self.columns_container.add_widget(self.playlists_column)
        self.columns_container.add_widget(self.tracks_column)
        self.columns_container.add_widget(self.details_column)
        self.columns_container.add_widget(self.features_column)
        
        main_layout.add_widget(self.columns_container)
        
        # Footer with close button
        footer = self._create_footer()
        main_layout.add_widget(footer)
        
        self.content = main_layout

    def _create_header(self) -> BoxLayout:
        """Create the header with search and refresh controls."""
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(10))
        
        # Search input
        search_label = Label(text='Search:', size_hint_x=None, width=dp(60), font_size=dp(14))
        header.add_widget(search_label)
        
        self.search_input = TextInput(
            multiline=False,
            size_hint_x=0.3,
            font_size=dp(14),
            hint_text='Filter cached playlists...',
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
        )
        self.search_input.bind(text=self.on_search_text)
        header.add_widget(self.search_input)
        
        # Refresh button
        refresh_btn = Button(
            text='Refresh',
            size_hint_x=None,
            width=dp(80),
            background_color=[0.3, 0.6, 0.3, 1],
            font_size=dp(14),
        )
        refresh_btn.bind(on_press=self.refresh_data)
        header.add_widget(refresh_btn)
        
        # Breadcrumb trail
        self.breadcrumb_label = Label(
            text='Playlists',
            font_size=dp(14),
            color=(0.7, 0.7, 0.7, 1),
            size_hint_x=0.4,
            halign='left'
        )
        header.add_widget(self.breadcrumb_label)
        
        return header

    def _create_footer(self) -> BoxLayout:
        """Create the footer with close button."""
        footer = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), padding=dp(5))
        
        # Spacer
        footer.add_widget(BoxLayout(size_hint_x=0.8))
        
        # Close button
        close_btn = Button(
            text='Close',
            size_hint_x=None,
            width=dp(80),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(14),
        )
        close_btn.bind(on_press=self.dismiss)
        footer.add_widget(close_btn)
        
        return footer

    def _create_playlists_column(self) -> BoxLayout:
        """Create the playlists column."""
        column = BoxLayout(orientation='vertical', size_hint_x=0.22, spacing=dp(2))
        
        # Column header
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30))
        header_label = Label(
            text='Playlists',
            font_size=dp(16),
            bold=True,
            color=(0.3, 0.8, 0.3, 1)
        )
        header.add_widget(header_label)
        column.add_widget(header)
        
        # Content scrollview
        scroll = ScrollView()
        self.playlists_content = GridLayout(
            cols=1,
            spacing=dp(2),
            size_hint_y=None,
            padding=dp(5)
        )
        self.playlists_content.bind(minimum_height=self.playlists_content.setter('height'))
        scroll.add_widget(self.playlists_content)
        column.add_widget(scroll)
        
        return column

    def _create_tracks_column(self) -> BoxLayout:
        """Create the tracks column."""
        column = BoxLayout(orientation='vertical', size_hint_x=0.22, spacing=dp(2))
        
        # Column header
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30))
        header_label = Label(
            text='Tracks',
            font_size=dp(16),
            bold=True,
            color=(0.3, 0.6, 0.8, 1)
        )
        header.add_widget(header_label)
        
        # Close button for column
        close_btn = Button(
            text='X',
            size_hint_x=None,
            width=dp(30),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(12)
        )
        close_btn.bind(on_press=lambda _: self.close_tracks_column())
        header.add_widget(close_btn)
        
        column.add_widget(header)
        
        # Content scrollview
        scroll = ScrollView()
        self.tracks_content = GridLayout(
            cols=1,
            spacing=dp(2),
            size_hint_y=None,
            padding=dp(5)
        )
        self.tracks_content.bind(minimum_height=self.tracks_content.setter('height'))
        scroll.add_widget(self.tracks_content)
        column.add_widget(scroll)
        
        return column

    def _create_details_column(self) -> BoxLayout:
        """Create the track details column."""
        column = BoxLayout(orientation='vertical', size_hint_x=0.22, spacing=dp(2))
        
        # Column header
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30))
        header_label = Label(
            text='Track Details',
            font_size=dp(16),
            bold=True,
            color=(0.8, 0.6, 0.3, 1)
        )
        header.add_widget(header_label)
        
        # Close button for column
        close_btn = Button(
            text='X',
            size_hint_x=None,
            width=dp(30),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(12)
        )
        close_btn.bind(on_press=lambda _: self.close_details_column())
        header.add_widget(close_btn)
        
        column.add_widget(header)
        
        # Content scrollview
        scroll = ScrollView()
        self.details_content = GridLayout(
            cols=1,
            spacing=dp(2),
            size_hint_y=None,
            padding=dp(5)
        )
        self.details_content.bind(minimum_height=self.details_content.setter('height'))
        scroll.add_widget(self.details_content)
        column.add_widget(scroll)
        
        return column

    def _create_features_column(self) -> BoxLayout:
        """Create the ReccoBeats features column."""
        column = BoxLayout(orientation='vertical', size_hint_x=0.22, spacing=dp(2))
        
        # Column header
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30))
        header_label = Label(
            text='Reccobeats Analysis',
            font_size=dp(16),
            bold=True,
            color=(0.8, 0.3, 0.8, 1)
        )
        header.add_widget(header_label)
        
        # Close button for column
        close_btn = Button(
            text='X',
            size_hint_x=None,
            width=dp(30),
            background_color=[0.8, 0.3, 0.3, 1],
            font_size=dp(12)
        )
        close_btn.bind(on_press=lambda _: self.close_features_column())
        header.add_widget(close_btn)
        
        column.add_widget(header)
        
        # Content scrollview
        scroll = ScrollView()
        self.features_content = GridLayout(
            cols=1,
            spacing=dp(2),
            size_hint_y=None,
            padding=dp(5)
        )
        self.features_content.bind(minimum_height=self.features_content.setter('height'))
        scroll.add_widget(self.features_content)
        column.add_widget(scroll)
        
        return column

    def load_cache_data(self) -> None:
        """Load cache data from persistent cache asynchronously."""
        try:
            # Show loading message in playlists column
            self.playlists_content.clear_widgets()
            loading_label = Label(
                text='Loading cache data...',
                font_size=dp(16),
                size_hint_y=None,
                height=dp(30)
            )
            self.playlists_content.add_widget(loading_label)
            
            # Load data in background thread
            threading.Thread(target=self._load_cache_data_worker, daemon=True).start()
            
        except Exception as exc:
            logger.error("Error starting cache data load: %s", exc)
            self.show_error(f"Error loading cache data: {exc}")

    def _load_cache_data_worker(self) -> None:
        """Worker thread for loading cache data."""
        try:
            # Load cache data
            cache = PersistentCache()
            cache_data = cache.get_detailed_cache_info()
            
            # Update UI on main thread
            Clock.schedule_once(lambda _: self._on_cache_data_loaded(cache_data))
            
        except Exception as exc:
            logger.error("Error loading cache data in worker: %s", exc)
            error_msg = f"Error loading cache data: {exc}"
            Clock.schedule_once(lambda _: self.show_error(error_msg))

    def _on_cache_data_loaded(self, cache_data: Dict[str, Any]) -> None:
        """Handle cache data loaded event and populate playlists column."""
        try:
            self.cache_data = cache_data
            self.populate_playlists_column()
        except Exception as exc:
            logger.error("Error handling cache data loaded: %s", exc)
            self.show_error(f"Error displaying cache data: {exc}")

    def populate_playlists_column(self) -> None:
        """Populate the playlists column with cached playlists."""
        self.playlists_content.clear_widgets()
        
        playlists = self.cache_data.get('playlists', [])
        if not playlists:
            no_data = Label(text='No cached playlists found', font_size=dp(14))
            self.playlists_content.add_widget(no_data)
            return
        
        # Filter playlists if search is active
        if self.filter_text:
            playlists = [p for p in playlists if self.filter_text.lower() in p.get('name', '').lower()]
        
        for playlist in playlists[:50]:  # Limit to 50 for performance
            playlist_widget = self._create_playlist_widget(playlist)
            self.playlists_content.add_widget(playlist_widget)

    def _create_playlist_widget(self, playlist: Dict[str, Any]) -> Button:
        """Create a clickable widget for a single playlist."""
        playlist_name = playlist.get('name', 'Unknown Playlist')
        tracks_count = playlist.get('tracks_count', 0)
        cached_time = datetime.fromtimestamp(playlist.get('cached_at', 0)).strftime('%Y-%m-%d %H:%M')
        size_mb = playlist.get('size_mb', 0)
        
        # Calculate truncation based on widget width (290px) and font size
        # Approximate character width at font size 11px
        char_width = dp(7)  # Rough estimate for monospace-like behavior
        max_chars = int(dp(280) / char_width)  # Leave some padding
        
        # Truncate long names based on calculated max length
        if len(playlist_name) > max_chars:
            playlist_name = playlist_name[:max_chars-3] + '...'
        
        text = f"{playlist_name}\n({tracks_count} tracks)\n{size_mb:.1f}MB • {cached_time}"
        
        btn = Button(
            text=text,
            size_hint_y=None,
            height=dp(60),
            background_color=[0.2, 0.4, 0.2, 1] if playlist == self.selected_playlist else [0.3, 0.3, 0.3, 1],
            font_size=dp(11),
            halign='left',
            padding=(dp(5), dp(5)),
            text_size=(dp(290), None)  # Constrain width for consistent alignment
        )
        btn.bind(on_press=lambda _: self.select_playlist(playlist))
        return btn

    def select_playlist(self, playlist: Dict[str, Any]) -> None:
        """Handle playlist selection - show tracks column."""
        self.selected_playlist = playlist
        self.selected_track = None
        
        # Update breadcrumb
        playlist_name = playlist.get('name', 'Unknown Playlist')
        self.breadcrumb_label.text = f"Playlists > {playlist_name}"
        
        # Show tracks column, hide details and features
        self.tracks_column.opacity = 1
        self.details_column.opacity = 0
        self.features_column.opacity = 0
        # Clear content, not the entire column structure
        self.details_content.clear_widgets()
        self.features_content.clear_widgets()
        
        # Populate tracks
        self.populate_tracks_column(playlist)
        
        # Update playlist button highlighting
        self.populate_playlists_column()

    def populate_tracks_column(self, playlist: Dict[str, Any]) -> None:
        """Populate the tracks column with tracks from selected playlist."""
        self.tracks_content.clear_widgets()
        
        playlist_id = playlist.get('playlist_id', '')
        user_id = playlist.get('user_id', '')
        
        try:
            # Get cached playlist tracks
            cache = PersistentCache()
            cached_data = cache.get_cached_playlist_tracks(playlist_id, user_id)
            
            # If no detailed track cache, try to get basic playlist data and extract tracks
            if not cached_data:
                basic_playlist_data = cache.get_cached_playlist_data(playlist_id, user_id)
                if basic_playlist_data and 'tracks' in basic_playlist_data:
                    # Create a basic track structure from playlist data
                    tracks = []
                    for track_item in basic_playlist_data['tracks'].get('items', []):
                        track = track_item.get('track', {})
                        if track:
                            basic_track = {
                                'id': track.get('id'),
                                'name': track.get('name'),
                                'artists': [artist.get('name') for artist in track.get('artists', [])],
                                'album': track.get('album', {}).get('name'),
                                'added_at': track_item.get('added_at'),
                                'spotify_cached': cache.get_cached_track_data(track.get('id'), 'spotify') is not None,
                                'reccobeats_cached': cache.get_cached_track_reccobeats(track.get('id')) is not None
                            }
                            tracks.append(basic_track)
                    
                    if tracks:
                        logger.info("Loaded %d tracks from basic playlist cache for %s", len(tracks), playlist_id)
                    else:
                        no_data = Label(text='No tracks found in playlist cache', font_size=dp(14))
                        self.tracks_content.add_widget(no_data)
                        return
                else:
                    no_data = Label(text='No cached tracks found for this playlist\n(Try opening playlist details first)', font_size=dp(14))
                    self.tracks_content.add_widget(no_data)
                    return
            else:
                tracks = cached_data.get('tracks', [])
            
            # Filter tracks if search is active
            if self.filter_text:
                tracks = [t for t in tracks if 
                         self.filter_text.lower() in t.get('name', '').lower() or
                         self.filter_text.lower() in t.get('id', '').lower()]
            
            for track in tracks[:100]:  # Limit to 100 for performance
                track_widget = self._create_track_widget(track)
                self.tracks_content.add_widget(track_widget)
                
        except Exception as exc:
            logger.error("Error loading playlist tracks: %s", exc)
            error_label = Label(text=f'Error loading tracks: {exc}', font_size=dp(14))
            self.tracks_content.add_widget(error_label)

    def _create_track_widget(self, track: Dict[str, Any]) -> Button:
        """Create a clickable widget for a single track using Button for simplicity."""
        # logger.debug("TRACK DEBUG: Basic track data keys: %s", list(track.keys()))
        track_name = track.get('name', 'Unknown Track')
        artists = track.get('artists', [])
        spotify_id = track.get('id', '')
        
        # Get full track data to include duration_ms from individual track cache
        full_track_data = get_cached_spotify_track(spotify_id)
        if full_track_data:
            # logger.debug("TRACK DEBUG: Full track data found with keys: %s", list(full_track_data.keys()))
            duration_ms = full_track_data.get('duration_ms', 0)
        else:
            # logger.debug("TRACK DEBUG: No full track data found for %s", spotify_id)
            duration_ms = 0
        
        spotify_cached = track.get('spotify_cached', False)
        reccobeats_cached = track.get('reccobeats_cached', False)
        
        # Format artists exactly like playlist details
        if artists:
            # Filter out None values and ensure all items are strings
            valid_artists = [str(artist) for artist in artists if artist is not None]
            artists_text = ', '.join(valid_artists[:2])
            if len(valid_artists) > 2:
                artists_text += '...'
        else:
            artists_text = 'Unknown Artist'
        
        # Format duration
        duration_text = ''
        # logger.debug("TRACK DEBUG: duration_ms=%s for track %s", duration_ms, track_name)
        if duration_ms:
            minutes = duration_ms // 60000
            seconds = (duration_ms % 60000) // 1000
            duration_text = f"{minutes}:{seconds:02d}"
            # logger.debug("TRACK DEBUG: formatted duration=%s", duration_text)
        else:
            # logger.debug("TRACK DEBUG: No duration data available")
            pass
        
        # Format sources
        sources = []
        if spotify_cached:
            sources.append('S')
        if reccobeats_cached:
            sources.append('R')
        sources_text = f"[{','.join(sources)}]" if sources else "[ ]"
        
        # Calculate truncation based on widget width (290px) and font size
        # Approximate character width at font size 11px
        char_width = dp(7)  # Rough estimate for monospace-like behavior
        max_chars = int(dp(280) / char_width)  # Leave some padding
        
        # Truncate names based on calculated max length
        if len(track_name) > max_chars:
            track_name = track_name[:max_chars-3] + '...'
        if len(artists_text) > max_chars:
            artists_text = artists_text[:max_chars-3] + '...'
        
        # Format exactly like playlist widgets: name, details, info
        text = f"{track_name}\n{artists_text}\n{duration_text} {sources_text}"
        
        btn = Button(
            text=text,
            size_hint_y=None,
            height=dp(60),  # Exactly same as playlist widgets
            background_color=[0.2, 0.4, 0.4, 1] if track == self.selected_track else [0.3, 0.3, 0.3, 1],
            font_size=dp(11),  # Exactly same as playlist widgets
            halign='left',    # Exactly same as playlist widgets
            padding=(dp(5), dp(5)),  # Exactly same as playlist widgets
            text_size=(dp(290), None)  # Constrain width for consistent alignment
        )
        btn.bind(on_press=lambda _: self.select_track(track))
        return btn

    def select_track(self, track: Dict[str, Any]) -> None:
        """Handle track selection - show details column."""
        self.selected_track = track
        
        # Debug logging for ReccoBeats cache status
        spotify_id = track.get('id', '')
        reccobeats_cached = track.get('reccobeats_cached', False)
        logger.debug("CACHE EXPLORER: Selected track %s - ReccoBeats cached: %s", spotify_id, reccobeats_cached)
        
        # Update breadcrumb
        track_name = track.get('name', 'Unknown Track')
        if len(track_name) > 20:
            track_name = track_name[:17] + '...'
        self.breadcrumb_label.text = f"Playlists > {self.selected_playlist.get('name', 'Unknown')} > {track_name}"
        
        # Show details and features columns
        self.details_column.opacity = 1
        self.features_column.opacity = 1
        
        # Populate details
        self.populate_details_column(track)
        
        # Update track button highlighting
        self.populate_tracks_column(self.selected_playlist)

    def populate_details_column(self, track: Dict[str, Any]) -> None:
        """Populate the details column with track information."""
        self.details_content.clear_widgets()
        
        track_name = track.get('name', 'Unknown Track')
        artists = track.get('artists', [])
        album = track.get('album', {})
        spotify_id = track.get('id', '')
        
        # Get full track data to include duration_ms from individual track cache
        full_track_data = get_cached_spotify_track(spotify_id)
        if full_track_data:
            duration_ms = full_track_data.get('duration_ms', 0)
        else:
            duration_ms = 0
        
        spotify_cached = track.get('spotify_cached', False)
        reccobeats_cached = track.get('reccobeats_cached', False)
        
        # Format duration
        duration_text = ''
        if duration_ms:
            minutes = duration_ms // 60000
            seconds = (duration_ms % 60000) // 1000
            duration_text = f"{minutes}:{seconds:02d}"
        
        # Create detail items
        details = [
            ("Track Name", track_name),
            ("Artists", ', '.join([str(artist) for artist in artists if artist is not None]) if artists else 'Unknown'),
            ("Album", album.get('name', 'Unknown') if isinstance(album, dict) else str(album)),
            ("Spotify ID", spotify_id),
            ("Duration", duration_text),
            ("Spotify Cached", "Yes" if spotify_cached else "No"),
            ("ReccoBeats Cached", "Yes" if reccobeats_cached else "No"),
        ]
        
        for label, value in details:
            detail_widget = self._create_detail_item(label, value)
            self.details_content.add_widget(detail_widget)
        
        # Always show features column (even if no ReccoBeats data)
        Clock.schedule_once(lambda _: self.show_features_column(track))

    def _create_detail_item(self, label: str, value: str) -> BoxLayout:
        """Create a detail item with label and value."""
        widget = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(5))
        
        label_widget = Label(
            text=f"{label}:",
            font_size=dp(12),
            bold=True,
            size_hint_x=None,
            width=dp(100),
            halign='left',
            color=(0.7, 0.7, 0.7, 1)
        )
        widget.add_widget(label_widget)
        
        value_widget = Label(
            text=value,
            font_size=dp(12),
            halign='left',
            text_size=(None, None)
        )
        widget.add_widget(value_widget)
        
        return widget

    def show_features_column(self, track: Dict[str, Any]) -> None:
        """Show the ReccoBeats features column."""
        # Features column already exists, just ensure it's visible
        if self.features_column.opacity == 0:
            self.features_column.opacity = 1
        
        # Populate features
        self.populate_features_column(track)

    def populate_features_column(self, track: Dict[str, Any]) -> None:
        """Populate the features column with ReccoBeats audio features."""
        self.features_content.clear_widgets()
        
        try:
            spotify_id = track.get('id', '')
            if not spotify_id:
                no_data = Label(text='No track ID available', font_size=dp(14))
                self.features_content.add_widget(no_data)
                return
            
            logger.debug("CACHE EXPLORER: Getting ReccoBeats data for track: %s", spotify_id)
            
            # Get cached track data
            cache = PersistentCache()
            track_data = cache.get_cached_track_reccobeats(spotify_id)
            logger.debug("CACHE EXPLORER: ReccoBeats data returned: %s", type(track_data))
            if track_data:
                logger.debug("CACHE EXPLORER: ReccoBeats data keys: %s", list(track_data.keys()))
            
            if not track_data:
                no_data = Label(text='No analysis available', font_size=dp(14))
                self.features_content.add_widget(no_data)
                return
            
            # ReccoBeats data has features directly in the dict, not under 'features' key
            features = track_data  # The entire dict contains the features
            logger.debug("CACHE EXPLORER: Features found: %s", features is not None)
            if features:
                logger.debug("CACHE EXPLORER: Feature keys: %s", list(features.keys()))
            
            if not features:
                no_data = Label(text='No analysis available', font_size=dp(14))
                self.features_content.add_widget(no_data)
                return
            
            # Display features
            feature_items = [
                ("Danceability", features.get('danceability', 0), "{:.3f}"),
                ("Energy", features.get('energy', 0), "{:.3f}"),
                ("Valence", features.get('valence', 0), "{:.3f}"),
                ("Tempo", features.get('tempo', 0), "{:.1f} BPM"),
                ("Acousticness", features.get('acousticness', 0), "{:.3f}"),
                ("Instrumentalness", features.get('instrumentalness', 0), "{:.3f}"),
                ("Liveness", features.get('liveness', 0), "{:.3f}"),
                ("Speechiness", features.get('speechiness', 0), "{:.3f}"),
                ("Key", features.get('key', 0), "{}"),
                ("Mode", "Major" if features.get('mode', 0) == 1 else "Minor", "{}"),
                ("Loudness", features.get('loudness', 0), "{:.1f} dB"),
            ]
            
            for feature_name, value, format_str in feature_items:
                feature_widget = self._create_feature_item(feature_name, value, format_str)
                self.features_content.add_widget(feature_widget)
                
        except Exception as exc:
            logger.error("Error loading ReccoBeats features: %s", exc)
            error_label = Label(text=f'Error loading features: {exc}', font_size=dp(14))
            self.features_content.add_widget(error_label)

    def _create_feature_item(self, name: str, value: Any, format_str: str) -> BoxLayout:
        """Create a feature item with name and formatted value."""
        widget = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(25), spacing=dp(5))
        
        name_widget = Label(
            text=f"{name}:",
            font_size=dp(12),
            bold=True,
            size_hint_x=None,
            width=dp(120),
            halign='left',
            color=(0.7, 0.7, 0.7, 1)
        )
        widget.add_widget(name_widget)
        
        formatted_value = format_str.format(value) if value is not None else "N/A"
        value_widget = Label(
            text=formatted_value,
            font_size=dp(12),
            halign='left',
            text_size=(None, None)
        )
        widget.add_widget(value_widget)
        
        return widget

    def close_tracks_column(self) -> None:
        """Close the tracks column."""
        self.tracks_column.opacity = 0
        # Clear content, not the entire column structure
        self.tracks_content.clear_widgets()
        self.selected_playlist = None
        self.close_details_column()
        self.close_features_column()
        self.breadcrumb_label.text = 'Playlists'
        self.populate_playlists_column()

    def close_details_column(self) -> None:
        """Close the details column."""
        self.details_column.opacity = 0
        # Clear content, not the entire column structure
        self.details_content.clear_widgets()
        self.selected_track = None
        self.close_features_column()
        if self.selected_playlist:
            playlist_name = self.selected_playlist.get('name', 'Unknown')
            self.breadcrumb_label.text = f"Playlists > {playlist_name}"

    def close_features_column(self) -> None:
        """Close the features column."""
        self.features_column.opacity = 0
        # Clear content, not the entire column structure
        self.features_content.clear_widgets()

    def refresh_data(self, *_args) -> None:
        """Refresh the cache data."""
        self.load_cache_data()

    def on_search_text(self, instance, value: str) -> None:
        """Handle search text changes."""
        self.filter_text = value.lower()
        if hasattr(self, 'cache_data') and self.cache_data:
            self.populate_playlists_column()

    def show_error(self, error_message: str) -> None:
        """Show an error message in the playlists column."""
        self.playlists_content.clear_widgets()
        
        error_label = Label(
            text=f'Error: {error_message}',
            font_size=dp(14),
            color=(0.8, 0.3, 0.3, 1),
            size_hint_y=None,
            height=dp(30)
        )
        self.playlists_content.add_widget(error_label)


__all__ = ["CacheExplorerPopup"]

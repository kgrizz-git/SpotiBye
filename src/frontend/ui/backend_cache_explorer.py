"""Backend Cache Explorer - Enhanced cache explorer with backend status."""

from __future__ import annotations

import threading
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.switch import Switch

from spotify_playlist_exporter_v2.ui.cache_explorer import CacheExplorerPopup
from spotify_playlist_exporter_v2.caching.persistent_cache import PersistentCache
from spotify_playlist_exporter_v2.logging_config import logger

try:
    from ..services.backend_client import BackendClient
    from ..config.backend_config import BackendConfig
    from ..caching.backend_cache import get_cache_manager
    BACKEND_AVAILABLE = True
except ImportError:
    BACKEND_AVAILABLE = False
    logger.warning("Backend components not available for backend cache status")


class BackendCacheExplorerPopup(Popup):
    """Enhanced cache explorer with backend cache status."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = 'Cache Explorer - Local & Backend'
        self.size_hint = (0.95, 0.9)
        self.auto_dismiss = False
        
        # Backend client for cache status
        self.backend_client = None
        self.backend_cache_status = None
        self.cache_manager = get_cache_manager() if BACKEND_AVAILABLE else None
        
        # UI components
        self.main_layout = None
        self.status_bar = None
        self.cache_explorer = None
        self.backend_status_label = None
        self.backend_switch = None
        
        self.build_ui()
        self.initialize_backend_client()
        self.populate_from_backend_local_cache()
        self.load_backend_cache_status()

    def build_ui(self) -> None:
        """Build the enhanced UI with backend status."""
        self.main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        
        # Status bar with backend toggle
        self.build_status_bar()
        
        # Main cache explorer (embed original)
        self.cache_explorer = CacheExplorerPopup()
        self.cache_explorer.size_hint = (1, 0.85)
        self.main_layout.add_widget(self.cache_explorer)
        
        self.add_widget(self.main_layout)

    def build_status_bar(self) -> None:
        """Build status bar with backend toggle."""
        status_layout = BoxLayout(
            orientation='horizontal', 
            size_hint_y=None, 
            height=dp(40),
            spacing=dp(10)
        )
        
        # Backend status label
        self.backend_status_label = Label(
            text='Backend: Checking...',
            size_hint_x=0.7,
            font_size=dp(12),
            color=(0.8, 0.8, 0.8, 1)
        )
        status_layout.add_widget(self.backend_status_label)
        
        # Backend toggle switch
        if BACKEND_AVAILABLE:
            toggle_layout = BoxLayout(
                orientation='horizontal',
                size_hint_x=0.3,
                spacing=dp(5)
            )
            
            toggle_label = Label(
                text='Backend:',
                size_hint_x=0.5,
                font_size=dp(12),
                color=(0.8, 0.8, 0.8, 1)
            )
            toggle_layout.add_widget(toggle_label)
            
            self.backend_switch = Switch(
                size_hint_x=0.5,
                active=False
            )
            self.backend_switch.bind(active=self.on_backend_toggle)
            toggle_layout.add_widget(self.backend_switch)
            
            status_layout.add_widget(toggle_layout)
        
        # Refresh button
        refresh_btn = Button(
            text='Refresh',
            size_hint_x=None,
            width=dp(80),
            font_size=dp(12)
        )
        refresh_btn.bind(on_press=self.refresh_backend_status)
        status_layout.add_widget(refresh_btn)
        
        self.status_bar = status_layout
        self.main_layout.add_widget(self.status_bar)

    def initialize_backend_client(self) -> None:
        """Initialize backend client if available."""
        if not BACKEND_AVAILABLE:
            self.backend_status_label.text = 'Backend: Not Available'
            return
            
        try:
            config = BackendConfig()
            self.backend_client = BackendClient(config.backend_url)
            self.backend_status_label.text = 'Backend: Connected'
            self.backend_switch.active = True
        except Exception as exc:
            logger.error("Failed to initialize backend client: %s", exc)
            self.backend_status_label.text = 'Backend: Connection Failed'

    def load_backend_cache_status(self) -> None:
        """Load backend cache status asynchronously."""
        if not self.backend_client or not hasattr(self.backend_client, 'get_cache_status'):
            self.update_backend_status_from_local_cache()
            return
            
        def load_status():
            try:
                # This would be a new endpoint in the backend
                status = self.backend_client.get_cache_status()
                self.backend_cache_status = status
                
                # Update UI on main thread
                Clock.schedule_once(self.update_backend_status_display)
                
            except Exception as exc:
                logger.error("Failed to load backend cache status: %s", exc)
                Clock.schedule_once(lambda dt: self.update_backend_status_from_local_cache())

        # Run in background thread
        threading.Thread(target=load_status, daemon=True).start()

    def update_backend_status_from_local_cache(self, *_args) -> None:
        """Fallback status using local backend cache manager stats."""
        if not self.cache_manager:
            self.backend_status_label.text = 'Backend: No cache manager'
            return

        stats = self.cache_manager.get_cache_stats()
        total_files = int(stats.get('total_files', 0) or 0)
        playlists = int(stats.get('playlists_count', 0) or 0)
        tracks = int(stats.get('tracks_count', 0) or 0)
        size_mb = float(stats.get('total_size_mb', 0) or 0)
        self.backend_status_label.text = (
            f'Backend Local Cache: {size_mb:.1f}MB, {total_files} files, '
            f'{playlists} playlists, {tracks} track entries'
        )

    def populate_from_backend_local_cache(self) -> None:
        """Populate embedded explorer using backend cache data when legacy cache is empty."""
        if not self.cache_manager or not self.cache_explorer:
            return

        cached_playlists = self.cache_manager.get_cached_playlists() or []
        if not cached_playlists:
            return

        existing_playlists = self.cache_explorer.cache_data.get('playlists', []) if self.cache_explorer.cache_data else []
        if existing_playlists:
            return

        now_ts = datetime.now().timestamp()
        mapped = []
        for playlist in cached_playlists:
            mapped.append({
                'cache_key': f"backend_{playlist.get('id', 'unknown')}",
                'playlist_id': playlist.get('id', ''),
                'user_id': playlist.get('owner', {}).get('id', ''),
                'name': playlist.get('name', 'Unknown Playlist'),
                'tracks_count': playlist.get('tracks', {}).get('total', 0),
                'cached_at': now_ts,
                'size_mb': 0.0,
            })

        self.cache_explorer.cache_data = {
            'summary': self.cache_manager.get_cache_stats(),
            'playlists': mapped,
            'tracks': [],
            'images': [],
            'analysis': [],
        }
        self.cache_explorer.populate_playlists_column()

    def update_backend_status_display(self, dt) -> None:
        """Update backend status display."""
        if not self.backend_cache_status:
            self.backend_status_label.text = 'Backend: No Data'
            return
            
        status = self.backend_cache_status
        hit_rate = status.get('hit_rate', 0)
        cache_size = status.get('cache_size_mb', 0)
        max_size = status.get('max_cache_size_mb', 0)
        
        status_text = f'Backend: {hit_rate:.1f}% hit rate, {cache_size:.1f}MB/{max_size:.1f}MB'
        self.backend_status_label.text = status_text

    def update_backend_error(self, error_msg: str) -> None:
        """Update backend status with error."""
        self.backend_status_label.text = f'Backend: Error - {error_msg[:30]}...'

    def on_backend_toggle(self, switch, value) -> None:
        """Handle backend toggle switch."""
        if value:
            self.initialize_backend_client()
            self.load_backend_cache_status()
        else:
            self.backend_client = None
            self.backend_cache_status = None
            self.backend_status_label.text = 'Backend: Disabled'

    def refresh_backend_status(self, button) -> None:
        """Refresh backend cache status."""
        self.backend_status_label.text = 'Backend: Refreshing...'
        self.load_backend_cache_status()

    def show_backend_details(self) -> None:
        """Show detailed backend cache information in a popup."""
        if not self.backend_cache_status:
            return
            
        details_popup = Popup(
            title='Backend Cache Details',
            size_hint=(0.6, 0.6),
            auto_dismiss=True
        )
        
        details_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        
        # Create details text
        status = self.backend_cache_status
        details_text = f"""
Backend Cache Status:
• Hit Rate: {status.get('hit_rate', 0):.1f}%
• Cache Size: {status.get('cache_size_mb', 0):.1f} MB
• Max Size: {status.get('max_cache_size_mb', 0):.1f} MB
• Total Requests: {status.get('total_requests', 0)}
• Cache Hits: {status.get('cache_hits', 0)}
• Cache Misses: {status.get('cache_misses', 0)}
• Last Updated: {status.get('last_updated', 'Unknown')}

Cache Types:
• Playlists: {status.get('cached_playlists', 0)} items
• Tracks: {status.get('cached_tracks', 0)} items
• Analysis: {status.get('cached_analysis', 0)} items
        """.strip()
        
        details_label = Label(
            text=details_text,
            font_size=dp(12),
            text_size=(dp(400), None),
            halign='left',
            valign='top'
        )
        
        close_btn = Button(
            text='Close',
            size_hint_y=None,
            height=dp(40)
        )
        close_btn.bind(on_press=details_popup.dismiss)
        
        details_layout.add_widget(details_label)
        details_layout.add_widget(close_btn)
        details_popup.add_widget(details_layout)
        details_popup.open()

"""Cached AsyncImage component for efficient playlist cover loading."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Optional

import requests
from kivy.cache import Cache
from kivy.core.image import Image as CoreImage
from kivy.properties import StringProperty
from kivy.uix.image import AsyncImage
from kivy.clock import Clock

from ..caching.persistent_cache import persistent_cache
from ..logging_config import logger


class CachedAsyncImage(AsyncImage):
    """AsyncImage with local caching support for improved performance."""
    
    # Custom property to track the original URL
    original_url = StringProperty('')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._is_loading = False
        self._load_thread = None
        self._cache_check_complete = False
        
        # Bind to source property changes
        self.bind(source=self._on_source_change)
    
    def _on_source_change(self, instance, value):
        """Handle source property changes."""
        if value and not self._cache_check_complete:
            self.original_url = value
            self._load_with_cache()
    
    def _load_with_cache(self):
        """Load image with cache support."""
        if not self.original_url or self._is_loading:
            return
        
        self._is_loading = True
        self._cache_check_complete = True
        
        # Check cache first (in background thread)
        self._load_thread = threading.Thread(
            target=self._check_and_load_image,
            daemon=True
        )
        self._load_thread.start()
    
    def _check_and_load_image(self):
        """Check cache and load image in background thread."""
        try:
            # Check if image is already cached locally
            cached_path = persistent_cache.get_cached_image_path(self.original_url)
            
            if cached_path and os.path.exists(cached_path):
                # Use cached image
                logger.debug("Using cached image: %s", self.original_url)
                Clock.schedule_once(lambda dt: self._load_from_local(cached_path))
            else:
                # Download and cache image
                logger.debug("Downloading and caching image: %s", self.original_url)
                self._download_and_cache_image()
                
        except Exception as exc:
            logger.warning("Error in cache check for %s: %s", self.original_url, exc)
            # Fallback to regular AsyncImage loading
            Clock.schedule_once(lambda dt: self._fallback_to_network())
    
    def _download_and_cache_image(self):
        """Download image from network and cache it locally."""
        try:
            response = requests.get(self.original_url, timeout=10)
            response.raise_for_status()
            
            # Cache the image data
            cached_path = persistent_cache.cache_image(self.original_url, response.content)
            
            if cached_path:
                # Load from cached path
                Clock.schedule_once(lambda dt: self._load_from_local(cached_path))
            else:
                # Fallback to network if caching failed
                Clock.schedule_once(lambda dt: self._fallback_to_network())
                
        except Exception as exc:
            logger.warning("Error downloading image %s: %s", self.original_url, exc)
            Clock.schedule_once(lambda dt: self._fallback_to_network())
    
    def _load_from_local(self, local_path: str):
        """Load image from local cached file."""
        try:
            if os.path.exists(local_path):
                # Update source to local file
                self.source = local_path
                logger.debug("Loaded cached image from: %s", local_path)
            else:
                # File doesn't exist, fallback to network
                self._fallback_to_network()
        except Exception as exc:
            logger.warning("Error loading local image %s: %s", local_path, exc)
            self._fallback_to_network()
    
    def _fallback_to_network(self):
        """Fallback to regular AsyncImage network loading."""
        try:
            # Reset to original URL and let AsyncImage handle it
            self.source = self.original_url
            logger.debug("Fallback to network loading: %s", self.original_url)
        except Exception as exc:
            logger.warning("Error in network fallback: %s", exc)
        finally:
            self._is_loading = False
    
    def reload_with_cache(self):
        """Reload the image, checking cache again."""
        self._cache_check_complete = False
        self._is_loading = False
        if self.original_url:
            self._load_with_cache()
    
    def on_touch_down(self, touch):
        """Handle touch events - reload cache on long press for debugging."""
        if self.collide_point(*touch.pos):
            # Optional: Add long press to reload cache for debugging
            pass
        return super().on_touch_down(touch)

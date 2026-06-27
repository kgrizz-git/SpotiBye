"""Unit tests for backend cache explorer functionality."""

from __future__ import annotations

import os
import platform
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# Test the backend cache explorer components
backend_available = False
BackendCacheExplorerPopup: Any = None
CacheExplorerAdapter: Any = None
create_cache_explorer: Any = None
try:
    from ..ui.backend_cache_explorer import BackendCacheExplorerPopup as _BackendCacheExplorerPopup
    from ..screens.cache_explorer_adapter import (
        CacheExplorerAdapter as _CacheExplorerAdapter,
    )
    from ..screens.cache_explorer_adapter import (
        create_cache_explorer as _create_cache_explorer,
    )

    BackendCacheExplorerPopup = _BackendCacheExplorerPopup
    CacheExplorerAdapter = _CacheExplorerAdapter
    create_cache_explorer = _create_cache_explorer
    backend_available = True
except ImportError:
    try:
        from src.frontend.ui.backend_cache_explorer import BackendCacheExplorerPopup as _BackendCacheExplorerPopup
        from src.frontend.screens.cache_explorer_adapter import (
            CacheExplorerAdapter as _CacheExplorerAdapter,
        )
        from src.frontend.screens.cache_explorer_adapter import (
            create_cache_explorer as _create_cache_explorer,
        )

        BackendCacheExplorerPopup = _BackendCacheExplorerPopup
        CacheExplorerAdapter = _CacheExplorerAdapter
        create_cache_explorer = _create_cache_explorer
        backend_available = True
    except ImportError:
        pass


def _kivy_display_available() -> bool:
    """Return True only when a real kivy window can be created.

    Instantiating kivy widgets (Popup, Switch, etc.) requires SDL2 to initialize
    a window. On headless CI runners there is no display server, so SDL2 calls
    sys.exit() instead of raising ImportError. Tests that construct kivy widgets
    must be skipped in those environments.
    """
    if os.environ.get("KIVY_WINDOW") in ("headless", "mock"):
        return False
    if platform.system() == "Linux":
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return False
    return True


KIVY_DISPLAY_AVAILABLE = _kivy_display_available()


class TestBackendCacheExplorer(unittest.TestCase):
    """Test backend cache explorer functionality."""

    mock_client: Mock | None = None

    def setUp(self):
        """Set up test fixtures."""
        if not backend_available:
            self.skipTest("Backend components not available")
        if not KIVY_DISPLAY_AVAILABLE:
            self.skipTest("Kivy window not available in this environment")

        # Mock backend client
        self.mock_client = Mock()
        self.mock_client.get_cache_status.return_value = {
            "hit_rate": 85.5,
            "cache_size_mb": 125.3,
            "max_cache_size_mb": 500.0,
            "total_requests": 1247,
            "cache_hits": 1066,
            "cache_misses": 181,
            "last_updated": "2025-12-14T23:40:00Z",
            "cached_playlists": 25,
            "cached_tracks": 1247,
            "cached_analysis": 18,
        }

    @patch("src.frontend.ui.backend_cache_explorer.resolve_startup_backend_url")
    @patch("src.frontend.ui.backend_cache_explorer.BackendClient")
    def test_backend_cache_explorer_initialization(
        self, mock_client_class, mock_backend_url
    ):
        """Test backend cache explorer initialization."""
        mock_backend_url.return_value = "http://test-backend.com"
        mock_client_class.return_value = self.mock_client

        explorer = BackendCacheExplorerPopup()

        self.assertIsNotNone(explorer)
        self.assertEqual(explorer.title, "Cache Explorer - Local & Backend")
        self.assertIsNotNone(explorer.backend_client)
        self.assertTrue(explorer.backend_switch.active)

    @patch("src.frontend.ui.backend_cache_explorer.resolve_startup_backend_url")
    def test_backend_cache_explorer_no_backend(self, mock_backend_url):
        """Test backend cache explorer when backend not available."""
        mock_backend_url.side_effect = Exception("Backend not available")

        explorer = BackendCacheExplorerPopup()

        self.assertIsNone(explorer.backend_client)
        self.assertFalse(
            explorer.backend_switch.active if explorer.backend_switch else True
        )

    def test_backend_cache_status_display(self):
        """Test backend cache status display update."""
        with patch(
            "src.frontend.ui.backend_cache_explorer.resolve_startup_backend_url"
        ) as mock_backend_url, patch(
            "src.frontend.ui.backend_cache_explorer.BackendClient"
        ) as mock_client_class:
            mock_backend_url.return_value = "http://test-backend.com"
            mock_client_class.return_value = self.mock_client

            explorer = BackendCacheExplorerPopup()
            explorer.backend_cache_status = (
                self.mock_client.get_cache_status.return_value
            )

            # Test status display update
            explorer.update_backend_status_display(None)

            expected_text = "Backend: 85.5% hit rate, 125.3MB/500.0MB"
            self.assertEqual(explorer.backend_status_label.text, expected_text)

    def test_backend_toggle_functionality(self):
        """Test backend toggle switch functionality."""
        with patch(
            "src.frontend.ui.backend_cache_explorer.resolve_startup_backend_url"
        ) as mock_backend_url, patch(
            "src.frontend.ui.backend_cache_explorer.BackendClient"
        ) as mock_client_class:
            mock_backend_url.return_value = "http://test-backend.com"
            mock_client_class.return_value = self.mock_client

            explorer = BackendCacheExplorerPopup()

            # Test turning off backend
            explorer.on_backend_toggle(explorer.backend_switch, False)
            self.assertIsNone(explorer.backend_client)
            self.assertEqual(explorer.backend_status_label.text, "Backend: Disabled")

            # Test turning on backend
            explorer.on_backend_toggle(explorer.backend_switch, True)
            self.assertIsNotNone(explorer.backend_client)

    def test_backend_details_popup(self):
        """Test backend details popup functionality."""
        with patch(
            "src.frontend.ui.backend_cache_explorer.resolve_startup_backend_url"
        ) as mock_backend_url, patch(
            "src.frontend.ui.backend_cache_explorer.BackendClient"
        ) as mock_client_class, patch(
            "src.frontend.ui.backend_cache_explorer.Popup"
        ) as mock_popup_class:
            mock_backend_url.return_value = "http://test-backend.com"
            mock_client_class.return_value = self.mock_client
            mock_popup = Mock()
            mock_popup_class.return_value = mock_popup

            explorer = BackendCacheExplorerPopup()
            explorer.backend_cache_status = (
                self.mock_client.get_cache_status.return_value
            )

            explorer.show_backend_details()

            # Verify popup was created and opened
            mock_popup_class.assert_called_once()
            mock_popup.open.assert_called_once()


class TestCacheExplorerAdapter(unittest.TestCase):
    """Test cache explorer adapter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        if not backend_available:
            self.skipTest("Backend components not available")

    @patch("src.frontend.screens.cache_explorer_adapter.resolve_startup_backend_url")
    @patch("src.frontend.screens.cache_explorer_adapter.BackendCacheExplorerPopup")
    def test_adapter_with_backend_available(
        self, mock_backend_explorer, mock_backend_url
    ):
        """Test adapter when backend is available."""
        mock_backend_url.return_value = "http://test-backend.com"
        mock_explorer = Mock()
        mock_backend_explorer.return_value = mock_explorer

        adapter = CacheExplorerAdapter()
        explorer = adapter.get_cache_explorer()

        self.assertTrue(adapter.is_backend_enabled())
        mock_backend_explorer.assert_called_once()
        self.assertEqual(explorer, mock_explorer)

    @patch("src.frontend.screens.cache_explorer_adapter.resolve_startup_backend_url")
    @patch("src.frontend.screens.cache_explorer_adapter.CacheExplorerPopup")
    def test_adapter_fallback_to_standard(
        self, mock_standard_explorer, mock_backend_url
    ):
        """Test adapter fallback to standard cache explorer."""
        mock_backend_url.side_effect = Exception("Backend not available")
        mock_explorer = Mock()
        mock_standard_explorer.return_value = mock_explorer

        adapter = CacheExplorerAdapter()
        explorer = adapter.get_cache_explorer()

        self.assertFalse(adapter.is_backend_enabled())
        mock_standard_explorer.assert_called_once()
        self.assertEqual(explorer, mock_explorer)

    def test_adapter_cache_status_info(self):
        """Test adapter cache status information."""
        with patch(
            "src.frontend.screens.cache_explorer_adapter.resolve_startup_backend_url"
        ) as mock_backend_url:
            mock_backend_url.return_value = "http://test-backend.com"

            adapter = CacheExplorerAdapter()
            info = adapter.get_cache_status_info()

            self.assertTrue(info["local_cache"])
            self.assertTrue(info["backend_cache"])
            self.assertEqual(info["backend_url"], "http://test-backend.com")


class TestCreateCacheExplorer(unittest.TestCase):
    """Test cache explorer creation function."""

    def setUp(self):
        """Set up test fixtures."""
        if not backend_available:
            self.skipTest("Backend components not available")

    @patch("src.frontend.screens.cache_explorer_adapter.get_cache_explorer_adapter")
    def test_create_cache_explorer_function(self, mock_get_adapter):
        """Test create_cache_explorer function."""
        mock_adapter = Mock()
        mock_explorer = Mock()
        mock_adapter.get_cache_explorer.return_value = mock_explorer
        mock_get_adapter.return_value = mock_adapter

        explorer = create_cache_explorer()

        mock_get_adapter.assert_called_once()
        mock_adapter.get_cache_explorer.assert_called_once()
        self.assertEqual(explorer, mock_explorer)


class TestCacheExplorerIntegration(unittest.TestCase):
    """Integration tests for cache explorer with backend."""

    def setUp(self):
        """Set up test fixtures."""
        if not backend_available:
            self.skipTest("Backend components not available")
        if not KIVY_DISPLAY_AVAILABLE:
            self.skipTest("Kivy window not available in this environment")

    @patch("src.frontend.ui.backend_cache_explorer.resolve_startup_backend_url")
    @patch("src.frontend.ui.backend_cache_explorer.BackendClient")
    def test_full_backend_status_flow(self, mock_client_class, mock_backend_url):
        """Test complete backend status flow."""
        # Setup mocks
        mock_backend_url.return_value = "http://test-backend.com"

        mock_client = Mock()
        mock_client.get_cache_status.return_value = {
            "hit_rate": 92.3,
            "cache_size_mb": 250.7,
            "max_cache_size_mb": 500.0,
            "total_requests": 2500,
            "cache_hits": 2308,
            "cache_misses": 192,
            "last_updated": "2025-12-14T23:40:00Z",
            "cached_playlists": 50,
            "cached_tracks": 2500,
            "cached_analysis": 35,
        }
        mock_client_class.return_value = mock_client

        # Create explorer and test flow
        explorer = BackendCacheExplorerPopup()

        # Simulate backend status loading
        explorer.backend_client = mock_client
        explorer.backend_cache_status = mock_client.get_cache_status.return_value

        # Test status display
        explorer.update_backend_status_display(None)

        expected_text = "Backend: 92.3% hit rate, 250.7MB/500.0MB"
        self.assertEqual(explorer.backend_status_label.text, expected_text)

        # Test details popup
        with patch("src.frontend.ui.backend_cache_explorer.Popup") as mock_popup_class:
            mock_popup = Mock()
            mock_popup_class.return_value = mock_popup

            explorer.show_backend_details()

            mock_popup_class.assert_called_once()
            mock_popup.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()

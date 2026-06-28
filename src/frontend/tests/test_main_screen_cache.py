"""Tests for FL-1 (clear_file, clear_cache_glob) and FL-9 (clear_all_cache).

Regression test for the env-hash-prefix-only behavior of clear_cache:
default clear_cache must NOT delete backend_token_*.json (auth) or
backend_selection.json (config).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


# Stub out kivy.uix.popup before importing the screen module, so the
# Popup() calls inside clear_all_cache do not try to construct a real
# Kivy window during tests.
_FAKE_POPUP = MagicMock()
sys.modules.setdefault("kivy.uix.popup", MagicMock(Popup=_FAKE_POPUP))

from ..caching.backend_cache import BackendCacheManager  # noqa: E402


class TestCacheClearEnvHashScoped:
    """FL-1 + FL-9: default clear_cache preserves auth + selection files."""

    def _make_manager(self, tmp_path: Path, backend_url: str) -> BackendCacheManager:
        client = MagicMock()
        client.base_url = backend_url
        manager = BackendCacheManager(client)
        # Override cache_dir to the test's tmp_path.
        manager.cache_dir = tmp_path
        env_hash = manager._hash_backend_url(backend_url)
        manager.token_cache_path = tmp_path / f"backend_token_{env_hash}.json"
        return manager

    def test_default_clear_preserves_auth_token(self, tmp_path):
        # Set up: an env-hash-prefixed data file, the auth token, and the
        # backend selection file.
        backend_url = "http://localhost:8787"
        manager = self._make_manager(tmp_path, backend_url)
        manager.token_cache_path.write_text(json.dumps({"access_token": "x"}))

        env_hash = manager._hash_backend_url(backend_url)

        data_file = tmp_path / f"{env_hash}_playlists.json"
        data_file.write_text(json.dumps([{"id": "1"}]))
        selection_file = tmp_path / "backend_selection.json"
        selection_file.write_text(json.dumps({"url": backend_url}))

        # Act
        manager.clear_cache(None)

        # Assert: data file gone, auth + selection preserved
        assert not data_file.exists(), "data file should be cleared"
        assert (
            manager.token_cache_path.exists()
        ), "auth token should NOT be deleted by clear_cache"
        assert (
            selection_file.exists()
        ), "backend_selection.json should NOT be deleted by clear_cache"

    def test_clear_file_removes_env_hashed_path(self, tmp_path):
        backend_url = "http://localhost:8787"
        manager = self._make_manager(tmp_path, backend_url)
        env_hash = manager._hash_backend_url(backend_url)
        data_file = tmp_path / f"{env_hash}_playlists.json"
        data_file.write_text(json.dumps([{"id": "1"}]))

        # Act
        manager.clear_file("playlists.json")

        # Assert
        assert not data_file.exists()

    def test_clear_file_missing_is_silent(self, tmp_path):
        backend_url = "http://localhost:8787"
        manager = self._make_manager(tmp_path, backend_url)
        # Act + Assert: should not raise
        manager.clear_file("nonexistent.json")

    def test_clear_cache_glob_matches_env_hashed_files(self, tmp_path):
        backend_url = "http://localhost:8787"
        manager = self._make_manager(tmp_path, backend_url)
        env_hash = manager._hash_backend_url(backend_url)

        (tmp_path / f"{env_hash}_tracks_1.json").write_text("[]")
        (tmp_path / f"{env_hash}_tracks_2.json").write_text("[]")
        (tmp_path / f"{env_hash}_analysis_1.json").write_text("[]")

        # Act
        manager.clear_cache_glob("tracks_*.json")

        # Assert
        assert not (tmp_path / f"{env_hash}_tracks_1.json").exists()
        assert not (tmp_path / f"{env_hash}_tracks_2.json").exists()
        assert (tmp_path / f"{env_hash}_analysis_1.json").exists()


class TestClearAllCacheCallsClear:
    """FL-9: clear_all_cache must invoke cache_manager.clear_cache.

    The function previously showed a 'Cache Cleared' success popup but
    never actually called any cache-clearing method.
    """

    def _patch_kivy_widgets(self):
        return (
            patch("src.frontend.screens.main_screen_cache.Popup"),
            patch("src.frontend.screens.main_screen_cache.Label"),
        )

    def test_clear_all_cache_invokes_clear(self):
        from src.frontend.screens import main_screen_cache

        screen = MagicMock()
        screen.backend_adapter = MagicMock()
        popup = MagicMock()

        with patch.object(main_screen_cache, "Popup") as MockPopup, patch.object(
            main_screen_cache, "Label"
        ):
            MockPopup.return_value = MagicMock()
            main_screen_cache.clear_all_cache(screen, popup)

        popup.dismiss.assert_called_once()
        screen.backend_adapter.cache_manager.clear_cache.assert_called_once_with(None)
        assert screen.status_label.text == "Clearing cache..."

    def test_clear_all_cache_no_backend_adapter_shows_error(self):
        from src.frontend.screens import main_screen_cache

        screen = MagicMock()
        screen.backend_adapter = None
        popup = MagicMock()

        with patch.object(main_screen_cache, "Popup") as MockPopup, patch.object(
            main_screen_cache, "Label"
        ):
            MockPopup.return_value = MagicMock()
            main_screen_cache.clear_all_cache(screen, popup)

        # The error popup should have been constructed
        MockPopup.assert_called_once()

    def test_clear_all_cache_handles_clear_cache_exception(self):
        from src.frontend.screens import main_screen_cache

        screen = MagicMock()
        screen.backend_adapter = MagicMock()
        screen.backend_adapter.cache_manager.clear_cache.side_effect = OSError(
            "disk error"
        )
        popup = MagicMock()

        with patch.object(main_screen_cache, "Popup"), patch.object(
            main_screen_cache, "Label"
        ):
            main_screen_cache.clear_all_cache(screen, popup)

        # status_label should reflect the error
        assert "Error clearing cache" in screen.status_label.text

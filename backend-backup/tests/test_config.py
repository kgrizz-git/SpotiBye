"""Tests for configuration settings."""

from __future__ import annotations

import os
import pytest
from pathlib import Path

from src.spotibye_backend.config import Settings, get_settings


class TestSettings:
    """Test Settings class."""
    
    def test_default_settings(self) -> None:
        """Test default settings values."""
        # Temporarily rename the .env file to avoid loading it
        import os
        env_file = "/Users/kevingrizzard/CascadeProjects/SpotiBye/backend/.env"
        backup_file = "/Users/kevingrizzard/CascadeProjects/SpotiBye/backend/.env.backup"
        
        try:
            if os.path.exists(env_file):
                os.rename(env_file, backup_file)
            
            # Create temporary .env file for testing
            env_content = """
SPOTIPY_CLIENT_ID=test_client_id
SPOTIPY_CLIENT_SECRET=test_client_secret
SECRET_KEY=test_secret_key
"""
            
            env_file_test = Path("/tmp/test_env")
            env_file_test.write_text(env_content)
            
            settings = Settings(_env_file=str(env_file_test))
            
            assert settings.SPOTIPY_CLIENT_ID == "test_client_id"
            assert settings.SPOTIPY_CLIENT_SECRET == "test_client_secret"
            assert settings.SECRET_KEY == "test_secret_key"
            assert settings.HOST == "0.0.0.0"
            assert settings.PORT == 8000
            assert settings.DEBUG is False
            assert settings.ALGORITHM == "HS256"
            assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
            
        finally:
            env_file_test.unlink(missing_ok=True)
            # Restore .env file
            if os.path.exists(backup_file):
                os.rename(backup_file, env_file)
    
    def test_missing_required_settings(self) -> None:
        """Test validation of required settings."""
        # Temporarily rename the .env file to avoid loading it
        import os
        env_file = "/Users/kevingrizzard/CascadeProjects/SpotiBye/backend/.env"
        backup_file = "/Users/kevingrizzard/CascadeProjects/SpotiBye/backend/.env.backup"
        
        try:
            if os.path.exists(env_file):
                os.rename(env_file, backup_file)
            
            with pytest.raises(ValueError, match="SECRET_KEY"):
                Settings(_env_file="/nonexistent")
        finally:
            # Restore .env file
            if os.path.exists(backup_file):
                os.rename(backup_file, env_file)
    
    def test_production_secret_key_validation(self) -> None:
        """Test secret key validation in production."""
        env_content = """
SPOTIPY_CLIENT_ID=test_client_id
SPOTIPY_CLIENT_SECRET=test_client_secret
SECRET_KEY=test-secret-key-for-development-only
DEBUG=false
"""
        
        env_file = Path("/tmp/test_env_prod")
        env_file.write_text(env_content)
        
        try:
            with pytest.raises(ValueError, match="SECRET_KEY must be set for production"):
                Settings(_env_file=str(env_file))
        finally:
            env_file.unlink(missing_ok=True)
    
    def test_development_secret_key_warning(self) -> None:
        """Test secret key warning in development."""
        env_content = """
SPOTIPY_CLIENT_ID=test_client_id
SPOTIPY_CLIENT_SECRET=test_client_secret
SECRET_KEY=test-secret-key-for-development-only
DEBUG=true
"""
        
        env_file = Path("/tmp/test_env_dev")
        env_file.write_text(env_content)
        
        try:
            # Should not raise error in debug mode
            settings = Settings(_env_file=str(env_file))
            assert settings.SECRET_KEY == "test-secret-key-for-development-only"
        finally:
            env_file.unlink(missing_ok=True)
    
    def test_directory_creation(self) -> None:
        """Test that required directories are created."""
        env_content = """
SPOTIPY_CLIENT_ID=test_client_id
SPOTIPY_CLIENT_SECRET=test_client_secret
SECRET_KEY=test_secret_key
CACHE_PATH=/tmp/test_cache/token
SAVE_DIR=/tmp/test_save
TMP_DIR=/tmp/test_tmp
DEFAULT_CACHE_DIR=/tmp/test_default_cache
"""
        
        env_file = Path("/tmp/test_env_dirs")
        env_file.write_text(env_content)
        
        try:
            settings = Settings(_env_file=str(env_file))
            
            # Check that directories were created
            assert os.path.exists("/tmp/test_cache")
            assert os.path.exists("/tmp/test_save")
            assert os.path.exists("/tmp/test_tmp")
            assert os.path.exists("/tmp/test_default_cache")
            
        finally:
            env_file.unlink(missing_ok=True)
            # Clean up test directories
            import shutil
            for path in ["/tmp/test_cache", "/tmp/test_save", "/tmp/test_tmp", "/tmp/test_default_cache"]:
                if os.path.exists(path):
                    shutil.rmtree(path, ignore_errors=True)


class TestGetSettings:
    """Test get_settings function."""
    
    def test_get_settings_singleton(self) -> None:
        """Test that get_settings returns the same instance."""
        env_content = """
SPOTIPY_CLIENT_ID=test_client_id
SPOTIPY_CLIENT_SECRET=test_client_secret
SECRET_KEY=test_secret_key
"""
        
        env_file = Path("/tmp/test_env_singleton")
        env_file.write_text(env_content)
        
        try:
            # Reset the global settings instance
            from src.spotibye_backend.config import _settings
            _settings = None
            
            settings1 = get_settings()
            settings2 = get_settings()
            
            assert settings1 is settings2
            
        finally:
            env_file.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__])

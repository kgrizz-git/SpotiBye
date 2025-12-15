"""Configuration settings for SpotiBye backend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Spotify API Configuration
    SPOTIPY_CLIENT_ID: str
    SPOTIPY_CLIENT_SECRET: str
    SPOTIPY_REDIRECT_URI: str = "http://127.0.0.1:8000/auth/callback"
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    RELOAD: bool = False
    
    # Security Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS Configuration
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # ReccoBeats API Configuration
    RECCOBEATS_BASE_URL: str = "https://api.reccobeats.com/v1"
    RECCOBEATS_TIMEOUT: int = 10
    
    # File Paths and Directories
    CACHE_PATH: str = "/tmp/.spotify_exporter_token"
    SAVE_DIR: str = "/tmp/Downloads"
    TMP_DIR: str = "/tmp/spotify_exports"
    DEFAULT_CACHE_DIR: str = "/tmp/.spotify_exporter_cache"
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/spotibye-backend.log"
    
    # OAuth Configuration
    OAUTH_PORTS: list[int] = [8080, 8081, 8082, 8083, 8084]
    SCOPE: str = (
        "playlist-read-private "
        "playlist-read-collaborative "
        "user-library-read "
        "user-read-email "
        "user-read-private"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate_settings()
    
    def _validate_settings(self) -> None:
        """Validate critical settings."""
        if not self.SPOTIPY_CLIENT_ID or self.SPOTIPY_CLIENT_ID == "YOUR_CLIENT_ID_HERE":
            raise ValueError("SPOTIPY_CLIENT_ID must be set")
        
        if not self.SPOTIPY_CLIENT_SECRET or self.SPOTIPY_CLIENT_SECRET == "YOUR_CLIENT_SECRET_HERE":
            raise ValueError("SPOTIPY_CLIENT_SECRET must be set")
        
        if not self.SECRET_KEY or self.SECRET_KEY == "test-secret-key-for-development-only":
            if self.DEBUG:
                # Import here to avoid circular import
                import logging
                logging.warning("Using default test secret key - not suitable for production")
            else:
                raise ValueError("SECRET_KEY must be set for production")
        
        # Ensure directories exist
        for dir_path in [os.path.dirname(self.CACHE_PATH), self.SAVE_DIR, self.TMP_DIR, self.DEFAULT_CACHE_DIR]:
            os.makedirs(dir_path, exist_ok=True)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Constants
OAUTH_PORTS: Final[list[int]] = [8080, 8081, 8082, 8083, 8084]

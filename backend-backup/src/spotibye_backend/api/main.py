"""Main FastAPI application setup."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .playlists import router as playlists_router
from .analysis import router as analysis_router
from .export import router as export_router
from ..config import get_settings

settings = get_settings()

app = FastAPI(
    title="SpotiBye Backend API",
    description="Backend API server for Spotify Playlist Exporter",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(playlists_router, prefix="/api", tags=["playlists"])
app.include_router(analysis_router, prefix="/api", tags=["analysis"])
app.include_router(export_router, prefix="/api", tags=["export"])

# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "spotibye-backend"}

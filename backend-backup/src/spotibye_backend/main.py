"""Main entry point for the SpotiBye backend API server."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add src directory to Python path when running this file directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import uvicorn

from spotibye_backend.api.main import app


def main() -> None:
    """Launch the FastAPI application."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    reload = os.getenv("RELOAD", "false").lower() == "true"

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if debug else "info",
    )


if __name__ == "__main__":
    main()

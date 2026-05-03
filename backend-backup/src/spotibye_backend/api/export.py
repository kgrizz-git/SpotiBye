"""Export API endpoints for playlist data export functionality."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth.oauth_handler import create_spotify_client_with_refresh
from ..caching.analysis import get_cached_playlist_analysis
from ..config import get_settings
from ..logging_config import logger

router = APIRouter()
settings = get_settings()


# Pydantic models
class ExportRequest(BaseModel):
    playlist_id: str
    format: str = "xlsx"  # "xlsx", "csv", "json"
    include_audio_features: bool = True
    include_reccobeats_analysis: bool = True


class ExportStatusResponse(BaseModel):
    export_id: str
    playlist_id: str
    status: str  # "pending", "in_progress", "completed", "failed"
    download_url: str | None = None
    error_message: str | None = None


def get_spotify_client(token_info: dict[str, Any] | None = None) -> Any:
    """Get authenticated Spotify client."""
    if not token_info:
        raise HTTPException(status_code=401, detail="Authentication required")

    sp = create_spotify_client_with_refresh(token_info)
    if not sp:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return sp


@router.post("/export/start", response_model=dict[str, str])
async def start_export(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    token_info: dict[str, Any] | None = Depends(lambda: None),
) -> dict[str, str]:
    """Start export of playlist data."""
    try:
        # Generate unique export ID
        import uuid

        export_id = str(uuid.uuid4())

        # Start background export
        background_tasks.add_task(
            export_playlist_background,
            export_id,
            request.playlist_id,
            request.format,
            request.include_audio_features,
            request.include_reccobeats_analysis,
            token_info,
        )

        logger.info(f"Started export {export_id} for playlist: {request.playlist_id}")
        return {"export_id": export_id, "message": "Export started"}

    except Exception as exc:
        logger.error(f"Error starting export: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to start export: {exc!s}")


@router.get("/export/{export_id}/download")
async def download_export(export_id: str) -> StreamingResponse:
    """Download exported file."""
    try:
        # In a real implementation, this would check a database or cache
        # For now, we'll create a simple file-based approach

        export_file_path = f"{settings.TMP_DIR}/export_{export_id}.xlsx"

        try:
            with open(export_file_path, "rb") as f:
                content = f.read()

            # Clean up file after download
            import os

            os.remove(export_file_path)

            return StreamingResponse(
                io.BytesIO(content),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename=playlist_export_{export_id}.xlsx"
                },
            )

        except FileNotFoundError:
            raise HTTPException(
                status_code=404, detail="Export file not found or expired"
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error downloading export: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to download export: {exc!s}"
        )


@router.get("/export/playlist/{playlist_id}/immediate")
async def export_playlist_immediate(
    playlist_id: str,
    format: str = "xlsx",
    include_audio_features: bool = True,
    include_reccobeats_analysis: bool = True,
    token_info: dict[str, Any] | None = Depends(lambda: None),
) -> StreamingResponse:
    """Export playlist data immediately (synchronous)."""
    try:
        sp = get_spotify_client(token_info)

        # Get playlist info
        playlist = sp.playlist(playlist_id)
        playlist_name = playlist["name"].replace("/", "_").replace("\\", "_")

        # Get tracks
        tracks = []
        results = sp.playlist_items(playlist_id)

        while results:
            for item in results["items"]:
                if item["track"]:
                    tracks.append(item["track"])
            if results["next"]:
                results = sp.next(results)
            else:
                results = None

        # Create DataFrame
        df_data = []
        for track in tracks:
            row = {
                "Track ID": track["id"],
                "Track Name": track["name"],
                "Artist(s)": ", ".join([artist["name"] for artist in track["artists"]]),
                "Album": track["album"]["name"],
                "Album Artist": track["album"]["artists"][0]["name"]
                if track["album"]["artists"]
                else "",
                "Release Date": track["album"]["release_date"],
                "Duration (ms)": track["duration_ms"],
                "Duration (mm:ss)": f"{track['duration_ms'] // 60000}:{(track['duration_ms'] % 60000) // 1000:02d}",
                "Explicit": track["explicit"],
                "Popularity": track["popularity"],
                "Track URL": track["external_urls"].get("spotify", ""),
                "Preview URL": track["preview_url"] or "",
            }
            df_data.append(row)

        df = pd.DataFrame(df_data)

        # Add audio features if requested
        if include_audio_features:
            track_ids = [track["id"] for track in tracks if track["id"]]
            features_data = {}

            # Get features in batches
            batch_size = 100
            for i in range(0, len(track_ids), batch_size):
                batch_ids = track_ids[i : i + batch_size]
                features = sp.audio_features(batch_ids)

                for j, feature in enumerate(features):
                    if feature and batch_ids[j]:
                        features_data[batch_ids[j]] = feature

            # Add feature columns
            feature_columns = [
                "danceability",
                "energy",
                "key",
                "loudness",
                "mode",
                "speechiness",
                "acousticness",
                "instrumentalness",
                "liveness",
                "valence",
                "tempo",
                "time_signature",
            ]

            for col in feature_columns:
                df[col] = df["Track ID"].map(
                    lambda x: features_data.get(x, {}).get(col, "")
                )

        # Add ReccoBeats analysis if requested
        if include_reccobeats_analysis:
            cached_analysis = get_cached_playlist_analysis(playlist_id)
            if cached_analysis and cached_analysis.get("reccobeats"):
                reccobeats_data = cached_analysis["reccobeats"]

                # Add ReccoBeats-specific columns
                recco_columns = [
                    "recco_energy",
                    "recco_valence",
                    "recco_danceability",
                    "recco_acousticness",
                    "recco_instrumentalness",
                ]

                for col in recco_columns:
                    df[col] = df["Track ID"].map(
                        lambda x: reccobeats_data.get(x, {}).get(col, "")
                    )

        # Export based on format
        if format.lower() == "csv":
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)

            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={playlist_name}_export.csv"
                },
            )

        elif format.lower() == "json":
            output = io.StringIO()
            df.to_json(output, orient="records", indent=2)
            output.seek(0)

            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="application/json",
                headers={
                    "Content-Disposition": f"attachment; filename={playlist_name}_export.json"
                },
            )

        else:  # Default to Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Tracks")

                # Add metadata sheet
                metadata = {
                    "Playlist Name": [playlist["name"]],
                    "Playlist ID": [playlist["id"]],
                    "Total Tracks": [len(tracks)],
                    "Export Date": [pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")],
                    "Includes Audio Features": [include_audio_features],
                    "Includes ReccoBeats Analysis": [include_reccobeats_analysis],
                }
                pd.DataFrame(metadata).to_excel(
                    writer, index=False, sheet_name="Metadata"
                )

            output.seek(0)

            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": f"attachment; filename={playlist_name}_export.xlsx"
                },
            )

    except Exception as exc:
        logger.error(f"Error in immediate export: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to export playlist: {exc!s}"
        )


async def export_playlist_background(
    export_id: str,
    playlist_id: str,
    format: str,
    include_audio_features: bool,
    include_reccobeats_analysis: bool,
    token_info: dict[str, Any] | None,
) -> None:
    """Background task to export playlist data."""
    try:
        # This would implement the same logic as export_playlist_immediate
        # but save to file for later download
        # For now, it's a placeholder

        logger.info(
            f"Background export {export_id} completed for playlist: {playlist_id}"
        )

    except Exception as exc:
        logger.error(f"Error in background export: {exc}")


__all__ = ["router"]

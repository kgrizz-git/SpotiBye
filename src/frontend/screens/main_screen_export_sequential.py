"""Sequential fallback support for backend exports."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List


class SequentialExportMixin:
    """Provide the per-playlist fallback when combined export generation fails."""

    def _backend_export_fallback_sequential(
        self, playlists: List[Dict[str, Any]], base_output_path: str
    ) -> Dict[str, Any]:
        """Generate and download one backend export per playlist."""
        screen = self.screen
        adapter = screen.backend_adapter
        if not adapter:
            return {
                "success_count": 0,
                "failed_count": len(playlists),
                "failed_playlist_ids": [
                    p.get("id", "") for p in playlists if p.get("id")
                ],
            }

        total = len(playlists)
        base_dir = os.path.dirname(base_output_path)
        base_name = os.path.splitext(os.path.basename(base_output_path))[0]
        export_format = self._selected_export_format()
        success_count = 0
        failed_playlist_ids: List[str] = []

        for index, playlist in enumerate(playlists, start=1):
            playlist_id = playlist.get("id")
            if not playlist_id:
                continue

            playlist_name = self._sanitize_export_filename_component(
                playlist.get("name", "playlist")
            )
            safe_id = self._sanitize_export_filename_component(playlist_id)
            extension = self._get_file_extension(export_format)
            target_file = f"{base_name} - {playlist_name} ({safe_id}){extension}"
            target_path = os.path.join(base_dir, target_file)

            self.scheduler.call_soon(
                lambda i=index, t=total, name=playlist_name: setattr(
                    screen.status_label,
                    "text",
                    f"Fallback [{i}/{t}] Generating export for {name}...",
                )
            )
            self.scheduler.call_soon(
                lambda i=index, t=total: setattr(
                    screen.progress_bar, "value", int(((i - 1) / t) * 100) + 10
                )
            )
            self._set_backend_error_context(
                "sequential-fallback",
                f"generate {index}/{total} playlist={playlist_id}",
            )

            if self._check_cancelled():
                return {
                    "success_count": success_count,
                    "failed_count": total - success_count,
                    "cancelled": True,
                }

            export_info = adapter.generate_export(
                playlist_id, export_format, report_errors=False
            )
            if not export_info:
                failed_playlist_ids.append(playlist_id)
                continue

            self.scheduler.call_soon(
                lambda i=index, t=total, name=playlist_name: setattr(
                    screen.status_label,
                    "text",
                    f"Fallback [{i}/{t}] Downloading export for {name}...",
                )
            )
            self.scheduler.call_soon(
                lambda i=index, t=total: setattr(
                    screen.progress_bar, "value", int(((i - 1) / t) * 100) + 60
                )
            )
            self._set_backend_error_context(
                "sequential-fallback",
                f"download {index}/{total} playlist={playlist_id}",
            )

            if self._check_cancelled():
                return {
                    "success_count": success_count,
                    "failed_count": total - success_count,
                    "cancelled": True,
                }

            if not adapter.download_export(playlist_id, target_path):
                failed_playlist_ids.append(playlist_id)
                continue

            success_count += 1
            if index < total:
                time.sleep(0.5)

        if success_count > 0 and not failed_playlist_ids:
            self._set_backend_error_context(
                "completed", f"sequential fallback success ({total} playlists)"
            )
        elif success_count > 0:
            self._set_backend_error_context(
                "completed",
                f"sequential fallback partial ({success_count}/{total} playlists)",
            )
        else:
            self._set_backend_error_context(
                "failed", f"sequential fallback failed ({total} playlists)"
            )

        return {
            "success_count": success_count,
            "failed_count": len(failed_playlist_ids),
            "failed_playlist_ids": failed_playlist_ids,
        }

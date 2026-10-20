#!/usr/bin/env python3
"""Capture personal-data-free README screenshots of the real SpotiBye app.

Regenerate with::

    .venv/bin/python scripts/capture_screenshots.py

A real (non-headless) Kivy window opens for roughly 30 seconds and closes by
itself. The script:

* starts ``src/frontend/tests/mock_backend.py`` on a free localhost port with
  the fictional fixture from ``scripts/screenshot_fixture.py``;
* points the app at it with ``SPOTIBYE_BACKEND_URL`` and redirects ``HOME`` and
  ``KIVY_HOME`` to a throwaway temp dir, so the app's cache, token and backend
  selection never touch ``~/.spotibye_cache`` (a before/after fingerprint of the
  real cache dir is printed);
* skips the browser by calling the backend's mock OAuth callback and handing the
  response to the login screen's own ``_on_login_success``;
* opens each view through the app's own handlers, waits until the expected
  fixture content is on screen (timeout -> exit 1), and saves it with
  ``Window.screenshot()`` at 1400x900;
* writes metadata-free JPEGs (quality ~82, max width 1400, under 500 KB) into a
  temp dir first and copies them to ``docs/images/`` only if every view
  succeeded, so a failed run never overwrites existing images.

The cache explorer's data columns are filled by the fixture's ``explorer`` data,
which the script injects into the explorer's ``cache_data`` (the backend
explorer never fills ``tracks_by_playlist`` or ``features_by_track`` itself).

Captured: login, playlist grid, analysis popup, tracks popup, cache explorer.
Not captured: the exported sheet (the XLSX is built by the Cloudflare Worker,
which the mock does not emulate, and rendering a spreadsheet needs a GUI app).
``Window.screenshot()`` grabs the GL framebuffer, so the OS title bar is not in
the image.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Generator

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "docs" / "images"
WINDOW_SIZE = (1400, 900)
MAX_BYTES = 500 * 1024
REAL_CACHE = Path.home() / ".spotibye_cache"  # read-only fingerprint, never opened

# Screen name -> output file name. The first three match README.md.
OUTPUTS = {
    "login": "screenshot-login.jpg",
    "playlists": "screenshot-playlists.jpg",
    "analysis": "screenshot-playlist-analysis.jpg",
    "tracks": "screenshot-tracks.jpg",
    "cache": "screenshot-cache-explorer.jpg",
}


def _fingerprint(path: Path) -> str:
    """Hash names, sizes and mtimes under ``path`` (never file contents)."""
    if not path.exists():
        return "absent"
    digest = hashlib.sha256()
    count = 0
    for entry in sorted(path.rglob("*")):
        st = entry.stat()
        digest.update(
            f"{entry.relative_to(path)}|{st.st_size}|{st.st_mtime_ns}".encode()
        )
        count += 1
    return f"{count} entries, sha256={digest.hexdigest()[:16]}"


def _load(name: str, path: Path) -> Any:
    """Import a module by file path (avoids importing ``src.frontend`` early)."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _save_jpeg(png_path: Path, dest: Path) -> int:
    """Convert ``png_path`` to a metadata-free JPEG under the size cap."""
    from PIL import Image

    with Image.open(png_path) as src:
        img = src.convert("RGB")
    if img.width > WINDOW_SIZE[0]:
        height = round(img.height * WINDOW_SIZE[0] / img.width)
        img = img.resize((WINDOW_SIZE[0], height), Image.Resampling.LANCZOS)
    clean = Image.new("RGB", img.size)  # fresh image: carries no metadata
    clean.paste(img)
    quality = 82
    while True:
        clean.save(dest, format="JPEG", quality=quality, optimize=True, exif=b"")
        size = dest.stat().st_size
        if size <= MAX_BYTES or quality <= 50:
            return size
        quality -= 6


PLAYLIST_COUNT = 14
FIRST_TRACK_COUNT = 32  # tracks in the first fixture playlist
STEP = 0.5
TIMEOUT = 30.0
ERROR_MARKERS = ("unavailable", "could not load", "error")


class CaptureError(RuntimeError):
    """A view never reached its expected content, or showed an error."""


def _texts(widget: Any) -> list[str]:
    return [
        str(w.text) for w in widget.walk() if isinstance(getattr(w, "text", None), str)
    ]


def _has_error(widget: Any) -> str | None:
    for text in _texts(widget):
        if any(marker in text.lower() for marker in ERROR_MARKERS):
            return text
    return None


def _wait(
    what: str, ready: Callable[[], bool], view: Any = None
) -> Generator[float, None, None]:
    """Yield to Kivy until ``ready()`` is true; raise on timeout or error text."""
    waited = 0.0
    while not ready():
        found = _has_error(view) if view is not None else None
        if found:
            raise CaptureError(f"{what}: view shows an error: {found!r}")
        if waited >= TIMEOUT:
            raise CaptureError(f"{what}: timed out after {TIMEOUT:.0f}s")
        yield STEP
        waited += STEP
    yield STEP  # let one more frame draw before the framebuffer is read


def _isolate_environment(tmp: Path, base_url: str) -> None:
    """Redirect every user-data location BEFORE importing kivy or the app."""
    home = tmp / "home"
    (home / ".kivy").mkdir(parents=True)
    (home / "Downloads").mkdir()
    os.environ.update(
        {
            "HOME": str(home),
            "KIVY_HOME": str(home / ".kivy"),
            "KIVY_NO_ARGS": "1",
            "SPOTIBYE_BACKEND_URL": base_url,
            "SPOTIBYE_USE_PRODUCTION": "false",
            "SPOTIBYE_ENABLE_BACKEND_SELECTOR": "false",
            # Shown in the UI; expands to the temp HOME.
            "SPOTIBYE_EXPORT_DIR": "~/Downloads",
            "SPOTIBYE_TEMP_DIR": str(tmp / "temp_exports"),
        }
    )
    for key in ("SPOTIBYE_PRODUCTION_BACKEND_URL", "SPOTIBYE_DEV_BACKEND_URL"):
        os.environ.pop(key, None)
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "src"))


class Capture:
    """Drives the app one view at a time; each ``*_view`` is a Clock generator."""

    def __init__(self, app: Any, window: Any, tmp: Path, explorer_data: dict[str, Any]):
        self.app = app
        self.window = window
        self.tmp = tmp
        self.explorer_data = explorer_data
        self.raw: dict[str, Path] = {}

    def shot(self, key: str) -> None:
        # Kivy inserts a counter before the extension; use the returned path.
        self.raw[key] = Path(self.window.screenshot(name=str(self.tmp / f"{key}.png")))

    def run(self) -> Generator[float, None, None]:
        self.window.size = WINDOW_SIZE
        yield from self.login_view()
        yield from self.playlists_view()
        card = self.app.main_screen.playlist_widgets[0]
        yield from self.analysis_view(card)
        yield from self.tracks_view(card)
        yield from self.cache_view()

    def login_view(self) -> Generator[float, None, None]:
        login = self.app.login_screen
        yield 1.0
        yield from _wait(
            "login",
            lambda: login.connection_status_label.text == "Connected to backend",
        )
        self.shot("login")
        # Scripted login: mock OAuth callback, then the screen's own handler.
        resp = self.app.backend_client.handle_spotify_callback(
            "test_code_12345", "test_state_12345"
        )
        login._on_login_success(resp)

    def playlists_view(self) -> Generator[float, None, None]:
        main = self.app.main_screen

        def grid_ready() -> bool:
            widgets = main.playlist_widgets
            return (
                len(widgets) == PLAYLIST_COUNT
                and all(w.cover_image.texture for w in widgets)
                and main.status_label.text == f"Loaded {PLAYLIST_COUNT} playlists"
            )

        yield from _wait("playlist grid", grid_ready)
        for widget in main.playlist_widgets[1:4:2]:
            widget.checkbox.active = True
        yield from _wait(
            "playlist selection", lambda: "Selected: 2 of" in main.selection_label.text
        )
        self.shot("playlists")

    def analysis_view(self, card: Any) -> Generator[float, None, None]:
        card.show_detailed_playlist_window()
        content = card._detailed_popup.content

        def ready() -> bool:
            done = content._analysis_status_label.text == "Analysis complete"
            return done and any(
                "synth pop" in t for t in _texts(content._analysis_container)
            )

        yield from _wait("analysis popup", ready, content)
        self.shot("analysis")
        card._detailed_popup.dismiss()  # keep the popups from bleeding together
        yield 1.0

    def tracks_view(self, card: Any) -> Generator[float, None, None]:
        main = self.app.main_screen
        card._open_tracks_window(None)
        content = card._tracks_popup.content
        yield from _wait(
            "tracks popup",
            lambda: len(content._tracks_layout.children) == FIRST_TRACK_COUNT,
            content,
        )

        def status_settled() -> bool:
            main.update_status_with_cache_info()
            return main.status_label.text == f"Loaded {PLAYLIST_COUNT} playlists"

        yield from _wait("tracks status bar", status_settled)
        self.shot("tracks")
        card._tracks_popup.dismiss()
        yield 1.0

    def cache_view(self) -> Generator[float, None, None]:
        main = self.app.main_screen
        main.open_cache_explorer()
        popup = self._find_explorer()
        inner = popup.cache_explorer
        yield from _wait(
            "cache explorer playlists",
            lambda: len(inner.playlists_content.children) == PLAYLIST_COUNT,
            inner,
        )
        yield 1.0  # the explorer's own loader replaces cache_data once; wait it out
        inner.cache_data.update(self.explorer_data)
        playlist = inner.cache_data["playlists"][0]
        inner.select_playlist(playlist)
        inner.select_track(
            inner.cache_data["tracks_by_playlist"][playlist["playlist_id"]][0]
        )

        def columns_ready() -> bool:
            return (
                len(inner.tracks_content.children) == FIRST_TRACK_COUNT
                and len(inner.details_content.children) == 7
                and len(inner.features_content.children) == 11
            )

        yield from _wait("cache explorer columns", columns_ready, inner)
        self.shot("cache")

    def _find_explorer(self) -> Any:
        from kivy.core.window import Window

        for child in Window.children:
            if hasattr(child, "cache_explorer"):
                return child
        raise CaptureError("cache explorer popup did not open")


def _write_outputs(raw: dict[str, Path], tmp: Path) -> list[tuple[Path, int]]:
    """Convert to JPEG in a temp dir, then copy all to docs/images/."""
    staging = tmp / "out"
    staging.mkdir()
    staged = [
        (staging / OUTPUTS[k], _save_jpeg(png, staging / OUTPUTS[k]))
        for k, png in raw.items()
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, _size in staged:
        shutil.copyfile(path, OUT_DIR / path.name)
    return [(OUT_DIR / path.name, size) for path, size in staged]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="spotibye-shots-"))
    before = _fingerprint(REAL_CACHE)

    # Mock backend (loaded by path so no frontend module sees the real HOME).
    mock = _load("spotibye_mock_backend", REPO / "src/frontend/tests/mock_backend.py")
    fixture = _load("screenshot_fixture", REPO / "scripts/screenshot_fixture.py")
    server = mock.MockBackendServer(host="127.0.0.1", port=0)
    if not server.start():
        print("Could not start the mock backend", file=sys.stderr)
        return 1
    base_url = server.get_base_url()
    test_data = fixture.build_test_data(base_url)
    server.set_test_data(test_data)
    _isolate_environment(tmp, base_url)

    from kivy.clock import Clock
    from kivy.config import Config

    Config.set("graphics", "width", str(WINDOW_SIZE[0]))
    Config.set("graphics", "height", str(WINDOW_SIZE[1]))
    Config.set("graphics", "resizable", "0")
    from kivy.core.window import Window

    from src.frontend.app import SpotifyExporterApp
    from src.frontend.config import backend_config

    assert str(backend_config.CACHE_DIR).startswith(str(tmp)), backend_config.CACHE_DIR

    app = SpotifyExporterApp()
    capture = Capture(app, Window, tmp, test_data["explorer"])
    steps = capture.run()
    errors: list[str] = []

    def tick(_dt: float) -> None:
        try:
            Clock.schedule_once(tick, next(steps))
        except StopIteration:
            app.stop()
        except Exception as exc:  # report, then close cleanly
            errors.append(f"{type(exc).__name__}: {exc}")
            app.stop()

    Clock.schedule_once(tick, 1.0)
    try:
        app.run()
    finally:
        server.stop()

    written = [] if errors else _write_outputs(capture.raw, tmp)
    title = Window.title
    shutil.rmtree(tmp, ignore_errors=True)

    after = _fingerprint(REAL_CACHE)
    print(f"Window title: {title}")
    print(f"Real cache before: {before}")
    state = "UNCHANGED" if before == after else "CHANGED"
    print(f"Real cache after:  {after}  ({state})")
    for err in errors:
        print(f"ERROR: {err} (no images written)", file=sys.stderr)
    for path, size in written:
        print(f"Wrote {path.relative_to(REPO)} ({size // 1024} KB)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

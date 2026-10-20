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
* opens each view through the app's own handlers and saves it with
  ``Window.screenshot()`` at 1400x900, then writes metadata-free JPEGs
  (quality ~82, max width 1400, under 500 KB) to ``docs/images/``.

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
from typing import Any, Generator

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


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="spotibye-shots-"))
    before = _fingerprint(REAL_CACHE)

    # 1. Mock backend (loaded by path so no frontend module sees the real HOME).
    mock = _load("spotibye_mock_backend", REPO / "src/frontend/tests/mock_backend.py")
    fixture = _load(
        "spotibye_screenshot_fixture", REPO / "scripts/screenshot_fixture.py"
    )
    server = mock.MockBackendServer(host="127.0.0.1", port=0)
    if not server.start():
        print("Could not start the mock backend", file=sys.stderr)
        return 1
    base_url = server.get_base_url()
    server.set_test_data(fixture.build_test_data(base_url))

    # 2. Isolate every user-data location BEFORE importing kivy or the app.
    home = tmp / "home"
    (home / ".kivy").mkdir(parents=True)
    (home / "Downloads").mkdir()
    os.environ.update(
        {
            "HOME": str(home),
            "KIVY_HOME": str(home / ".kivy"),
            "KIVY_NO_ARGS": "1",
            "SPOTIBYE_BACKEND_URL": base_url,
            "SPOTIBYE_ENABLE_BACKEND_SELECTOR": "false",
            "SPOTIBYE_EXPORT_DIR": "~/Downloads",  # shown in the UI; expands to the temp HOME
            "SPOTIBYE_TEMP_DIR": str(tmp / "temp_exports"),
        }
    )
    for key in ("SPOTIBYE_PRODUCTION_BACKEND_URL", "SPOTIBYE_DEV_BACKEND_URL"):
        os.environ.pop(key, None)
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "src"))

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
    raw: dict[str, Path] = {}
    errors: list[str] = []

    def shot(key: str) -> None:
        # Kivy inserts a counter before the extension; use the returned path.
        raw[key] = Path(Window.screenshot(name=str(tmp / f"{key}.png")))

    def steps() -> Generator[float, None, None]:
        Window.size = WINDOW_SIZE
        yield 3.0  # build, resize, backend health check
        shot("login")
        yield 0.5

        # Scripted login: the mock OAuth callback, then the login screen's own
        # success handler (saves the token into the temp cache, switches screens).
        resp = app.backend_client.handle_spotify_callback(
            "test_code_12345", "test_state_12345"
        )
        app.login_screen._on_login_success(resp)
        main = app.main_screen
        for _ in range(40):  # wait for the grid and every cover image (<= 20 s)
            widgets = main.playlist_widgets
            if len(widgets) == 14 and all(w.cover_image.texture for w in widgets):
                break
            yield 0.5
        for widget in main.playlist_widgets[1:4:2]:
            widget.checkbox.active = True
        yield 1.0
        shot("playlists")
        yield 0.5

        card = main.playlist_widgets[0]
        card.show_detailed_playlist_window()
        yield 4.0  # analysis job + results
        shot("analysis")
        yield 0.5

        card._detailed_popup.dismiss()  # keep the popups from bleeding together
        yield 1.0
        card._open_tracks_window(None)
        yield 5.0
        main.update_status_with_cache_info()  # clear the leftover "Loading..." text
        yield 1.0  # let a frame draw before grabbing the framebuffer
        shot("tracks")
        yield 0.5
        card._tracks_popup.dismiss()
        yield 1.0

        main.open_cache_explorer()
        yield 3.0
        shot("cache")
        yield 0.5

    gen = steps()

    def tick(_dt: float) -> None:
        try:
            Clock.schedule_once(tick, next(gen))
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

    written: list[tuple[Path, int]] = []
    if not errors:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for key, png in raw.items():
            dest = OUT_DIR / OUTPUTS[key]
            written.append((dest, _save_jpeg(png, dest)))
    title = Window.title
    shutil.rmtree(tmp, ignore_errors=True)

    after = _fingerprint(REAL_CACHE)
    print(f"Window title: {title}")
    print(f"Real cache before: {before}")
    print(
        f"Real cache after:  {after}  ({'UNCHANGED' if before == after else 'CHANGED'})"
    )
    for err in errors:
        print(f"ERROR: {err}", file=sys.stderr)
    for path, size in written:
        print(f"Wrote {path.relative_to(REPO)} ({size // 1024} KB)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

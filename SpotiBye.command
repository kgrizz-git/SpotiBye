#!/bin/bash
# Double-click launcher for running SpotiBye from source on macOS.
# Finder starts Terminal in $HOME, so move to the repo root first.
cd "$(dirname "$0")" || exit 1

# Prefer the project venv; fall back to python3 only if Kivy is installed.
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif python3 -c 'import kivy' >/dev/null 2>&1; then
  PY=python3
else
  echo "SpotiBye: dependencies are not installed. Run:" >&2
  echo "  python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi

# First run only: give this file the app icon in Finder. Never blocks launch.
# Skip if an icon is already attached, or a previous attempt failed (sentinel).
ICON="$PWD/resources/SpotiBye black edited 1-modified.icns"
SENTINEL=.spotibye-launcher-icon-failed
if [ "$(uname)" = "Darwin" ] \
  && ! /usr/bin/xattr -p com.apple.ResourceFork SpotiBye.command >/dev/null 2>&1 \
  && [ ! -e "$SENTINEL" ]; then
  RESULT=$(/usr/bin/osascript -l JavaScript -e '
    function run(argv) {
      ObjC.import("AppKit");
      var img = $.NSImage.alloc.initWithContentsOfFile(argv[0]);
      if (!img || img.isNil()) { return "false"; }
      return String($.NSWorkspace.sharedWorkspace.setIconForFileOptions(img, argv[1], 0));
    }' "$ICON" "$PWD/SpotiBye.command" 2>&1) || true
  if [ "$RESULT" = "true" ]; then
    echo "SpotiBye: applied the app icon to SpotiBye.command."
  else
    echo "SpotiBye: could not apply the launcher icon (${RESULT:-no output}); continuing." >&2
    touch "$SENTINEL" || true
  fi
fi

exec "$PY" run_frontend_backend.py "$@"

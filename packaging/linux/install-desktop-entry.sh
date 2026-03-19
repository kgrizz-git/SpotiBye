#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$SCRIPT_DIR"
APP_EXEC="$PACKAGE_ROOT/SpotiBye/SpotiBye"
APP_ICON="$PACKAGE_ROOT/resources/SpotiBye black edited 1-modified.png"
TEMPLATE="$PACKAGE_ROOT/SpotiBye.desktop.template"
TARGET_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
TARGET_FILE="$TARGET_DIR/spotibye.desktop"

if [[ ! -x "$APP_EXEC" ]]; then
  echo "Expected executable not found: $APP_EXEC"
  exit 1
fi

if [[ ! -f "$APP_ICON" ]]; then
  echo "Expected icon not found: $APP_ICON"
  exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Desktop template not found: $TEMPLATE"
  exit 1
fi

mkdir -p "$TARGET_DIR"

sed \
  -e "s|__SPOTIBYE_EXEC__|$APP_EXEC|g" \
  -e "s|__SPOTIBYE_ICON__|$APP_ICON|g" \
  "$TEMPLATE" > "$TARGET_FILE"

chmod 644 "$TARGET_FILE"

echo "Installed launcher: $TARGET_FILE"
echo "You may need to log out/in or run: update-desktop-database '$TARGET_DIR'"

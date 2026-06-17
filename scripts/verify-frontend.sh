#!/bin/bash
set -e

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Resolve venv pytest
if [ -f "$REPO_ROOT/.venv/bin/pytest" ]; then
  PYTEST="$REPO_ROOT/.venv/bin/pytest"
elif [ -f "$REPO_ROOT/venv/bin/pytest" ]; then
  PYTEST="$REPO_ROOT/venv/bin/pytest"
else
  echo "Warning: No virtual environment found. Using system pytest — tests may fail." >&2
  PYTEST="python -m pytest"
fi

# Run from repo root so src.frontend.* imports resolve
if ! OUTPUT=$(KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 $PYTEST src/frontend/tests/ -q 2>&1); then
  echo "Test failures:" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

# Silent on success
exit 0

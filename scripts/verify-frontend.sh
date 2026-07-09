#!/bin/bash
set -e

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

# Resolve venv pytest and python
if [ -f "$REPO_ROOT/.venv/bin/pytest" ]; then
  PYTEST="$REPO_ROOT/.venv/bin/pytest"
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif [ -f "$REPO_ROOT/venv/bin/pytest" ]; then
  PYTEST="$REPO_ROOT/venv/bin/pytest"
  PYTHON="$REPO_ROOT/venv/bin/python"
else
  echo "Warning: No virtual environment found. Using system pytest/python — tests may fail." >&2
  PYTEST="python -m pytest"
  PYTHON="python"
fi

# Run from repo root so src.frontend.* imports resolve
if ! OUTPUT=$(KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 $PYTEST src/frontend/tests/ -q 2>&1); then
  echo "Test failures (src/frontend/tests/):" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

if ! OUTPUT=$(KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 $PYTEST scripts/tests/ -q 2>&1); then
  echo "Test failures (scripts/tests/):" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

if ! OUTPUT=$($PYTHON scripts/check_file_lengths.py --exemptions scripts/file-length-exemptions.json 2>&1); then
  echo "File length check failures:" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

# Silent on success
exit 0

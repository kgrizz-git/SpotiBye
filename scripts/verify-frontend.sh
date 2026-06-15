#!/bin/bash
set -e

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT/src/frontend"

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d ".venv" ] && [ ! -d "$REPO_ROOT/venv" ] && [ ! -d "$REPO_ROOT/.venv" ]; then
  echo "Warning: No virtual environment found. Tests may fail." >&2
fi

# Run pytest in quiet mode
if ! OUTPUT=$(python -m pytest tests/ -q 2>&1); then
  echo "Test failures:" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

# Silent on success
exit 0

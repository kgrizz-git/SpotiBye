#!/bin/bash
set -e

cd src/frontend

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
  echo "Warning: No virtual environment found. Tests may fail." >&2
fi

# Run pytest in quiet mode
OUTPUT=$(python -m pytest tests/ -q 2>&1)
if [ $? -ne 0 ]; then
  echo "Test failures:" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

# Silent on success
exit 0

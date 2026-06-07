#!/bin/bash
set -e

cd src/backend

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
  echo "Error: node_modules not found. Run 'npm install' first." >&2
  exit 1
fi

# Run TypeScript compiler (no emit, check only)
OUTPUT=$(npx tsc --noEmit 2>&1)
if [ $? -ne 0 ]; then
  echo "TypeScript errors:" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

# Run linter
OUTPUT=$(npm run lint 2>&1)
if [ $? -ne 0 ]; then
  echo "Lint errors:" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

# Silent on success
exit 0

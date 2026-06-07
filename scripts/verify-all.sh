#!/bin/bash
set -e

# Dry-run mode
if [ "$1" = "--dry-run" ]; then
  echo "Dry run mode - would run verifications"
  exit 0
fi

echo "Verifying backend..."
./scripts/verify-backend.sh

echo "Verifying frontend..."
./scripts/verify-frontend.sh

echo "All verifications passed."
exit 0

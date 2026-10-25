#!/bin/bash
set -e

# Dry-run mode
if [[ "$1" = "--dry-run" ]]; then
  echo "Dry run mode - would run verifications"
  exit 0
fi

echo "Verifying backend..."
./scripts/verify-backend.sh

echo "Verifying dependency manifests..."
PYTHON_BIN="./.venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="python3"
"$PYTHON_BIN" scripts/check-dependencies.py --manifests

echo "Verifying backend deploy-status script..."
./scripts/test-backend-deploy-status.sh >/dev/null

echo "Verifying frontend..."
./scripts/verify-frontend.sh

echo "All verifications passed."
exit 0

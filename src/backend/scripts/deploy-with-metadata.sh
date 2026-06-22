#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-}"

if [[ -z "${ENVIRONMENT}" ]]; then
  echo "Usage: $0 <development|production>" >&2
  exit 2
fi

case "${ENVIRONMENT}" in
  development|production) ;;
  *)
    echo "Invalid environment: ${ENVIRONMENT}" >&2
    echo "Expected: development or production" >&2
    exit 2
    ;;
esac

RELEASE_SHA="$(git rev-parse HEAD)"
RELEASE_VERSION="$(node -p "require('./package.json').version")"
DEPLOYED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
WRANGLER_BIN="./node_modules/.bin/wrangler"

if [[ ! -x "${WRANGLER_BIN}" ]]; then
  echo "Wrangler binary not found at ${WRANGLER_BIN}. Run npm install in src/backend." >&2
  exit 2
fi

export RELEASE_SHA
export RELEASE_VERSION
export DEPLOYED_AT

"${WRANGLER_BIN}" deploy --env "${ENVIRONMENT}" \
  --var "RELEASE_SHA:${RELEASE_SHA}" \
  --var "RELEASE_VERSION:${RELEASE_VERSION}" \
  --var "DEPLOYED_AT:${DEPLOYED_AT}"

printf '{\n  "environment": "%s",\n  "release_sha": "%s",\n  "release_version": "%s",\n  "deployed_at": "%s"\n}\n' \
  "${ENVIRONMENT}" "${RELEASE_SHA}" "${RELEASE_VERSION}" "${DEPLOYED_AT}" > .deployed-commit.json

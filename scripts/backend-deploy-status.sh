#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${1:-${SPOTIBYE_BACKEND_URL:-}}"

if [[ -z "${BACKEND_URL}" ]]; then
  echo "Usage: $0 <backend-url>" >&2
  echo "Or set SPOTIBYE_BACKEND_URL." >&2
  exit 2
fi

BACKEND_URL="${BACKEND_URL%/}"
HEALTH_URL="${BACKEND_URL}/health"
HEALTH_JSON="$(curl -fsS "${HEALTH_URL}")"

release_sha="$(printf '%s' "${HEALTH_JSON}" | node -e "let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>{const j=JSON.parse(s);console.log(j.data?.release_sha ?? 'unknown')})")"
release_version="$(printf '%s' "${HEALTH_JSON}" | node -e "let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>{const j=JSON.parse(s);console.log(j.data?.release_version ?? 'unknown')})")"
deployed_at="$(printf '%s' "${HEALTH_JSON}" | node -e "let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>{const j=JSON.parse(s);console.log(j.data?.deployed_at ?? 'unknown')})")"
environment="$(printf '%s' "${HEALTH_JSON}" | node -e "let s='';process.stdin.on('data',c=>s+=c);process.stdin.on('end',()=>{const j=JSON.parse(s);console.log(j.data?.environment ?? 'unknown')})")"

head_sha="$(git rev-parse HEAD)"

echo "Backend URL: ${BACKEND_URL}"
echo "Environment: ${environment}"
echo "Live release SHA: ${release_sha}"
echo "Live release version: ${release_version}"
echo "Live deployed at: ${deployed_at}"
echo "Local HEAD: ${head_sha}"

needs_deployment="UNKNOWN"

if [[ "${release_sha}" == "unknown" ]]; then
  needs_deployment="UNKNOWN"
  echo "Reason: live backend does not expose release_sha."
elif ! git cat-file -e "${release_sha}^{commit}" 2>/dev/null; then
  needs_deployment="UNKNOWN"
  echo "Reason: live release_sha is not present in this local repository."
else
  changed_since_deploy="$(git diff --name-only "${release_sha}..HEAD" -- src/backend .github/workflows/deploy-backend.yml .github/workflows/deploy-production.yml)"
  dirty_backend="$(git status --short -- src/backend .github/workflows/deploy-backend.yml .github/workflows/deploy-production.yml)"

  if [[ -n "${changed_since_deploy}" || -n "${dirty_backend}" ]]; then
    needs_deployment="YES"
  else
    needs_deployment="NO"
  fi

  echo
  echo "Committed backend/workflow changes since live release:"
  if [[ -n "${changed_since_deploy}" ]]; then
    printf '%s\n' "${changed_since_deploy}"
  else
    echo "None"
  fi

  echo
  echo "Uncommitted backend/workflow changes:"
  if [[ -n "${dirty_backend}" ]]; then
    printf '%s\n' "${dirty_backend}"
  else
    echo "None"
  fi
fi

echo
echo "Needs Deployment: ${needs_deployment}"

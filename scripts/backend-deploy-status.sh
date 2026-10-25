#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${SPOTIBYE_DESKTOP_ENV_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.desktop.env.local}"

# Read KEY from the environment, falling back to .desktop.env.local.
# Parses KEY=value lines only; the file is never executed. Handles an
# optional `export`, spaces around `=`, CRLF endings, single or double
# quotes, and trailing `# comments`. The last matching line wins.
# SPOTIBYE_DESKTOP_ENV_FILE overrides the file path (used by tests).
env_url() {
  local key="$1" value="${!1:-}" line k v
  if [[ -z "${value}" && -f "${ENV_FILE}" ]]; then
    while IFS= read -r line || [[ -n "${line}" ]]; do
      line="${line%$'\r'}"
      [[ "${line}" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*(.*)$ ]] || continue
      k="${BASH_REMATCH[2]}"; v="${BASH_REMATCH[3]}"
      [[ "${k}" == "${key}" ]] || continue
      if [[ "${v}" =~ ^\"([^\"]*)\" || "${v}" =~ ^\'([^\']*)\' ]]; then
        v="${BASH_REMATCH[1]}"
      elif [[ "${v}" == [\"\'#]* ]]; then
        # Unterminated quote or comment-only value: treat as unset.
        v=""
      else
        v="${v%%[[:space:]]#*}"
        v="${v%"${v##*[![:space:]]}"}"
      fi
      value="${v}"
    done < "${ENV_FILE}"
  fi
  printf '%s' "${value}"
}

case "${1:-}" in
  prod|production) BACKEND_URL="$(env_url SPOTIBYE_PRODUCTION_BACKEND_URL)" ;;
  dev|development) BACKEND_URL="$(env_url SPOTIBYE_DEV_BACKEND_URL)" ;;
  "") BACKEND_URL="$(env_url SPOTIBYE_BACKEND_URL)" ;;
  *) BACKEND_URL="$1" ;;
esac

if [[ -z "${BACKEND_URL}" ]]; then
  echo "Usage: $0 [prod|dev|<backend-url>]" >&2
  echo "URLs come from the environment or ${ENV_FILE}:" >&2
  echo "  prod -> SPOTIBYE_PRODUCTION_BACKEND_URL, dev -> SPOTIBYE_DEV_BACKEND_URL," >&2
  echo "  no argument -> SPOTIBYE_BACKEND_URL." >&2
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

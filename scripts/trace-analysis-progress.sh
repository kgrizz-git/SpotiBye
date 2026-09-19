#!/bin/bash
set -euo pipefail

# Live analysis-progress trace for the progress-bar plan.
# POSTs a fresh analysis job (force_enrichment=1) and polls the status endpoint,
# recording timestamped raw JSON lines so intermediate progress values can be
# inspected for the 65->85 ReccoBeats stall / queued:0 staleness symptoms.
#
# Usage:
#   scripts/trace-analysis-progress.sh <backend-url> <playlist-id> [max-seconds]
#
#   The backend session token (Authorization: Bearer ...) is NEVER passed as an
#   argument (it would leak via ps / shell history). Provide it via the
#   TRACE_BEARER_TOKEN env var, a pipe on stdin, or an interactive prompt.
#   Obtain it from the app's Spotify login flow, e.g.:
#     TRACE_BEARER_TOKEN="$(python3 -c "import json,os; print(json.load(open(os.path.expanduser('~/.spotibye_cache/backend_token_<hash>.json')))['token'])")" \
#       scripts/trace-analysis-progress.sh <backend-url> <playlist-id>
#
#   Trace output goes to a unique per-run directory under tmp/ (gitignored).
#
# Needs: curl, python3.

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <backend-url> <playlist-id> [max-seconds]" >&2
  exit 2
fi

BACKEND_URL="${1%/}"
case "${BACKEND_URL}" in
  https://*) ;;
  http://localhost*|http://127.0.0.1*|http://\[::1\]*|http://\[::1\]:*) ;;
  *)
    echo "Error: BACKEND_URL must be https (http allowed only for localhost/127.0.0.1/::1): ${BACKEND_URL}" >&2
    exit 2
    ;;
esac
PLAYLIST_ID="$2"
MAX_SECONDS="${3:-120}"
INTERVAL=2

# Bearer token from protected runtime input only — never argv.
if [ -z "${TRACE_BEARER_TOKEN:-}" ]; then
  if [ -t 0 ]; then
    read -rsp "Bearer token: " TRACE_BEARER_TOKEN
    echo
  else
    IFS= read -r TRACE_BEARER_TOKEN || true
  fi
fi
if [ -z "${TRACE_BEARER_TOKEN:-}" ]; then
  echo "Error: no bearer token (set TRACE_BEARER_TOKEN, pipe it on stdin, or run interactively)" >&2
  exit 2
fi

# Pass the token to curl via a 0600 config file (keeps it out of ps output);
# remove it on exit.
CURL_CFG="$(mktemp -t spotibye-trace-curl-XXXXXX)"
chmod 600 "${CURL_CFG}"
printf 'header = "Authorization: Bearer %s"\nheader = "Content-Type: application/json"\n' "${TRACE_BEARER_TOKEN}" > "${CURL_CFG}"
unset TRACE_BEARER_TOKEN
trap 'rm -f "${CURL_CFG}"' EXIT

mkdir -p tmp
RUN_DIR="$(mktemp -d tmp/trace-run-XXXXXX)"
OUTFILE="${RUN_DIR}/trace.jsonl"

auth=(-K "${CURL_CFG}")

echo "POST fresh job (force_enrichment=1)..."
curl -fsS --max-time 30 "${auth[@]}" -X POST \
  "${BACKEND_URL}/analysis/playlist/${PLAYLIST_ID}?force_enrichment=1" > /dev/null
echo "Polling status every ${INTERVAL}s (max ${MAX_SECONDS}s) -> ${OUTFILE}"

elapsed=0
while [ "${elapsed}" -lt "${MAX_SECONDS}" ]; do
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  body="$(curl -fsS --max-time 15 "${auth[@]}" \
    "${BACKEND_URL}/analysis/playlist/${PLAYLIST_ID}/status" || echo '{"error":{"code":"FETCH_FAILED"}}')"
  printf '%s %s\n' "${now}" "${body}" >> "${OUTFILE}"
  summary="$(printf '%s' "${body}" | python3 -c "import json,sys; d=json.load(sys.stdin).get('data',{}); print(f\"{d.get('status','?')}:{d.get('progress','?')}\")")"
  echo "t=${elapsed}s ${summary}"
  case "${summary}" in
    completed:*|failed:*) break ;;
  esac
  sleep "${INTERVAL}"
  elapsed=$((elapsed + INTERVAL))
done

echo "Done. Raw trace: ${OUTFILE}"

if printf '%s' "${summary:-}" | grep -q "^completed:"; then
  echo "Fetching final results..."
  results="$(curl -fsS --max-time 30 "${auth[@]}" \
    "${BACKEND_URL}/analysis/playlist/${PLAYLIST_ID}/results" || echo '{}')"
  printf '%s' "${results}" > "${RUN_DIR}/results.json"
  printf '%s' "${results}" | python3 -c "
import json,sys
d = json.load(sys.stdin).get('data', {})
genres = (d.get('genre_distribution') or {})
errors = d.get('errors') or []
print(f\"genre buckets: {len(genres)} | errors: {len(errors)}\")
for e in errors[:10]: print(f\"  - {e.get('source')}: {e.get('message')}\")"
fi

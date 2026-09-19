#!/bin/bash
set -euo pipefail

# Live analysis-progress trace for the progress-bar plan.
# POSTs a fresh analysis job (force_enrichment=1) and polls the status endpoint,
# recording timestamped raw JSON lines so intermediate progress values can be
# inspected for the 65->85 ReccoBeats stall / queued:0 staleness symptoms.
#
# Usage:
#   scripts/trace-analysis-progress.sh <backend-url> <bearer-token> <playlist-id> [max-seconds]
#
#   <bearer-token> is a backend session token (Authorization: Bearer ...),
#   obtained via the app's Spotify login flow — it is passed as an argument so
#   it never lands in a file. Trace output goes to tmp/ (gitignored).
#
# Needs: curl, python3.

if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <backend-url> <bearer-token> <playlist-id> [max-seconds]" >&2
  exit 2
fi

BACKEND_URL="${1%/}"
TOKEN="$2"
PLAYLIST_ID="$3"
MAX_SECONDS="${4:-120}"
INTERVAL=2

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTFILE="tmp/trace-${PLAYLIST_ID}-${STAMP}.jsonl"
mkdir -p tmp

auth=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")

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
  printf '%s' "${results}" > "tmp/results-${PLAYLIST_ID}-${STAMP}.json"
  printf '%s' "${results}" | python3 -c "
import json,sys
d = json.load(sys.stdin).get('data', {})
genres = (d.get('genre_distribution') or {})
errors = d.get('errors') or []
print(f\"genre buckets: {len(genres)} | errors: {len(errors)}\")
for e in errors[:10]: print(f\"  - {e.get('source')}: {e.get('message')}\")"
fi

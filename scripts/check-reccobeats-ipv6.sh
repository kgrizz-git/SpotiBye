#!/bin/bash
set -euo pipefail

TRACK_ID="${1:-01K4zKU104LyJ8gMb7227B}"
HOST="api.reccobeats.com"
URL="https://${HOST}/v1/audio-features?ids=${TRACK_ID}"

if ! command -v dig >/dev/null 2>&1; then
  echo "Error: dig is required for AAAA lookup" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is required for IPv6 reachability check" >&2
  exit 1
fi

echo "AAAA records for ${HOST}:"
dig +short AAAA "${HOST}"

echo
echo "IPv6 ReccoBeats audio-features probe:"
curl -6 --fail --silent --show-error \
  --max-time 15 \
  --header "Accept: application/json" \
  --header "User-Agent: SpotiBye-ReccoBeats-IPv6-Check/1.0" \
  --write-out "\nHTTP %{http_code}\n" \
  "${URL}"

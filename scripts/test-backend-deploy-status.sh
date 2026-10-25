#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

tmp_dir="$(mktemp -d)"
port_file="${tmp_dir}/port"
output_file="${tmp_dir}/output"
head_sha="$(git rev-parse HEAD)"

cleanup() {
  if [[ -n "${server_pid:-}" ]]; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  rm -rf "${tmp_dir}"
}
trap cleanup EXIT

node -e '
const fs = require("fs");
const http = require("http");
const portFile = process.argv[1];
const releaseSha = process.argv[2];

const server = http.createServer((req, res) => {
  if (req.url !== "/health") {
    res.writeHead(404);
    res.end("not found");
    return;
  }

  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify({
    data: {
      status: "healthy",
      service: "spotibye-backend",
      environment: "test",
      release_sha: releaseSha,
      release_version: "test-version",
      deployed_at: "2026-06-22T00:00:00Z",
      timestamp: "2026-06-22T00:00:01Z"
    }
  }));
});

server.listen(0, "127.0.0.1", () => {
  fs.writeFileSync(portFile, String(server.address().port));
});
' "${port_file}" "${head_sha}" &
server_pid="$!"

for _ in {1..50}; do
  if [[ -s "${port_file}" ]]; then
    break
  fi
  sleep 0.1
done

if [[ ! -s "${port_file}" ]]; then
  echo "Mock health server did not start" >&2
  exit 1
fi

port="$(cat "${port_file}")"

./scripts/backend-deploy-status.sh "http://127.0.0.1:${port}" > "${output_file}"

rg -q "Environment: test" "${output_file}"
rg -q "Live release SHA: ${head_sha}" "${output_file}"
rg -q "Needs Deployment: NO" "${output_file}"

# prod/dev shorthands resolve URLs from the env file, never sourcing it.
env_file="${tmp_dir}/desktop.env"
printf '%s\r\n' \
  "export SPOTIBYE_PRODUCTION_BACKEND_URL = \"http://127.0.0.1:${port}\" # prod" \
  "SPOTIBYE_DEV_BACKEND_URL=http://127.0.0.1:1   # superseded below" \
  "SPOTIBYE_DEV_BACKEND_URL='http://127.0.0.1:${port}'   # dev, last wins" \
  > "${env_file}"
for target in prod dev; do
  env -u SPOTIBYE_PRODUCTION_BACKEND_URL -u SPOTIBYE_DEV_BACKEND_URL \
    SPOTIBYE_DESKTOP_ENV_FILE="${env_file}" \
    ./scripts/backend-deploy-status.sh "${target}" > "${output_file}"
  rg -q "Backend URL: http://127.0.0.1:${port}$" "${output_file}"
  rg -q "Needs Deployment: NO" "${output_file}"
done

# The environment wins over the file.
SPOTIBYE_DEV_BACKEND_URL="http://127.0.0.1:${port}" \
  SPOTIBYE_DESKTOP_ENV_FILE=/nonexistent \
  ./scripts/backend-deploy-status.sh dev > "${output_file}"
rg -q "Backend URL: http://127.0.0.1:${port}$" "${output_file}"

# Comment-only and unterminated values count as unset: usage error, exit 2.
for bad in 'SPOTIBYE_DEV_BACKEND_URL= # disabled' 'SPOTIBYE_DEV_BACKEND_URL="http://broken'; do
  printf '%s\n' "${bad}" > "${env_file}"
  status=0
  env -u SPOTIBYE_DEV_BACKEND_URL SPOTIBYE_DESKTOP_ENV_FILE="${env_file}" \
    ./scripts/backend-deploy-status.sh dev > /dev/null 2>&1 || status=$?
  [[ "${status}" -eq 2 ]] || { echo "expected exit 2 for: ${bad} (got ${status})" >&2; exit 1; }
done

echo "backend-deploy-status functional test passed"

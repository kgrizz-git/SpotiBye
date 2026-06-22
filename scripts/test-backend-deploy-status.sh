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

echo "backend-deploy-status functional test passed"

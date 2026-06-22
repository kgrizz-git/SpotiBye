# Backend Deployment Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make backend deployment status answerable from the live Worker, local git state, and CI metadata, then document a single agent-friendly check.

**Architecture:** The live Cloudflare Worker becomes the source of truth by exposing deployment metadata in `/health`. GitHub Actions and local deploy scripts pass immutable metadata into Wrangler as environment variables. A repo script compares the live deployed SHA against local `HEAD` and backend file changes, while docs teach agents to use that script before claiming backend changes are deployed.

**Tech Stack:** Cloudflare Workers, Hono, Wrangler, GitHub Actions, Bash, Vitest, TypeScript.

---

## File Structure

- Modify `src/backend/types/env.ts`: add optional deployment metadata bindings to the Worker `Env`.
- Modify `src/backend/index.ts`: include deployment metadata in the `/health` response.
- Modify `src/backend/tests/helpers/env.ts`: set deterministic metadata defaults for tests.
- Modify `src/backend/tests/integration.test.ts`: assert `/health` includes deployment metadata.
- Create `scripts/backend-deploy-status.sh`: query live backend health metadata and compare it to local git state.
- Create `scripts/test-backend-deploy-status.sh`: run a local mock `/health` server and verify the status script without Cloudflare.
- Modify `src/backend/package.json`: add metadata-aware deploy helper scripts.
- Create `src/backend/scripts/deploy-with-metadata.sh`: wrapper around `wrangler deploy` that injects git SHA/version/timestamp.
- Modify `.github/workflows/deploy-backend.yml`: fix unreachable tag-triggered production deployment, inject deployment vars before deploy, and record GitHub deployment environments.
- Modify `.github/workflows/deploy-production.yml`: inject deployment vars before deploy and record the GitHub production environment.
- Modify `docs/cloudflare-deployment.md`: document live health metadata and status script.
- Modify `AGENTS.md`: add the agent rule for checking backend deployment status.
- Modify `CHANGELOG.md`: record the deployment-tracking behavior as a developer-visible change.
- Optional local-only file: `src/backend/.deployed-commit.json` may be created by the deploy wrapper as a cache only, and must be ignored by git.
- Modify `.gitignore`: ignore `src/backend/.deployed-commit.json`.
- No `src/backend/wrangler.toml` change is required. `RELEASE_SHA`, `RELEASE_VERSION`, and `DEPLOYED_AT` are deploy-time Wrangler vars injected by scripts and GitHub Actions, and they override config-file values for that deployment.

---

### Task 1: Add Live Deployment Metadata to `/health`

**Files:**
- Modify: `src/backend/types/env.ts`
- Modify: `src/backend/index.ts`
- Modify: `src/backend/tests/helpers/env.ts`
- Modify: `src/backend/tests/integration.test.ts`

- [x] **Step 1: Write the failing health metadata assertions**

In `src/backend/tests/integration.test.ts`, update the health check test to assert metadata:

```ts
expect(data.data).toHaveProperty('environment', 'test');
expect(data.data).toHaveProperty('release_sha', 'test-release-sha');
expect(data.data).toHaveProperty('release_version', 'test-release-version');
expect(data.data).toHaveProperty('deployed_at', '2026-06-22T00:00:00.000Z');
```

- [x] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
cd src/backend
npm run test:run -- tests/integration.test.ts
```

Expected: the health check test fails because those fields are missing.

- [x] **Step 3: Add optional metadata fields to `Env`**

In `src/backend/types/env.ts`, add these fields after `ENVIRONMENT: string;`:

```ts
  // Deployment metadata injected by deploy scripts and GitHub Actions.
  RELEASE_SHA?: string;
  RELEASE_VERSION?: string;
  DEPLOYED_AT?: string;
```

- [x] **Step 4: Add test defaults**

In `src/backend/tests/helpers/env.ts`, add these properties to `baseEnv` after `ENVIRONMENT: 'test',`:

```ts
    RELEASE_SHA: 'test-release-sha',
    RELEASE_VERSION: 'test-release-version',
    DEPLOYED_AT: '2026-06-22T00:00:00.000Z',
```

- [x] **Step 5: Return metadata from `/health`**

In `src/backend/index.ts`, replace the current `/health` response object with:

```ts
app.get('/health', (c) => {
  const env = c.env;

  return c.json({
    data: {
      status: 'healthy',
      service: 'spotibye-backend',
      environment: env.ENVIRONMENT,
      release_sha: env.RELEASE_SHA ?? 'unknown',
      release_version: env.RELEASE_VERSION ?? 'unknown',
      deployed_at: env.DEPLOYED_AT ?? 'unknown',
      timestamp: new Date().toISOString(),
    },
  });
});
```

- [x] **Step 6: Run the focused test and confirm it passes**

Run:

```bash
cd src/backend
npm run test:run -- tests/integration.test.ts
```

Expected: all tests in `tests/integration.test.ts` pass.

- [x] **Step 7: Commit**

```bash
git add src/backend/types/env.ts src/backend/index.ts src/backend/tests/helpers/env.ts src/backend/tests/integration.test.ts
git commit -m "feat: expose backend deployment metadata"
```

---

### Task 2: Add Metadata-Aware Local Deploy Wrapper

**Files:**
- Create: `src/backend/scripts/deploy-with-metadata.sh`
- Modify: `src/backend/package.json`
- Modify: `.gitignore`

- [x] **Step 1: Create the deploy wrapper**

Create `src/backend/scripts/deploy-with-metadata.sh`:

```bash
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
```

The `--var NAME:VALUE` syntax is supported by Wrangler v3+ and the repo pins Wrangler v4 through `src/backend/package.json`.

- [x] **Step 2: Make the wrapper executable**

Run:

```bash
chmod +x src/backend/scripts/deploy-with-metadata.sh
```

Expected: command exits with status 0.

- [x] **Step 3: Update package scripts**

In `src/backend/package.json`, replace the deploy scripts with:

```json
    "deploy": "wrangler deploy",
    "deploy:dev": "./scripts/deploy-with-metadata.sh development",
    "deploy:prod": "./scripts/deploy-with-metadata.sh production",
```

Keep the rest of the scripts unchanged.

- [x] **Step 4: Ignore the local deployment cache**

Add this line to `.gitignore`:

```gitignore
src/backend/.deployed-commit.json
```

- [x] **Step 5: Validate the wrapper without deploying**

Run:

```bash
cd src/backend
bash -n scripts/deploy-with-metadata.sh
```

Expected: command exits with status 0.

- [x] **Step 6: Commit**

```bash
git add .gitignore src/backend/package.json src/backend/scripts/deploy-with-metadata.sh
git commit -m "chore: deploy backend with release metadata"
```

---

### Task 3: Fix GitHub Actions Deployment Metadata, Tag Trigger, and Deployment Records

**Files:**
- Modify: `.github/workflows/deploy-backend.yml`
- Modify: `.github/workflows/deploy-production.yml`

- [x] **Step 1: Confirm GitHub deployment environments exist**

Before adding `environment:` keys to workflow jobs, verify the repo has GitHub Environments named exactly `development` and `production` in **Settings > Environments**. Environment names are case-sensitive. If the repo has `Development` or `Production` instead, either rename/create lower-case environments before this task or use the exact existing names consistently in the workflow snippets below.

Expected: `development` and `production` exist before the workflow changes are pushed. Without this prerequisite, deployment jobs may wait for approval unexpectedly or fail depending on organization settings.

- [x] **Step 2: Fix tag trigger in `deploy-backend.yml`**

In `.github/workflows/deploy-backend.yml`, replace the `push` trigger block with:

```yaml
  push:
    branches: [main]
    tags: ['v*']
    paths:
      - 'src/backend/**'
      - '.github/workflows/deploy-backend.yml'
      - '.github/workflows/security.yml'
```

This makes the existing production job condition reachable for version tags.

Important: GitHub Actions `paths` filters do not apply to tag pushes. Any pushed tag matching `v*` can trigger this workflow, even if the tagged commit has no backend changes. That is acceptable here because `v*` tags are treated as production release intent.

- [x] **Step 3: Remove the post-deploy package version mutation**

In `.github/workflows/deploy-backend.yml`, delete the production job steps named `Update worker version` and `Upload deployment info`. The deploy wrapper now injects metadata before deployment, and the old artifact was created after deployment so it did not describe the running Worker.

- [x] **Step 4: Keep the production deploy command unchanged**

Leave this step in `.github/workflows/deploy-backend.yml`:

```yaml
    - name: Deploy to Cloudflare Workers (Production)
      working-directory: src/backend
      run: npm run deploy:prod
      env:
        CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
        CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
```

The `npm run deploy:prod` wrapper computes `RELEASE_SHA`, `RELEASE_VERSION`, and `DEPLOYED_AT` before calling Wrangler.

- [x] **Step 5: Add GitHub deployment environments**

In `.github/workflows/deploy-backend.yml`, add `environment: development` to the `deploy-dev` job:

```yaml
  deploy-dev:
    needs: test
    runs-on: ubuntu-latest
    environment: development
```

In `.github/workflows/deploy-backend.yml`, add `environment: production` to the `deploy-prod` job:

```yaml
  deploy-prod:
    needs: test
    runs-on: ubuntu-latest
    environment: production
```

In `.github/workflows/deploy-production.yml`, add `environment: production` to the `deploy-prod` job:

```yaml
  deploy-prod:
    needs: [test, security-checks]
    if: always() && needs.test.result == 'success' && (needs.security-checks.result == 'success' || needs.security-checks.result == 'skipped')
    runs-on: ubuntu-latest
    environment: production
```

This gives GitHub a durable deployment record alongside the live `/health` metadata.

Because these workflows define explicit token permissions, also add `deployments: write` wherever workflow or job permissions are declared for deployment jobs.

- [x] **Step 6: Remove post-deploy artifact steps from `deploy-production.yml`**

In `.github/workflows/deploy-production.yml`, delete the steps named `Update worker version` and `Upload deployment info` for the same reason.

- [x] **Step 7: Validate workflow syntax structurally**

Run:

```bash
rg -n "Update worker version|deployment-info.txt|Upload deployment info" .github/workflows/deploy-backend.yml .github/workflows/deploy-production.yml
```

Expected: no matches.

- [x] **Step 8: Confirm deployment environments are declared**

Run:

```bash
rg -n "environment: (development|production)" .github/workflows/deploy-backend.yml .github/workflows/deploy-production.yml
```

Expected: matches for `deploy-dev` development and both production deploy jobs.

- [x] **Step 9: Commit**

```bash
git add .github/workflows/deploy-backend.yml .github/workflows/deploy-production.yml
git commit -m "fix: track backend deployment metadata in actions"
```

---

### Task 4: Add Backend Deployment Status Script

**Files:**
- Create: `scripts/backend-deploy-status.sh`
- Create: `scripts/test-backend-deploy-status.sh`

- [x] **Step 1: Create the status script**

Create `scripts/backend-deploy-status.sh`:

```bash
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
```

This script depends on `curl`, `git`, and Node.js. Node.js is already required by the backend toolchain and is used here to parse JSON without adding a `jq` dependency.

The comparison uses `${release_sha}..HEAD`, so run it from a fresh local checkout of the branch you want to compare, normally `main` after pulling. Detached HEADs, stale local branches, or feature branches can produce misleading "changed since deploy" lists.

- [x] **Step 2: Create a functional test for the status script**

Create `scripts/test-backend-deploy-status.sh`:

```bash
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
```

- [x] **Step 3: Make the scripts executable**

Run:

```bash
chmod +x scripts/backend-deploy-status.sh
chmod +x scripts/test-backend-deploy-status.sh
```

Expected: command exits with status 0.

- [x] **Step 4: Validate script syntax**

Run:

```bash
bash -n scripts/backend-deploy-status.sh
bash -n scripts/test-backend-deploy-status.sh
```

Expected: command exits with status 0.

- [x] **Step 5: Validate missing URL behavior**

Run:

```bash
env -u SPOTIBYE_BACKEND_URL ./scripts/backend-deploy-status.sh
```

Expected: command exits with status 2 and prints usage instructions.

- [x] **Step 6: Run the functional status-script test**

Run:

```bash
./scripts/test-backend-deploy-status.sh
```

Expected: prints `backend-deploy-status functional test passed`.

- [ ] **Step 7: Commit**

```bash
git add scripts/backend-deploy-status.sh scripts/test-backend-deploy-status.sh
git commit -m "chore: add backend deployment status script"
```

---

### Task 5: Document Agent and Developer Workflow

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/cloudflare-deployment.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add `AGENTS.md` backend deployment rule**

Add this section near "Running Tests & Verification" in `AGENTS.md`:

````md
## Backend Deployments

Before saying backend changes are deployed, or when asked whether backend deployment is needed, run:

```bash
./scripts/backend-deploy-status.sh <backend-url>
```

Use the production or development Worker URL that matches the question. If `Needs Deployment: YES`, tell the user which committed or uncommitted backend/workflow files differ from the live `release_sha` and ask before deploying. Treat `src/backend/.deployed-commit.json` as a local cache only; the live `/health` metadata is the source of truth.

Run the script from a fresh local checkout of the target branch, normally `main` after pulling. Detached HEADs, stale branches, and feature branches can make the `release_sha..HEAD` comparison look different from the deployment branch.
````

- [ ] **Step 2: Document health metadata in `docs/cloudflare-deployment.md`**

Add this section after "Monitoring Deployment":

````md
## Deployment Status Metadata

The Worker `/health` endpoint returns deployment metadata:

```json
{
  "data": {
    "status": "healthy",
    "service": "spotibye-backend",
    "environment": "production",
    "release_sha": "git commit SHA deployed to Cloudflare",
    "release_version": "package.json version at deploy time",
    "deployed_at": "UTC timestamp set before Wrangler deploy",
    "timestamp": "current health response timestamp"
  }
}
```

To compare the live Worker against local code, run:

```bash
./scripts/backend-deploy-status.sh https://<worker-url>
```

The script reports the live release SHA, local `HEAD`, backend/workflow files changed since deployment, uncommitted backend/workflow changes, and `Needs Deployment: YES/NO/UNKNOWN`.

The status script requires Node.js for JSON parsing. Run it from a fresh local checkout of the target branch, normally `main` after pulling, because it compares the live `release_sha` to local `HEAD`.
````

- [ ] **Step 3: Fix manual deployment commands in `docs/cloudflare-deployment.md`**

Replace the current manual deployment commands with:

```bash
cd src/backend

# Development deployment with release metadata
npm run deploy:dev

# Production deployment with release metadata
npm run deploy:prod
```

- [ ] **Step 4: Check for additional health endpoint reference docs**

Run:

```bash
rg -n "/health|health endpoint|Health" docs dev-docs README.md ARCHITECTURE.md
```

Expected: `docs/cloudflare-deployment.md` is updated in this task. Existing completed plans and short-lived review notes can remain unchanged. If a durable API reference outside completed/superseded plans describes the `/health` response shape, update that same document to include `environment`, `release_sha`, `release_version`, and `deployed_at`.

- [ ] **Step 5: Add changelog entry**

Add this bullet under the existing first `### Added` heading in the `[Unreleased]` section of `CHANGELOG.md`. Do not create another `### Added` heading. The current file already has duplicate `### Changed` and `### Fixed` headings in `[Unreleased]`; leave that pre-existing duplication alone unless the task owner separately asks for changelog cleanup.

```md
- Added live backend deployment metadata to `/health`, metadata-aware Wrangler deploy wrappers, and a `scripts/backend-deploy-status.sh` helper so agents and developers can tell whether backend changes need deployment.
```

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md docs/cloudflare-deployment.md CHANGELOG.md
git commit -m "docs: document backend deployment tracking"
```

---

### Task 6: Final Verification

**Files:**
- Verify all files touched by Tasks 1-5.

- [ ] **Step 1: Run backend tests**

Run:

```bash
cd src/backend
npm run test:run
```

Expected: Vitest exits successfully.

- [ ] **Step 2: Run TypeScript build**

Run:

```bash
cd src/backend
npm run build
```

Expected: TypeScript exits successfully.

- [ ] **Step 3: Run deploy dry-run**

Run:

```bash
cd src/backend
./node_modules/.bin/wrangler deploy --dry-run
```

Expected: Wrangler validates the Worker bundle without deploying.

- [ ] **Step 4: Run status-script functional test**

Run from repo root:

```bash
./scripts/test-backend-deploy-status.sh
```

Expected: prints `backend-deploy-status functional test passed`.

- [ ] **Step 5: Run repo verification**

Run from repo root:

```bash
./scripts/verify-all.sh
```

Expected: command is silent on success.

- [ ] **Step 6: Check plan/documentation placement**

Run:

```bash
./scripts/check-repo-structure.sh
```

Expected: command exits successfully and does not report an active completed plan or root-level plan file.

- [ ] **Step 7: Commit final verification fixes if needed**

If verification required fixes, commit only those touched files:

```bash
git status --short
git add <verified-files>
git commit -m "fix: stabilize backend deployment tracking"
```

If no fixes were needed, skip this step.

---

## Acceptance Criteria

- [ ] `/health` returns `environment`, `release_sha`, `release_version`, and `deployed_at`.
- [ ] Local and GitHub Actions production deployments inject metadata before `wrangler deploy`.
- [ ] `.github/workflows/deploy-backend.yml` can actually run its version-tag production deployment path.
- [ ] `scripts/backend-deploy-status.sh` reports `Needs Deployment: YES/NO/UNKNOWN`.
- [ ] `scripts/test-backend-deploy-status.sh` verifies the status script against a mock `/health` endpoint.
- [ ] `AGENTS.md` tells agents to use the status script and treat live `/health` as source of truth.
- [ ] Local `.deployed-commit.json` is ignored and documented as a cache only.
- [ ] Backend tests, TypeScript build, Wrangler dry-run, and repo verification pass.

## Self-Review

- Spec coverage: Covers all prior recommendations: live metadata, status script, tags/workflow history, AGENTS rule, and the unreachable tag-trigger issue.
- Placeholder scan: No `TBD`, `TODO`, "similar to", or undefined future work remains.
- Type consistency: Metadata names are consistently `RELEASE_SHA`, `RELEASE_VERSION`, `DEPLOYED_AT` in Worker bindings and `release_sha`, `release_version`, `deployed_at` in JSON output.

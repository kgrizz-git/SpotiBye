# Plan: Add Zod and OSV-Scanner

## Objective
Enhance the repository's security posture and data validation through two independent workstreams:
1. **Zod Validation**: Add Zod to the TypeScript backend for robust parsing at all external boundaries (HTTP requests, KV storage, Cloudflare Queues, Environment Variables, and external API boundaries).
2. **OSV-Scanner**: Integrate Google's `osv-scanner` as a `pre-push` hook and in CI workflows to catch vulnerable dependencies, replacing existing audit tools.

*(Note: Dependabot is already configured in the repo).*

---

## Part 1: Zod Implementation (Backend)

### 1.1 Setup & Installation
- [ ] Verify Hono v4 compatibility with `@hono/zod-validator`. (Sticking with `@hono/zod-validator` as migrating to `@hono/zod-openapi` is too large of an architectural shift).
- [ ] Check `src/backend/tsconfig.json` and ensure `strict: true` is enabled to maximize Zod's type inference.
- [ ] Install dependencies in `src/backend/`: `npm install zod @hono/zod-validator`

### 1.2 HTTP Route Payload Validation
Refactor routes to use Zod (lazily instantiate schemas to avoid cold-start latency):
- [ ] `/auth/spotify/login`: validate `redirect_uri` string.
- [ ] Export routes: validate request bodies for endpoints like `POST /export/playlists`, `POST /export/playlist/:id`, `POST /export/jobs`.
- [ ] Analysis routes (`routes/analysis.ts`): validate request bodies (e.g., `POST /analysis/playlist/:id`).
- [ ] Spotify routes (e.g., `/spotify/playlists/:id/tracks`): validate `limit` and `offset` query params.

### 1.3 System Boundary Validation (Env, KV, Queues, APIs)
- [ ] **Environment Variables**: Define an `Env` schema and parse bindings on startup or global middleware to fail fast if secrets/bindings are misconfigured.
- [ ] **KV Storage**: Refactor `middleware/auth.ts` to use Zod for `safeParseSession` when reading from KV.
- [ ] **Cloudflare Queues**: Define an `AnalysisQueueMessageSchema` and validate message bodies at the top of the `queue()` handler in `src/backend/index.ts` before passing them to the service layer.
- [ ] **Spotify API**: Gradually migrate `parseSpotifyResponse<T>` in `types/spotify-api.ts` to use Zod schemas, wrapping the existing function and updating call-sites sequentially.

### 1.4 Testing & Verification
- [ ] Write unit tests for each new Zod schema (valid, invalid, edge cases).
- [ ] Write integration tests for route handlers using `@hono/zod-validator`.
- [ ] Verify that `parseSpotifyResponse` call-sites still pass in `src/backend/tests/`.
- [ ] Check the Cloudflare Worker bundle size. Zod adds ~12KB (min+gzip). Ensure the bundle remains well within limits.

---

## Part 2: OSV-Scanner Integration

### 2.1 Pre-commit Configuration
- [ ] Update `.pre-commit-config.yaml` at the **repo root** to include the `osv-scanner-docker` hook in the `pre-push` stage using the `v2.3.5` revision.
  ```yaml
  - repo: https://github.com/google/osv-scanner
    rev: v2.3.5 
    hooks:
      - id: osv-scanner-docker
        name: OSV-Scanner (pre-push)
        stages: [pre-push]
        args:
          - "scan"
          - "source"
          - "--format=vertical"
          - "--recursive"
          - "--verbosity=error"
          - "--skip-dirs=.venv"
          - "--skip-dirs=node_modules"
          - "--skip-dirs=backups"
          - "--skip-dirs=docs/old-docs-backup"
          - "."
  ```
- [ ] Update the `security-scan` hook (running `check-dependencies.py`) in `.pre-commit-config.yaml` to include the `--ci` flag, ensuring it returns a non-zero exit code on failure and properly blocks the push:
  ```yaml
      - id: security-scan
        name: Full Security Scan
        description: Run comprehensive security checks before push
        entry: python scripts/check-dependencies.py --security --ci
        language: system
        pass_filenames: false
  ```

### 2.2 CI Workflow (`security.yml`) Refactor
- [ ] Update `.github/workflows/security.yml` to replace the individual `pip-audit` and `npm-audit` jobs (which currently use `|| true` and ignore failures) with a unified `google/osv-scanner-action/bootstrap-action`.
  ```yaml
  dependency-scan:
    name: Dependency Vulnerabilities (OSV-Scanner)
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write  # Allows uploading SARIF to GitHub security tab
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Run OSV-Scanner
        uses: google/osv-scanner-action/bootstrap-action@v1.0.2
        with:
          scan-args: |
            -r
            --skip-dirs=.venv,node_modules,backups,docs/old-docs-backup
            ./
  ```

### 2.3 Verification
- [ ] Run `pre-commit run --hook-stage push osv-scanner-docker` locally to ensure it successfully scans dependencies without false positives.

---

## Rollback Plan
- **Part 1 (Zod)**: Revert `package.json` changes, remove Zod validators, and revert modified boundary/test files if severe performance or typing regressions occur.
- **Part 2 (OSV-Scanner)**: Revert `.pre-commit-config.yaml` and `.github/workflows/security.yml` if the OSV scans become overly noisy or block deployments unnecessarily.

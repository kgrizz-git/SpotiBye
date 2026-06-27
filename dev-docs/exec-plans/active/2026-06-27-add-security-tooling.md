# Plan: Add Zod and OSV-Scanner

## Objective
Enhance the repository's security posture and data validation through two independent workstreams:
1. **Zod Validation**: Add Zod to the TypeScript backend for robust parsing at all external boundaries (HTTP requests, KV storage, Cloudflare Queues, Environment Variables, and external API boundaries).
2. **Security tooling (OSV-Scanner + Bandit)**: Integrate Google's `osv-scanner` as a `pre-push` hook and in CI to replace pip-audit/npm audit, and harden Bandit so local pre-push and CI both enforce the project's `[tool.bandit]` policy (medium/medium + skips).

*(Note: Dependabot is already configured in the repo).*

---

## Part 1: Zod Implementation (Backend)

### 1.1 Setup & Installation
- [ ] Verify Hono v4 compatibility with `@hono/zod-validator`. (Sticking with `@hono/zod-validator` as migrating to `@hono/zod-openapi` is too large of an architectural shift).
- [ ] Check `src/backend/tsconfig.json` and ensure `strict: true` is enabled to maximize Zod's type inference.
- [ ] Install dependencies in `src/backend/`: `npm install zod @hono/zod-validator`
- [ ] **Error-format adapter (required before any route validation):** `@hono/zod-validator` defaults to returning its own error shape (`{ success: false, error: ... }`), which does **not** match this app's uniform envelope (`{ error: { code, message } }`, see the 404 handler in `index.ts`). Add a shared `result` hook (e.g. `zValidator(target, schema, (result, c) => { if (!result.success) return c.json({ error: { code: 'VALIDATION_ERROR', message: ... } }, 400); })`) and reuse it for every validator so clients receive a consistent error shape. Add a unit test asserting the adapted error envelope.

### 1.2 HTTP Route Payload Validation
Refactor routes to use Zod (lazily instantiate schemas to avoid cold-start latency):
- [ ] `/auth/spotify/login`: validate `redirect_uri` string.
- [ ] Export routes: validate request bodies for endpoints like `POST /export/playlists`, `POST /export/playlist/:id`, `POST /export/jobs`.
- [ ] Analysis routes (`routes/analysis.ts`): validate request bodies (e.g., `POST /analysis/playlist/:id`).
- [ ] Spotify routes (e.g., `/spotify/playlists/:id/tracks`): validate `limit` and `offset` query params.
- [ ] **Path parameters:** validate `c.req.param()` values with `zValidator('param', ...)`. All five route files use path params: `routes/spotify.ts` (`:id`), `routes/analysis.ts` (`:id`), `routes/export/playlist.ts` (`:id`), `routes/export/jobs.ts` (`:jobId`), `routes/export/playlists.ts` (`:jobId`). Enforce non-empty strings and, for Spotify IDs, the base62 ID format.

### 1.3 System Boundary Validation (Env, KV, Queues, APIs)
- [ ] **Environment Variables**: Define an `Env` schema and parse bindings on startup or global middleware to fail fast if secrets/bindings are misconfigured.
- [ ] **KV Storage**: Refactor `middleware/auth.ts` `safeParseSession` (currently `middleware/auth.ts:17-36`) using an explicit **two-layer boundary**: (a) `JSON.parse` the raw KV string inside a `try/catch` (the deserialization/KV boundary), then (b) run the parsed value through a `z.object({ user_id, access_token, refresh_token?, expires_at }).safeParse()` (the schema boundary). Preserve the existing behavior of returning `null` (not throwing) on either failure, and keep the truncated-session-id error logging.
- [ ] **Cloudflare Queues**: Define an `AnalysisQueueMessageSchema` and validate message bodies at the top of the `queue()` handler in `src/backend/index.ts` before passing them to the service layer. Note that `index.ts:77-80` overrides `attempt` with `message.attempts` **after** deserialization, so the schema for the raw KV/queue payload must treat `attempt` as optional (or omit it) and validation must run on the raw `message.body` before the `attempt` override is applied. The post-override object can be validated against a stricter schema if desired.
- [ ] **Spotify API**: Gradually migrate `parseSpotifyResponse<T>` in `types/spotify-api.ts` to use Zod schemas. **Decision: wrap, don't replace** — `parseSpotifyResponse` is currently an `asserts data is T` function (`types/spotify-api.ts:128-141`) that throws/narrows. Keep that `asserts` signature and run Zod internally (throw on failure) so existing call-sites and their type-narrowing are unchanged. Replacing it with `safeParse` would change control flow at every call-site and is out of scope; migrate per-schema behind the stable signature.

### 1.4 Testing & Verification
- [ ] **Test organization:** co-locate schema unit tests with existing backend tests in `src/backend/tests/` (mirroring current convention — no new top-level `tests/schemas/` dir). Each schema gets valid/invalid/edge-case cases.
- [ ] Write unit tests for each new Zod schema (valid, invalid, edge cases).
- [ ] Write integration tests for route handlers using `@hono/zod-validator`, including at least one test that asserts a validation failure returns the app's `{ error: { code, message } }` envelope (covers the 1.1 error-format adapter).
- [ ] Verify that `parseSpotifyResponse` call-sites still pass in `src/backend/tests/` (the wrap-don't-replace approach should require no call-site changes; treat any required change as a regression to investigate).
- [ ] Gate the change on the full backend suite passing (`npm run test:run` + `npm run lint`) so pre-existing tests confirm nothing broke.
- [ ] Check the Cloudflare Worker bundle size. Zod adds ~12 KB (min+gzip). Measure with `npx wrangler deploy --dry-run --outdir=dist` (or `wrangler deploy --dry-run`) and read the reported `Total Upload ... / gzip` line. Current Cloudflare limit is **3 MB compressed (Free) / 10 MB compressed (Paid), 64 MB uncompressed**; treat a compressed bundle over ~1 MB as a flag to investigate. Zod's ~12 KB is well within limits, so this is a sanity check rather than a risk.

---

## Part 2: Security Tooling (OSV-Scanner + Bandit)

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
- [ ] **Docker dependency / fallback:** `osv-scanner-docker` requires a running Docker daemon; developers without Docker will see the pre-push hook fail. Choose one and document it in `SECURITY.md` / contributor docs: (a) declare Docker a prerequisite for pushing, or (b) additionally register the native `osv-scanner` hook (non-Docker binary hook from the same repo) as a fallback. Prefer documenting Docker as the default with the native hook noted as an alternative.
- [ ] **Re-install pre-commit hooks:** after editing `.pre-commit-config.yaml`, hooks must be re-registered or the new OSV stage won't run. Add to verification steps and contributor docs: `pre-commit install --hook-type pre-commit --hook-type pre-push`.
- [ ] Update the `security-scan` hook (running `check-dependencies.py`) in `.pre-commit-config.yaml` to include the `--ci` flag, ensuring it returns a non-zero exit code on failure and properly blocks the push:
  ```yaml
      - id: security-scan
        name: Full Security Scan
        description: Run comprehensive security checks before push
        entry: python scripts/check-dependencies.py --security --ci
        language: system
        pass_filenames: false
  ```
- [ ] **Bandit — pin the existing hook to pre-commit only.** The current Bandit hook (`.pre-commit-config.yaml:50-58`) has no `stages:` key, so pre-commit runs it on every installed stage (commit + push) but only on *changed* `.py` files. Set `stages: [pre-commit]` explicitly so scope is intentional: fast feedback on staged Python edits.
- [ ] **Bandit — add a full-tree pre-push hook** (mirror the Semgrep split: secrets on commit, full scan on push). Add a local hook with `stages: [pre-push]`, `pass_filenames: false`, `always_run: true`:
  ```yaml
      - id: bandit-full
        name: Bandit Python Security (pre-push)
        description: Full-tree Bandit scan before push; uses project policy in pyproject.toml
        entry: bandit -r src/ -c pyproject.toml
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
  ```
  Verified clean today: `bandit -r src/ -c pyproject.toml` exits 0 (~0.4s). This catches drift in untouched files that the per-file pre-commit hook can miss.

### 2.2 Bandit CI hardening (`security.yml`)
- [ ] **Use the project Bandit config in CI.** The Bandit job currently runs `bandit -r src/` without `-c pyproject.toml` (`security.yml:100`), so it uses Bandit defaults and reports 247 low + 15 medium findings — all masked by `|| true`. Change both run steps to `bandit -r src/ -c pyproject.toml` so CI matches local/pre-push policy (`severity = medium`, `confidence = medium`, and the `[tool.bandit] skips` list).
- [ ] **Make Bandit blocking in CI.** Remove `|| true` from the run and display steps (`security.yml:100`, `:103`). CI is the non-bypassable gate (`git push --no-verify` skips pre-push). With `-c pyproject.toml`, the tree is clean today (0 findings), so this should not break CI. Keep the JSON report upload step with `if: always()` so artifacts remain available on failure.

### 2.3 CI Workflow (`security.yml`) Refactor — OSV-Scanner
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
- [ ] **Drop the now-unneeded `npm ci` install step.** The current `npm-audit` job runs `npm ci` (`security.yml:163-165`) before auditing; OSV-Scanner reads lockfiles directly and does not need `node_modules`. Removing the install step (and Node setup) from the dependency-scan job saves ~30s per run.
- [ ] **Update the `security-summary` `needs` list.** The summary job (`security.yml:210-227`) lists `needs: [secret-scan, semgrep, bandit, pip-audit, npm-audit]` and prints a per-job table. Replace the removed `pip-audit`/`npm-audit` entries with the new `dependency-scan` job in both the `needs:` list and the summary table rows.

### 2.4 Documentation & Config Cleanup
- [ ] **Update `SECURITY.md`.** It documents `pip-audit` and `npm audit` as the dependency scanners and lists local commands (`SECURITY.md:23-24`, `:70`, `:208`, `:214`). After OSV-Scanner replaces them, update these sections to describe OSV-Scanner and its local/CI usage so developers aren't misled.
- [ ] **Dependabot vs OSV cadence (optional).** Dependabot is set to `monthly` for all ecosystems (`.github/dependabot.yml`). OSV-Scanner covers CVEs disclosed between Dependabot runs, but notifications now come from two systems on different cadences. Consider bumping Dependabot to `weekly`; note the trade-off in the plan if left monthly.
- [ ] **`.semgrepignore` review (optional).** Confirm whether `.semgrepignore` (repo root) needs any change given OSV-Scanner now covers dependency vulnerabilities; likely no change needed since Semgrep is SAST and OSV is SCA, but verify there's no redundant/conflicting coverage.
- [ ] **Note CI path-filter limitation (info).** `security.yml` triggers on source/manifest `paths:` (`:8-16`); PRs touching only docs/config won't re-scan dependencies. The weekly `schedule` cron covers newly-disclosed CVEs on installed deps. Document this so the gap is understood, not surprising.

### 2.5 Verification
- [ ] Run `pre-commit install --hook-type pre-commit --hook-type pre-push` to register the new stages.
- [ ] Run `pre-commit run --hook-stage push osv-scanner-docker` locally to ensure it successfully scans dependencies without false positives.
- [ ] Run `pre-commit run --hook-stage push bandit-full` (or `bandit -r src/ -c pyproject.toml`) and confirm exit 0 before merging Bandit CI changes.

---

## Rollback Plan
Because Zod changes span routes, middleware, types, and tests across **multiple commits**, the rollback must be commit-aware rather than a single revert:
- **Part 1 (Zod)**: Land Zod work as a contiguous, clearly-tagged series of commits (e.g. prefix `zod:`) so rollback is `git revert <first-zod-sha>..<last-zod-sha>` (or revert of the squashed PR merge commit). If only a subset regresses, revert the offending commit(s) individually. As a last resort, revert by file scope: `package.json`/`package-lock.json` plus the Zod validators and modified boundary/test files. Trigger conditions: severe performance or typing regressions.
- **Part 2 (OSV-Scanner + Bandit)**: Revert the `.pre-commit-config.yaml` and `.github/workflows/security.yml` commits (and the `SECURITY.md` doc update) if OSV scans become overly noisy or block deployments unnecessarily. Bandit CI/pre-push changes can be reverted independently (restore `|| true` and/or drop the `bandit-full` hook) if policy tightening causes false positives. Keep tooling changes in their own commit(s), separate from Zod.

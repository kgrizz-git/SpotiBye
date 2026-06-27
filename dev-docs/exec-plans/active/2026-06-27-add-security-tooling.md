# Plan: Add Zod, Dependabot, and OSV-Scanner

## Objective
Enhance the repository's security posture and data validation by adding Zod for the backend, OSV-Scanner for dependency vulnerability scanning, and Dependabot for automated updates. Per user request, OSV-Scanner checks will be run locally as a `pre-push` hook to catch issues before CI fails on GitHub.

## Scope
1. **Zod Validation**: Add `zod` and `@hono/zod-validator` to the TypeScript backend to parse and validate data at the boundaries.
2. **OSV-Scanner**: Integrate Google's `osv-scanner` as a `pre-push` hook to catch vulnerable dependencies (Python and Node) before they hit CI.
3. **Dependabot**: Add a `.github/dependabot.yml` configuration to automatically open PRs when dependencies require updates (Note: Dependabot runs exclusively on GitHub, so it cannot be a local hook).

## Execution Steps

### 1. Zod Implementation (Backend)
- [ ] Install dependencies in `src/backend/`:
  - `npm install zod @hono/zod-validator`
- [ ] Refactor backend routes to use Zod validators for parsing query parameters, headers, and request bodies.
  - *Golden Principle check: Parse data shapes at boundaries - never pass raw, unvalidated API responses between layers.*
- [ ] Run backend tests (`npm run test:run`) to ensure no existing functionality is broken.

### 2. OSV-Scanner Integration (Pre-push)
- [ ] Update `.pre-commit-config.yaml` to include the `osv-scanner` hook in the `pre-push` stage.
  ```yaml
  - repo: https://github.com/google/osv-scanner
    rev: v1.7.4 # Check for latest version
    hooks:
      - id: osv-scanner
        name: OSV-Scanner (pre-push)
        stages: [pre-push]
        args: ["-r", "."]
  ```
- [ ] (Optional) Update `scripts/check-dependencies.py` to optionally run `osv-scanner` if a manual local check is preferred.
- [ ] Run `pre-commit run --hook-stage push osv-scanner` locally to ensure it successfully scans `requirements.txt` and `package-lock.json` without false positives.

### 3. Dependabot Configuration
- [ ] Create `.github/dependabot.yml`.
- [ ] Configure it to monitor:
  - `pip` ecosystem at `/` (weekly)
  - `npm` ecosystem at `/src/backend` (weekly)
  - `github-actions` ecosystem at `/` (weekly)
- [ ] Commit and push the configuration (if `osv-scanner` passes locally).

## Rollback Plan
- Revert `package.json` changes and remove Zod validators if they introduce severe performance or typing regressions.
- Remove `osv-scanner` from `.pre-commit-config.yaml` if it blocks pushes due to unpatchable vulnerabilities (can temporarily skip using `git push --no-verify`).
- Delete `.github/dependabot.yml` if the automated PRs become too noisy.

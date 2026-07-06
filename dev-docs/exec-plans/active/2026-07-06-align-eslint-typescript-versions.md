# Align typescript-eslint Versions Between pre-commit and package.json

> **Source:** dev-docs/backlog/TO_DO.md — "Align `.pre-commit-config.yaml` typescript-eslint versions (v6.0.0 in eslint hook's `additional_dependencies`) with `src/backend/package.json` (^8.61.0)"

**NEEDS REVIEW**

---

## 1. Audit Current State

- [ ] Document version mismatch
  - `.pre-commit-config.yaml:93-94`: `@typescript-eslint/eslint-plugin@6.0.0`, `@typescript-eslint/parser@6.0.0`
  - `src/backend/package.json:21-22`: `@typescript-eslint/eslint-plugin@^8.61.0`, `@typescript-eslint/parser@^8.61.0`

## 2. Risk Assessment

- [ ] Check ESLint plugin v8 breaking changes vs v6
  - Rule name changes, configuration format changes
  - Verify existing `.eslintrc.json` rules are compatible
- [ ] Confirm Node version compatibility (ESLint v8.57.0 is pinned, and Node 24 is now in use)

## 3. Implementation

- [ ] Update `.pre-commit-config.yaml` `additional_dependencies` to match package.json versions:
  ```yaml
  additional_dependencies:
    - eslint@8.57.0
    - "@typescript-eslint/eslint-plugin@8.61.0"
    - "@typescript-eslint/parser@8.61.0"
  ```
- [ ] Verify `.eslintrc.json` configuration is compatible with v8
- [ ] Run pre-commit hook to verify no regressions

## 4. Verification

- [ ] `pre-commit run --all-files` — ensure ESLint passes on all TS files
- [ ] `./scripts/verify-all.sh` — full verification chain
- [ ] CI dry-run (push to branch, check workflow)

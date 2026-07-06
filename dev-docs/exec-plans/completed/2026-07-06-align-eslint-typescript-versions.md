# Align typescript-eslint Versions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `.pre-commit-config.yaml` additional dependencies with the resolved backend versions in `src/backend/package-lock.json`.

**Architecture:** Update the pre-commit configuration file to pin the exact version of ESLint (`8.57.1`) and `typescript-eslint` packages (`8.61.0`) resolved in the backend to ensure local pre-commit checks run the same linting environment as CI and local npm lint tasks. Clean the pre-commit environment cache to force rebuild, and verify everything passes.

**Tech Stack:** ESLint v8, typescript-eslint v8, pre-commit

## Global Constraints

- Pre-commit additional dependencies must match backend package-lock.json resolved versions exactly.
- Do not alter the order of packages under `additional_dependencies` (eslint first, then typescript-eslint packages).
- Maintain compatibility with the Node 24 LTS environment.

---

### Task 1: Audit and Risk Assessment

**Files:**
- Modify: `dev-docs/exec-plans/active/2026-07-06-align-eslint-typescript-versions.md`

**Interfaces:**
- Consumes: Existing config versions
- Produces: Confirmed version targets and assessed risk profile

- [x] **Step 1: Document version mismatch**
  - `.pre-commit-config.yaml:93-94`: `@typescript-eslint/eslint-plugin@6.0.0`, `@typescript-eslint/parser@6.0.0`
  - `src/backend/package.json:21-22`: `@typescript-eslint/eslint-plugin@^8.61.0`, `@typescript-eslint/parser@^8.61.0`
- [x] **Step 2: Check resolved versions in package-lock.json**
  - ESLint: `8.57.1` (from `^8.57.0`)
  - `@typescript-eslint/eslint-plugin`: `8.61.0`
  - `@typescript-eslint/parser`: `8.61.0`
- [x] **Step 3: Verify peer dependency compatibility**
  - `@typescript-eslint/*@8.61.0` peer-depends on `eslint@^8.57.0 || ^9.0.0 || ^10.0.0` — compatible with ESLint `8.57.1`.
  - TypeScript range: `>=4.8.4 <6.1.0` — compatible with project's `^5.4.0`.
  - Node 24 LTS compatibility: ESLint v8 and typescript-eslint v8 fully support Node 24.
- [x] **Step 4: Check typescript-eslint v6 → v8 breaking changes**
  - `@typescript-eslint/no-empty-function` is deprecated but still supported; our config sets it to `"off"`, which is safe. *Note: Expect a non-fatal deprecation notice for `@typescript-eslint/no-empty-function` in eslint output — this is cosmetic.*
  - `@typescript-eslint/no-unnecessary-condition` is a type-aware rule that requires type information and is part of `strict-type-checked` / `recommended-type-checked`. It is not active in our base `recommended` set, so it won't flag new warnings unless type-aware linting is explicitly set up.
  - Verify that no other removed rules (like removed formatting rules) are configured in `src/backend/.eslintrc.json`. (Confirmed: config contains no formatting rules).

### Task 2: Update Pre-commit Dependencies

**Files:**
- Modify: `.pre-commit-config.yaml`

**Interfaces:**
- Consumes: Target version alignment (ESLint `8.57.1`, `@typescript-eslint/*@8.61.0`)
- Produces: Updated pre-commit eslint hook configuration

- [x] **Step 1: Update additional_dependencies in .pre-commit-config.yaml**
  - Edit the `eslint` hook `additional_dependencies` block to match:
    ```yaml
    additional_dependencies:
      - eslint@8.57.1
      - "@typescript-eslint/eslint-plugin@8.61.0"
      - "@typescript-eslint/parser@8.61.0"
    ```
- [x] **Step 2: Confirm edits with git diff**
  Run: `git diff .pre-commit-config.yaml`
  Expected: Only the three dependency lines (eslint, eslint-plugin, parser) are modified.
- [x] **Step 3: Purge cached pre-commit environments**
  Run: `pre-commit clean` to purge existing environments and force re-installation of dependencies.
- [x] **Step 4: Run targeted pre-commit lint check**
  Run: `pre-commit run eslint --all-files`
  Expected: Hook completes successfully (`Passed`). *Fallback: If new lint failures are introduced, investigate new lint rules added in v8 `recommended` and adjust `src/backend/.eslintrc.json` as needed.*

### Task 3: Full Workspace Verification

**Files:**
- Test: All workspace TS files and hooks

**Interfaces:**
- Consumes: Updated pre-commit and eslint config
- Produces: Clean verify-all report

- [x] **Step 1: Run project-local linter**
  Run: `npm run lint` in `src/backend`
  Expected: Runs without errors (warnings on test files are acceptable as they are configured to `warn`).
- [x] **Step 2: Run all pre-commit hooks**
  Run: `pre-commit run --all-files`
  Expected: All checks pass.
- [x] **Step 3: Run full verification script**
  Run: `./scripts/verify-all.sh`
  Expected: Backend and frontend checks pass successfully.

### Task 4: Backlog Cleanup

**Files:**
- Modify: `dev-docs/backlog/TO_DO.md`

**Interfaces:**
- Consumes: Verification of aligned versions
- Produces: Clean backlog status

- [x] **Step 1: Update backlog status**
  - Mark the alignment task complete in `dev-docs/backlog/TO_DO.md:71` or clear the TODO.

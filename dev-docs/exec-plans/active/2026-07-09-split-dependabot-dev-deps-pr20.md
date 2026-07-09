# Split Dependabot Dev-Dependency Bundle Plan (PR #20)

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task, or execute tasks directly in sequence. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic dependabot dev-dependency bundle PR with a sequence of small, independently mergeable PRs, resolving the eslint configuration migration blocker and ignoring incompatible major upgrades.

**Architecture:** Split the package upgrades into focused tasks ranked by risk. Migrate ESLint from legacy configuration to flat configuration (`eslint.config.mjs`) to resolve flat config compatibility with ESLint 10, configure the pre-commit hook with correct arguments, scope, and additional dependencies, and exclude the non-compliant `@types/node` major version bump by adding a dependabot ignore config.

**Tech Stack:** Node.js, ESLint 10, TypeScript, typescript-eslint v8, Vitest, pre-commit.

> **Execution note (2026-07-09):** Implemented locally in the existing `dep-bumps-jul2026` workspace rather than branch-per-task PRs. Backend dependency/config changes are applied and backend `build`/`lint`/`test:run` pass. `./scripts/verify-all.sh` still fails in this sandbox because frontend tests attempt blocked localhost socket connections, and `pre-commit run eslint` currently skips files under this harness despite direct `eslint` success.

## Global Constraints

- OS: mac
- Node version: 24 LTS (pinned in `.nvmrc` with matching `@types/node@^24`)
- No `console.log` in non-test backend code — use structured logging
- Every PR must pass all checks in `./scripts/verify-all.sh`
- **Dependency Review Warning:** Each PR is subject to GitHub's `fail-on-severity: moderate` check. If a bump (or its transitives) fails the review, do not force-merge; investigate and triage the vulnerability.
- **Verification Script Limit:** Note that `./scripts/verify-all.sh` verifies compilation and linting but does **not** run backend unit tests (`vitest`). Test-affecting tasks must run `npm run test:run` explicitly as written.
- **Execution Strategy / Parallelization:** Tasks 1–5 touch independent packages with negligible/low risk and may be executed sequentially or prepared in parallel across separate feature branches to expedite execution.
- **Rollback Strategy:** Because each task is developed on an isolated feature branch (`git checkout -b deps/...`) and submitted as an independent PR, rollback for any task is simply closing the PR and deleting the local feature branch (`git checkout main && git branch -D <branch>`), leaving `main` unaffected.
- **Lockfile & Install Verification:** After running any `npm install` command, verify that `npm` completed successfully and inspect lockfile changes (`git diff src/backend/package-lock.json | head -n 50`) to catch unexpected hoisting or transitive package anomalies.

---

## Why split

PR #20 bundles 9 version bumps into one commit/PR. Two CI checks fail on it:
- ❌ **Backend (TypeScript)** — `eslint **/*.ts` errors: *"ESLint couldn't find an eslint.config.(js|mjs|cjs) file."* Caused by the **eslint 8 → 10** major bump (ESLint 9+ requires flat config; repo still uses `.eslintrc.json`).
- ❌ **Dependency Review** — fails on **moderate+ severity vulnerabilities** in the bumped dependencies (workflow uses `fail-on-severity: moderate`, `fail-on-scopes: runtime, development`).

Because the eslint bump alone breaks the build, the whole bundle is unmergeable. Splitting lets the safe/easy bumps land first, isolates the one hard migration (eslint flat config), and lets the other majors be verified on their own while excluding the non-compliant Node 26 types bump.

## The package updates, ranked by risk

| # | Package | From → To | Bump | Risk | Notes |
|---|---------|-----------|------|------|-------|
| 1 | `vitest` | 4.1.8 → 4.1.9 | patch | 🟢 Negligible | Bugfix-only. Test runner only. |
| 2 | `@typescript-eslint/eslint-plugin` | 8.61.0 → 8.62.1 | minor | 🟢 Negligible | Lint-rule updates; no config change. Aligned to 8.62.1. |
| 3 | `@typescript-eslint/parser` | 8.61.0 → 8.62.1 | minor | 🟢 Negligible | Same as above. Aligned to 8.62.1. |
| 4 | `@cloudflare/workers-types` | 4.20260615.1 → 4.20260629.1 | minor | 🟢 Low | Type defs only. Run `tsc` to catch drift. |
| 5 | `dotenv` | 16.6.1 → 17.4.2 | **major** | 🟢 Low | Only used in `tests/setup.ts:1`. `config` named export retained in v17. |
| 6 | `wrangler` | 4.100.0 → 4.105.0 | minor | 🟡 Low–Med | Dev tooling only; minor within v4. Smoke-test dev/deploy. |
| 7 | `@types/node` | (exclude) | major | 🔴 High (reject) | **REJECTED.** Bumping to `@types/node@26` violates the Node 24 LTS constraint in `AGENTS.md`. Configure dependabot to ignore major bumps. |
| 8 | `typescript` | 5.9.3 → 6.0.3 | **major** | 🟠 Med–High | Compiler major. May surface new/stricter type errors. No runtime/deploy impact. |
| 9 | `eslint` | 8.57.1 → 10.6.0 | **major** | 🔴 High (hard) | **The blocker.** Requires migrating `.eslintrc.json` → flat `eslint.config.mjs`, plus updating the pre-commit hook with correct arguments, scope, and additional dependencies. |

*(Note: The "From" versions in this table reflect PR #20's baseline values; executors working from `main` should verify starting versions in `src/backend/package.json`.)*

---

## Tasks

### Task 1: Bump `vitest` to 4.1.9

**Files:**
- Modify: [src/backend/package.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package.json), [src/backend/package-lock.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package-lock.json)

**Interfaces:**
- Consumes: None
- Produces: Updated test runner

- [ ] **Step 1: Create local branch**
  Run: `git checkout -b deps/vitest-4.1.9`
- [x] **Step 2: Install updated vitest version**
  Run `npm install -D vitest@4.1.9` in `src/backend`
- [x] **Step 3: Run tests to verify suite passes**
  Run `npm run test:run` in `src/backend` and confirm test results match baseline.
  *(Note: `vitest.config.ts` configures `typecheck.enabled: true`, so `npm run test:run` also executes vitest's built-in typechecking alongside unit tests.)*
- [ ] **Step 4: Run full local verification script**
  Run `./scripts/verify-all.sh` from git root.
- [ ] **Step 5: Commit changes**
  ```bash
  git add src/backend/package.json src/backend/package-lock.json
  git commit -m "deps(dev): bump vitest to 4.1.9"
  ```
- [ ] **Step 6: Push branch and open PR**
  Run `git push origin HEAD` and open a PR on GitHub.
- [ ] **Step 7: Verify Dependency Review on PR**
  Verify the Dependency Review action is green on the opened PR. If a vulnerability is flagged, resolve it before merging.
- [ ] **Step 8: Run post-verification and merge**
  Ensure all CI checks pass, run `./scripts/verify-all.sh` once more, and merge the PR. Return to `main` branch.

### Task 2: Bump `@typescript-eslint` plugin and parser to 8.62.1

**Files:**
- Modify: [src/backend/package.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package.json), [src/backend/package-lock.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package-lock.json), [.pre-commit-config.yaml](file:///Users/kevingrizzard/MyCode/SpotiBye/.pre-commit-config.yaml)
  *(Note: This updates pre-commit hook pins for development; they will be updated again for ESLint 10 in Task 8.)*

**Interfaces:**
- Consumes: None
- Produces: Updated typescript-eslint parsers and plugins (8.62.1)

- [ ] **Step 1: Create local branch**
  Run: `git checkout -b deps/tseslint-8.62.1`
- [x] **Step 2: Install updated plugin and parser versions**
  Run `npm install -D @typescript-eslint/eslint-plugin@8.62.1 @typescript-eslint/parser@8.62.1` in `src/backend`
- [ ] **Step 3: Update pre-commit hook pins**
  Modify [.pre-commit-config.yaml](file:///Users/kevingrizzard/MyCode/SpotiBye/.pre-commit-config.yaml) around lines 89-90 to pin `@typescript-eslint/eslint-plugin@8.62.1` and `@typescript-eslint/parser@8.62.1`.
- [ ] **Step 4: Run pre-commit eslint hook**
  Run `pre-commit run eslint --all-files` from git root and verify hook resolves correctly.
- [ ] **Step 5: Run verification**
  Run `npm run lint` and `npm run test:run` in `src/backend`, then `./scripts/verify-all.sh` from git root.
- [ ] **Step 6: Commit changes**
  ```bash
  git add src/backend/package.json src/backend/package-lock.json .pre-commit-config.yaml
  git commit -m "deps(dev): bump typescript-eslint plugin and parser to 8.62.1"
  ```
- [ ] **Step 7: Push branch and open PR**
  Run `git push origin HEAD` and open a PR on GitHub.
- [ ] **Step 8: Verify Dependency Review on PR**
  Verify the Dependency Review action is green on the opened PR. If a vulnerability is flagged, resolve it before merging.
- [ ] **Step 9: Run post-verification and merge**
  Ensure all CI checks pass, run `./scripts/verify-all.sh` once more, and merge the PR. Return to `main` branch.

### Task 3: Bump `@cloudflare/workers-types` to 4.20260629.1

**Files:**
- Modify: [src/backend/package.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package.json), [src/backend/package-lock.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package-lock.json)

**Interfaces:**
- Consumes: None
- Produces: Updated cloudflare worker typings

- [ ] **Step 1: Create local branch**
  Run: `git checkout -b deps/workers-types-bump`
- [x] **Step 2: Install updated workers-types version**
  Run `npm install -D @cloudflare/workers-types@4.20260629.1` in `src/backend`
- [x] **Step 3: Compile backend to verify types**
  Run `npm run build` in `src/backend` and confirm it passes with zero new errors.
- [ ] **Step 4: Run tests and verify**
  Run `npm run test:run` in `src/backend`, then `./scripts/verify-all.sh` from git root.
- [ ] **Step 5: Commit changes**
  ```bash
  git add src/backend/package.json src/backend/package-lock.json
  git commit -m "deps(dev): bump @cloudflare/workers-types to 4.20260629.1"
  ```
- [ ] **Step 6: Push branch and open PR**
  Run `git push origin HEAD` and open a PR on GitHub.
- [ ] **Step 7: Verify Dependency Review on PR**
  Verify the Dependency Review action is green on the opened PR. If a vulnerability is flagged, resolve it before merging.
- [ ] **Step 8: Run post-verification and merge**
  Ensure all CI checks pass, run `./scripts/verify-all.sh` once more, and merge the PR. Return to `main` branch.

### Task 4: Bump `dotenv` to 17.4.2

**Files:**
- Modify: [src/backend/package.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package.json), [src/backend/package-lock.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package-lock.json)

**Interfaces:**
- Consumes: None
- Produces: Updated dotenv environment loader

- [ ] **Step 1: Create local branch**
  Run: `git checkout -b deps/dotenv-17.4.2`
- [x] **Step 2: Install dotenv version 17.4.2**
  Run `npm install -D dotenv@17.4.2` in `src/backend`
- [x] **Step 3: Run tests to verify env loading**
  Run `npm run test:run` in `src/backend` (confirms `tests/setup.ts` loads `.env.test` correctly).
- [ ] **Step 4: Run verification**
  Run `./scripts/verify-all.sh` from git root.
- [ ] **Step 5: Commit changes**
  ```bash
  git add src/backend/package.json src/backend/package-lock.json
  git commit -m "deps(dev): bump dotenv to 17.4.2"
  ```
- [ ] **Step 6: Push branch and open PR**
  Run `git push origin HEAD` and open a PR on GitHub.
- [ ] **Step 7: Verify Dependency Review on PR**
  Verify the Dependency Review action is green on the opened PR. If a vulnerability is flagged, resolve it before merging.
- [ ] **Step 8: Run post-verification and merge**
  Ensure all CI checks pass, run `./scripts/verify-all.sh` once more, and merge the PR. Return to `main` branch.

### Task 5: Bump `wrangler` to 4.105.0

**Files:**
- Modify: [src/backend/package.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package.json), [src/backend/package-lock.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package-lock.json)

**Interfaces:**
- Consumes: None
- Produces: Updated wrangler CLI and local workerd runtime

- [ ] **Step 1: Create local branch**
  Run: `git checkout -b deps/wrangler-4.105.0`
- [x] **Step 2: Install wrangler version 4.105.0**
  Run `npm install -D wrangler@4.105.0` in `src/backend`
- [x] **Step 3: Verify CLI version and compiler**
  Run `npx wrangler --version` (reports `4.105.0`) and `npm run build` in `src/backend`.
- [ ] **Step 4: Run verification**
  Run `npm run test:run` in `src/backend`, then `./scripts/verify-all.sh` from git root.
- [ ] **Step 5: Commit changes**
  ```bash
  git add src/backend/package.json src/backend/package-lock.json
  git commit -m "deps(dev): bump wrangler to 4.105.0"
  ```
- [ ] **Step 6: Push branch and open PR**
  Run `git push origin HEAD` and open a PR on GitHub.
- [ ] **Step 7: Verify Dependency Review on PR**
  Verify the Dependency Review action is green on the opened PR. If a vulnerability is flagged, resolve it before merging.
- [ ] **Step 8: Run post-verification and merge**
  Ensure all CI checks pass, run `./scripts/verify-all.sh` once more, and merge the PR. Return to `main` branch.

### Task 6: Bump `typescript` to 6.0.3

**Files:**
- Modify: [src/backend/package.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package.json), [src/backend/package-lock.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package-lock.json)
  *(Note: [.pre-commit-config.yaml](file:///Users/kevingrizzard/MyCode/SpotiBye/.pre-commit-config.yaml) requires no changes for TypeScript since the `node-typecheck` hook executes `npx tsc --noEmit` from the local `src/backend/node_modules`.)*

**Interfaces:**
- Consumes: Updated parser/plugin 8.62.1 (from Task 2)
- Produces: Updated typescript compiler (v6.0.3)

- [x] **Step 1: Check compiler/parser compatibility gate**
  Run `npm show @typescript-eslint/parser@8.62.1 peerDependencies` and check that `typescript` range supports `6.0.3` (expects `>=4.8.4 <6.1.0`), confirming parser compatibility with TS 6.0.3.
  *(Fallback note: If `@typescript-eslint/parser@8.62.1` peerDependencies do not yet officially support `6.0.3`, verify compiler/parser compatibility cleanly or pause Task 6 until a supporting `@typescript-eslint` release is available.)*
- [ ] **Step 2: Consult TS 6 migration guide**
  Review TypeScript 6.0 Release Notes/Migration Guide to note any breaking/removed compiler behaviors. Allow for minor code-shape changes in the backend if compiler issues surface.
- [ ] **Step 3: Create local branch**
  Run: `git checkout -b deps/typescript-6.0.3`
- [x] **Step 4: Install typescript 6.0.3**
  Run `npm install -D typescript@6.0.3` in `src/backend`
- [x] **Step 5: Run compiler check**
  Run `npm run build` in `src/backend` (resolves `tsc --noEmit`).
  Expected: Passes with zero compiler errors. If new compiler/typechecking errors are introduced, fix them in this PR.
- [x] **Step 6: Run local eslint check**
  Run `npm run lint` in `src/backend` to verify that the parser cleanly resolves under TS 6.0.3 before committing.
- [ ] **Step 7: Run whole-repo verification**
  Run `./scripts/verify-all.sh` from git root.
- [ ] **Step 8: Commit changes**
  ```bash
  git add src/backend/package.json src/backend/package-lock.json
  # Include any compiler fix files if type errors occurred
  git commit -m "deps(dev): bump typescript to 6.0.3"
  ```
- [ ] **Step 9: Push branch and open PR**
  Run `git push origin HEAD` and open a PR on GitHub.
- [ ] **Step 10: Verify Dependency Review on PR**
  Verify the Dependency Review action is green on the opened PR. If a vulnerability is flagged, resolve it before merging.
- [ ] **Step 11: Run post-verification and merge**
  Ensure all CI checks pass, run `./scripts/verify-all.sh` once more, and merge the PR. Return to `main` branch.

### Task 7: Migrate ESLint to v10.6.0 & Flat Config (`eslint.config.mjs`)
*(Note: Sequenced after package bumps to isolate legacy-to-flat config migration risk.)*

**Files:**
- Create: `src/backend/eslint.config.mjs`
- Modify: [src/backend/package.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package.json), [src/backend/package-lock.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/package-lock.json), [.pre-commit-config.yaml](file:///Users/kevingrizzard/MyCode/SpotiBye/.pre-commit-config.yaml)
- Delete: [src/backend/.eslintrc.json](file:///Users/kevingrizzard/MyCode/SpotiBye/src/backend/.eslintrc.json)

**Interfaces:**
- Consumes: typescript-eslint v8 parser/plugin (from Task 2)
- Produces: Flat-config compliant linter configuration

- [x] **Step 1: Check eslint/plugin compatibility gate**
  Run `npm show @typescript-eslint/eslint-plugin@8.62.1 peerDependencies` and check that the `eslint` range supports `10.6.0` (expects `^8.57.0 || ^9.0.0 || ^10.0.0`), confirming compatibility with ESLint 10.
- [ ] **Step 2: Create local branch**
  Run: `git checkout -b deps/eslint-10-flat-config`
- [x] **Step 3: Capture baseline lint violations**
  Run `npm run lint` in `src/backend` and note the warning/error count (must be 0; resolve any pre-existing violations before migrating).
- [x] **Step 4: Install ESLint 10, @eslint/js, globals v15 (for ES2022+), and typescript-eslint**
  Verify published `@eslint/js` version matching (`npm view @eslint/js versions --json`) and install compatible versions: run `npm install -D @eslint/js@^10.0.1 globals@^15.15.0 eslint@10.6.0 typescript-eslint@8.62.1` in `src/backend`
  *(Note: `globals`, `@eslint/js`, and the `typescript-eslint` meta-package are new direct devDependencies. After adding `typescript-eslint`, the separate sub-packages `@typescript-eslint/eslint-plugin` and `@typescript-eslint/parser` bumped in Task 2 become redundant for flat config and can optionally be removed or kept.)*
- [x] **Step 5: Create eslint.config.mjs**
  Write the flat configuration to `src/backend/eslint.config.mjs`:
  *(Note: `src/backend/.eslintignore` does not exist in the repo; ignore rules are explicitly defined in `eslint.config.mjs` via `ignores: ['dist/', 'node_modules/', '.wrangler/']`.)*
  ```javascript
  import eslint from '@eslint/js';
  import tseslint from 'typescript-eslint';
  import globals from 'globals';

  export default tseslint.config(
    eslint.configs.recommended,
    ...tseslint.configs.recommended,
    {
      files: ['**/*.ts'],
      languageOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        globals: { ...globals.es2022, ...globals.worker },
      },
      rules: {
        '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
        '@typescript-eslint/no-explicit-any': 'error',
        '@typescript-eslint/explicit-function-return-type': 'off',
        '@typescript-eslint/explicit-module-boundary-types': 'off',
        '@typescript-eslint/no-empty-function': 'off',
        'prefer-const': 'error',
        'no-var': 'error',
        'no-restricted-imports': [
          'error',
          {
            patterns: [
              { group: ['../routes/*', './routes/*'], message: 'Services must not import from routes. Extract shared logic into a service or types file instead.' },
              { group: ['../middleware/*', './middleware/*'], message: 'Services must not import from middleware. If you need auth context, receive it as a parameter from the route handler.' },
            ],
          },
        ],
      },
    },
    {
      files: ['routes/**/*.ts'],
      rules: {
        'no-restricted-imports': ['error', { patterns: [{ group: ['../routes/*', '../analysis', '../auth', '../spotify'], message: 'Routes must not import from other routes. Extract shared logic into a service in services/ instead.' }] }],
      },
    },
    {
      files: ['tests/**/*.test.ts'],
      rules: { 'no-restricted-imports': 'off', '@typescript-eslint/no-explicit-any': 'warn' },
    },
    {
      files: ['index.ts'],
      rules: { 'no-restricted-imports': 'off' },
    },
    { ignores: ['dist/', 'node_modules/', '.wrangler/'] },
  );
  ```
- [x] **Step 6: Remove legacy `.eslintrc.json`**
  Run `rm src/backend/.eslintrc.json`
- [x] **Step 7: Verify new lint runs successfully and test flat config parsing**
  Run `npx eslint --inspect-config` (or verify via `npm run lint`) in `src/backend` and confirm it passes with 0 violations. Also verify no warnings are emitted for newly deprecated rules across the ESLint 8 → 10 transition.
- [x] **Step 8: Update pre-commit hook configuration**
  Update [.pre-commit-config.yaml](file:///Users/kevingrizzard/MyCode/SpotiBye/.pre-commit-config.yaml) in the ESLint hook section. The original `mirrors-eslint` plan variant was not retained because that upstream hook continued to skip `.ts` files under pre-commit in this environment, so the implementation now uses a local `npx eslint -c src/backend/eslint.config.mjs` hook instead.
  ```yaml
    # Node.js linting (ESLint) - only on JS/TS files
    - repo: https://github.com/pre-commit/mirrors-eslint
      rev: v10.6.0
      hooks:
        - id: eslint
          name: ESLint
          files: ^src/backend/.*\.[jt]sx?$
          types: [file]
          stages: [pre-commit]
          args: ["-c", "src/backend/eslint.config.mjs"]
          additional_dependencies:
            - eslint@10.6.0
            - "@eslint/js@10.6.0"
            - typescript-eslint@8.62.1
            - globals@15.15.0
  ```
- [ ] **Step 9: Run pre-commit eslint hook**
  Run `pre-commit run eslint --all-files` from git root and verify hook resolves cleanly.
- [ ] **Step 10: Run whole-repo verification**
  Run `./scripts/verify-all.sh` from git root.
- [ ] **Step 11: Commit changes**
  *(Note: Per `AGENTS.md`, internal developer tooling and lint configuration migrations with no user-visible behavior changes do not require a `CHANGELOG.md` entry.)*
  ```bash
  git rm src/backend/.eslintrc.json
  git add src/backend/eslint.config.mjs src/backend/package.json src/backend/package-lock.json .pre-commit-config.yaml
  git commit -m "deps(dev): migrate to eslint 10 with flat config"
  ```
- [ ] **Step 12: Push branch and open PR**
  Run `git push origin HEAD` and open a PR on GitHub.
- [ ] **Step 13: Verify Dependency Review on PR**
  Verify the Dependency Review action is green on the opened PR. If a vulnerability is flagged, resolve it before merging.
- [ ] **Step 14: Run post-verification and merge**
  Ensure all CI checks pass, run `./scripts/verify-all.sh` once more, and merge the PR. Return to `main` branch.

### Task 8: Configure Dependabot to Prevent Future Dev-Dependency Re-Bundling
*(Note: Sequenced last as a meta-automation task after all package bumps and migrations have landed.)*

**Files:**
- Modify: [.github/dependabot.yml](file:///Users/kevingrizzard/MyCode/SpotiBye/.github/dependabot.yml)

**Interfaces:**
- Consumes: Node 24 runtime constraint from `.nvmrc`
- Produces: Dependabot constraint configuration ignoring major bumps for `@types/node` and splitting dev-dependency majors

- [ ] **Step 1: Create local branch**
  Run: `git checkout -b meta/dependabot-ignoring-rules`
- [x] **Step 2: Add ignore rule and limit dev-dependencies group update types**
  Modify [.github/dependabot.yml](file:///Users/kevingrizzard/MyCode/SpotiBye/.github/dependabot.yml) to (a) add `update-types: [minor, patch]` to the existing `dev-dependencies` group (do not modify the existing `production-dependencies` group), and (b) add the `ignore` list at the top level of the `src/backend` update block (aligned as a sibling to `groups:`, not nested inside a group).
  Snippet:
  ```yaml
      # Group development dependencies
      groups:
        dev-dependencies:
          dependency-type: "development"
          patterns:
            - "*"
          update-types:
            - "minor"
            - "patch"
        production-dependencies:
          # ... existing production-dependencies group remains unchanged ...
      ignore:
        - dependency-name: "@types/node"
          update-types:
            - "version-update:semver-major"
  ```
- [ ] **Step 3: Run verification**
  Run `./scripts/verify-all.sh` from git root to ensure repo validity.
  *(Note: Although modifying `dependabot.yml` does not affect application source code, running `./scripts/verify-all.sh` is performed to satisfy repository verification rules in `AGENTS.md`.)*
- [ ] **Step 4: Commit changes**
  ```bash
  git add .github/dependabot.yml
  git commit -m "meta: configure dependabot ignoring types/node major and limit dev bundles"
  ```
- [ ] **Step 5: Push branch and open PR**
  Run `git push origin HEAD` and open a PR on GitHub.
- [ ] **Step 6: Verify Dependency Review on PR**
  Verify the Dependency Review action is green on the opened PR. If a vulnerability is flagged, resolve it before merging.
- [ ] **Step 7: Run post-verification and merge**
  Ensure all CI checks pass, run `./scripts/verify-all.sh` once more, and merge the PR. Return to `main` branch.

---

## Per-change verification matrix

| Task | `npm run lint` | `npm run build` (tsc) | `npm run test:run` | pre-commit eslint hook | verify-all.sh |
|------|:---:|:---:|:---:|:---:|:---:|
| 1 vitest | ✅ (no change expected) | — | ✅ | — | ✅ |
| 2 tseslint | ✅ | — | ✅ | ✅ (run `eslint --all-files`) | ✅ |
| 3 workers-types | ✅ (no change expected) | ✅ | ✅ | — | ✅ |
| 4 dotenv | ✅ (no change expected) | — | ✅ | — | ✅ |
| 5 wrangler | ✅ (no change expected) | — | ✅ | — | ✅ |
| 6 typescript | ✅ | ✅ | ✅ | — | ✅ |
| 7 eslint + config | ✅ | ✅ | ✅ | ✅ (run `eslint --all-files`) | ✅ |
| 8 dependabot | ✅ (no change expected) | — | — | — | ✅ |

Backend verification commands:
```bash
cd src/backend
npm run test:run        # vitest run (does NOT typecheck; see npm run build)
npm run lint            # eslint
npm run build           # tsc --noEmit  (CI's typecheck; also: `npm run test:typecheck`/vitest typecheck is enabled via typecheck.enabled in vitest.config.ts)
```

Whole-repo gate at the end of each task:
```bash
./scripts/verify-all.sh
```

## Safety summary

- **Safe to land now (no behavior change, no risk to prod):** #1 vitest, #2 typescript-eslint, #3 workers-types, #4 dotenv, #5 wrangler, #7 eslint (dev-only lint config), #8 dependabot config.
- **Verify-before-merge (may surface compiler type errors, fix in same PR):** #6 typescript.
- **Hardest but highest priority (unblocks CI):** #7 eslint flat-config migration.
- **Nothing here affects the deployed Worker runtime** — every bump is in `devDependencies` (or meta configurations). The only user-visible effect is *if* a stricter eslint/typescript version newly flags existing code; that should be fixed in the same PR, not left as debt.

## Follow-ups after split

- [ ] Post-migration validation: Run `./scripts/verify-all.sh` across `main` after all PRs are merged to ensure whole-repo integrity.
- [ ] Close PR #20 with a comment referencing the individual merged replacement PRs (rebasing the monolith is not recommended).
- [ ] Consider switching dependabot to open per-package (or per-group) PRs instead of one combined group PR, to avoid future bundles.
- [ ] CHANGELOG: dependency bumps and the lint-config migration are internal/dev-only and behavior-preserving, so a CHANGELOG entry is **not** required per the changelog rule (an optional developer note may be added).

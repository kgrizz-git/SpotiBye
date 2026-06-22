# AGENTS.md

> This is the entry point for AI coding agents (Copilot, Codex, etc.) working in this repository.
> Keep this file short. Follow the pointers to find deeper context.
>
> **Claude Code users:** see [`CLAUDE.md`](CLAUDE.md) for a focused entry point.

---

## What is SpotiBye?

SpotiBye is a desktop application that lets users export their Spotify playlists to CSV, Excel, or JSON files. It consists of:

- **Frontend** — Python desktop GUI built with Kivy/KivyMD (`src/frontend/`)
- **Backend** — Cloudflare Worker written in TypeScript using Hono (`src/backend/`)
- **Auth flow** — Spotify OAuth 2.0 PKCE, tokens managed by the backend

Users log in with Spotify, the backend exchanges tokens, and the frontend calls backend API routes to fetch playlists and trigger exports.

---

## Navigation

- **Start here:** [dev-docs/code-map.md](dev-docs/code-map.md) — file index, Mermaid diagrams, and role of every source file
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) — layer contracts, data flow, domain breakdown
- **All docs:** [docs/index.md](docs/index.md) — full navigable map
- **Dependency graph:** [dev-docs/dependency-graph.json](dev-docs/dependency-graph.json) — machine-readable import graph for impact analysis

---

## Plans and Documentation Conventions

- New implementation plans go in `docs/exec-plans/active/YYYY-MM-DD-topic.md`.
- Plans must use checkbox steps (`- [ ]`) and executors must mark steps complete (`- [x]`) as work is completed.
- If a plan comes from `dev-docs/TO_DO.md`, keep that TODO linked while active and mark it complete when the plan is finished.
- Completed or superseded plans move to `docs/exec-plans/completed/` and must be indexed in `docs/exec-plans/completed/README.md`.
- Design decisions that should remain durable go in `docs/design-docs/`.
- Third-party API/platform reference notes go in `docs/references/`.
- Short-lived investigations, audits, and working notes go in `dev-docs/`.
- Before creating a new doc, check `docs/index.md`, `dev-docs/README.md`, and `rg` for an existing page to update.
- Do not leave completed plans in `active/`, and do not create new root-level `plans/` files. (Enforced by pre-commit hook.)
- IDE security rules live in `.cursor/rules/` only. `.windsurf/rules/` and `.qwen/` have been removed and are gitignored.

---

## Key Principles

1. Parse data shapes at boundaries — never pass raw, unvalidated API responses between layers
2. All Spotify API calls go through `services/spotify.ts` only
3. Export cursors are always persisted before any destructive step
4. Cache keys are namespaced: `<user_id>:<resource_type>:<identifier>`
5. No `console.log` in non-test backend code — use structured logging
6. No bare `except:` in Python — always name the exception type

Full list: [docs/golden-principles.md](docs/golden-principles.md)

---

## Sub-Agents

For context-heavy analysis tasks, use sub-agents to prevent context rot:
- Architecture analysis: invoke architecture-analyst (activates on "analyze architecture", "layer violations")
- Dependency impact: invoke dependency-analyst (activates on "impact", "dependencies")
- Test coverage: invoke test-coverage-analyst (activates on "test coverage", "coverage gaps")
- Security scanning: invoke security-scanner (activates on "security", "vulnerability")
- Behavior evaluation: invoke evaluator (activates on "evaluate this change", "verify behavior", "does this satisfy")

Sub-agents return condensed findings with citations, keeping parent context clean.

## Context Budget

On complex multi-step tasks, plan for partial completion: finish each step to a clean stopping point (tests passing, no broken imports) before moving to the next. If context is filling up, stop at the current clean state and summarize what remains rather than rushing to finish.

---

## Running Tests & Verification

**Quick verification:** Run `./scripts/verify-all.sh` from repo root (silent on success, errors only on failure)

**Backend (TypeScript):**
```bash
cd src/backend
npm run test:run        # vitest
npm run lint            # eslint
```

**Frontend (Python):**
```bash
# Always use the venv's pytest from the repo root — never the system pytest
KIVY_WINDOW=headless KIVY_NO_ENV_CONFIG=1 .venv/bin/pytest src/frontend/tests/ -v
```

---

## Backend Deployments

Before saying backend changes are deployed, or when asked whether backend deployment is needed, run:

```bash
./scripts/backend-deploy-status.sh <backend-url>
```

Use the production or development Worker URL that matches the question. If `Needs Deployment: YES`, tell the user which committed or uncommitted backend/workflow files differ from the live `release_sha` and ask before deploying. Treat `src/backend/.deployed-commit.json` as a local cache only; the live `/health` metadata is the source of truth.

Run the script from a fresh local checkout of the target branch, normally `main` after pulling. Detached HEADs, stale branches, and feature branches can make the `release_sha..HEAD` comparison look different from the deployment branch.

---

## Changelog Rule

Any user-visible change must update `CHANGELOG.md` in the same PR.
See [.github/copilot-instructions.md](.github/copilot-instructions.md) for details.

# AGENTS.md

> This is the entry point for AI coding agents (Copilot, Codex, etc.) working in this repository.
> Keep this file short. Follow the pointers to find deeper context.

---

## What is SpotiBye?

SpotiBye is a desktop application that lets users export their Spotify playlists to CSV, Excel, or JSON files. It consists of:

- **Frontend** — Python desktop GUI built with CustomTkinter (`src/frontend/`)
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

## Key Principles

1. Parse data shapes at boundaries — never pass raw, unvalidated API responses between layers
2. All Spotify API calls go through `services/spotify.ts` only
3. Export cursors are always persisted before any destructive step
4. Cache keys are namespaced: `<user_id>:<resource_type>:<identifier>`
5. No `console.log` in non-test backend code — use structured logging
6. No bare `except:` in Python — always name the exception type

Full list: [docs/golden-principles.md](docs/golden-principles.md)

---

## Skills

This repo uses skills for progressive disclosure. Skills load automatically based on context:
- Spotify API: activates on "spotify", "playlist", "auth"
- Cloudflare Worker: activates on "cloudflare", "worker", "deployment"
- Testing: activates on "test", "pytest", "vitest"
- Export formats: activates on "export", "csv", "excel", "json"
- Dependency analysis: activates on "dependency", "impact", "graph"
- Security: activates on "security", "vulnerability", "audit", "crypto", "certificate"

---

## Sub-Agents

For context-heavy analysis tasks, use sub-agents to prevent context rot:
- Architecture analysis: invoke architecture-analyst (activates on "analyze architecture", "layer violations")
- Dependency impact: invoke dependency-analyst (activates on "impact", "dependencies")
- Test coverage: invoke test-coverage-analyst (activates on "test coverage", "coverage gaps")
- Security scanning: invoke security-scanner (activates on "security", "vulnerability")

Sub-agents return condensed findings with citations, keeping parent context clean.

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
cd src/frontend
pytest tests/
```

---

## Changelog Rule

Any user-visible change must update `CHANGELOG.md` in the same PR.
See [.github/copilot-instructions.md](.github/copilot-instructions.md) for details.

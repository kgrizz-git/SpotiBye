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

## Repository Map

| Path | What it contains |
|------|-----------------|
| `src/backend/` | Cloudflare Worker: routes, services, middleware, types |
| `src/frontend/` | Python CustomTkinter desktop app: screens, services, auth, caching, utils |
| `docs/` | All design docs, plans, references, and architecture guides |
| `dev-docs/` | Internal developer notes, TO_DO, and execution plans for in-flight work |
| `ARCHITECTURE.md` | Layer contracts, data flow, domain breakdown |
| `QUALITY_SCORE.md` | Per-domain quality grades and known gaps |
| `CHANGELOG.md` | User-visible changes by release |
| `SECURITY.md` | Security policy |
| `.github/copilot-instructions.md` | Coding conventions and golden principle pointers |
| `dev-docs/code-map.md` | **Start here for navigation** — file index, Mermaid diagrams, and role of every source file |
| `dev-docs/dependency-graph.json` | Machine-readable import graph (file → internal deps); use for impact analysis and dead-code detection |

---

## Key Design Docs

- **File map & diagrams:** [dev-docs/code-map.md](dev-docs/code-map.md) — every source file, its role, and Mermaid import graphs
- **Import graph (machine-readable):** [dev-docs/dependency-graph.json](dev-docs/dependency-graph.json) — JSON adjacency list for impact analysis
- Architecture decision: [docs/design-docs/cloudflare-worker-choice.md](docs/design-docs/cloudflare-worker-choice.md)
- Resumable export: [docs/design-docs/resumable-export-cursors.md](docs/design-docs/resumable-export-cursors.md)
- Spotify API migration notes: [docs/february-2026-spotify-migration-findings.md](docs/february-2026-spotify-migration-findings.md)
- Authentication flow: [docs/authentication-flow.md](docs/authentication-flow.md)

## All Docs Index

See [docs/index.md](docs/index.md) for a full navigable map of every document.

---

## Running Tests

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

## Layer Contracts (enforce mechanically — do not violate)

**Backend:**
- `routes/` → `services/` → `types/`
- `middleware/` is cross-cutting; routes may use it
- Routes must not import from other routes
- Services must not import from routes
- All Spotify API calls go through `services/spotify.ts` — no direct `fetch` to `api.spotify.com` in routes

**Frontend:**
- `screens/` → `services/` → `auth/` | `caching/` | `config/`
- `ui/` is leaf — no business logic
- `utils/` has no imports from other app layers

See [ARCHITECTURE.md](ARCHITECTURE.md) for full diagrams and rationale.

---

## Golden Principles (short form)

Full list: [docs/golden-principles.md](docs/golden-principles.md)

1. Parse data shapes at boundaries — never pass raw, unvalidated API responses between layers
2. All Spotify API calls go through `services/spotify.ts` only
3. Export cursors are always persisted before any destructive step
4. Cache keys are namespaced: `<user_id>:<resource_type>:<identifier>`
5. No `console.log` in non-test backend code — use structured logging
6. No bare `except:` in Python — always name the exception type
7. Prefer shared utilities over hand-rolled helpers; if logic appears twice, extract it

---

## Current Plans & Debt

- Active plans: [docs/exec-plans/active/](docs/exec-plans/active/)
- Completed plans: [docs/exec-plans/completed/](docs/exec-plans/completed/)
- Technical debt: [docs/tech-debt-tracker.md](docs/tech-debt-tracker.md)

---

## Changelog Rule

Any user-visible change must update `CHANGELOG.md` in the same PR.
See [.github/copilot-instructions.md](.github/copilot-instructions.md) for details.

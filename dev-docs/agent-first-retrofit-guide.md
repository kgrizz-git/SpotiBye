# Agent-First Retrofit Guide for SpotiBye

> Based on principles from OpenAI's [Harness Engineering](https://openai.com/index/harness-engineering/) post (February 2026).
> Goal: reshape this repo so AI coding agents (Copilot, Codex, etc.) can reason about, navigate, and modify it reliably — maximizing throughput while preserving coherence.

---

## Core Philosophy

**Humans steer. Agents execute.**

Agents can only work with what they can see inside the repository. Every architectural decision, constraint, or convention that lives in a Slack thread, someone's head, or an external doc is invisible to the agent and effectively does not exist. The discipline shifts from writing code to designing environments, specifying intent, and building feedback loops.

---

## Principle 1: AGENTS.md as Table of Contents

### What the article says
A monolithic `AGENTS.md` crowds out context, rots quickly, and becomes non-guidance. Instead, keep it ~100 lines max — a short map that tells the agent where to look, not everything it needs to know.

### SpotiBye today
- No `AGENTS.md` exists anywhere in the repo.
- `.github/copilot-instructions.md` exists but only covers changelog rules.

### Actions
1. **Create `AGENTS.md` at repo root** — ~100 lines covering:
   - What this project is (one paragraph)
   - Repo layout (backend = Cloudflare Worker TypeScript, frontend = Python CustomTkinter)
   - Pointers to `docs/`, `dev-docs/`, `CHANGELOG.md`, `SECURITY.md`
   - Pointer to this file for agent-first conventions
   - Where to find architecture, plans, and known debt
   - How to run tests (`vitest` for backend, pytest for frontend)
   - Golden principles summary (3–5 bullets; full list in separate doc)

2. **Expand `.github/copilot-instructions.md`** to include:
   - Layered architecture rules (see Principle 4)
   - Linting/formatting requirements
   - When to open a plan doc vs. just a PR

---

## Principle 2: Repository Knowledge as System of Record

### What the article says
All context the agent needs must exist as versioned, in-repo artifacts. Design docs, execution plans, architectural decisions, tech debt, and product specs should all live in a structured `docs/` hierarchy — not in external tools. A "doc-gardening" process keeps it fresh.

### SpotiBye today
- `docs/` is extensive but flat — no clear index, no design docs or exec-plan directories, no ARCHITECTURE.md.
- `dev-docs/` is a loose collection with a TO_DO and a route analysis.
- Plans exist under `docs/plans/` (good), but are not indexed.

### Actions
1. **Create `ARCHITECTURE.md` at repo root** describing:
   - The two-tier architecture: Python frontend ↔ Cloudflare Worker backend ↔ Spotify API
   - Domain breakdown: auth, export, analysis, caching, reccobeats
   - Package/module layering rules (see Principle 4)
   - Key data flows (OAuth PKCE, export pipeline, cursor-based resumable export)

2. **Add `docs/index.md`** as a navigable map of all docs — what each file is, its status (current/stale/draft).

3. **Create `docs/design-docs/`** for non-trivial decisions, with entries like:
   - `cloudflare-worker-choice.md`
   - `resumable-export-cursors.md`
   - `spotify-api-migration-feb-2026.md` (already exists as a flat file — move it here)

4. **Create `docs/exec-plans/active/` and `docs/exec-plans/completed/`** — move existing plan docs from `docs/plans/` into this structure, keeping only active ones open.

5. **Create `docs/tech-debt-tracker.md`** listing known shortcuts, brittle areas, and things to clean up. Agents use this to prioritize and avoid re-introducing known-bad patterns.

6. **Add a `QUALITY_SCORE.md`** grading each domain (auth, export, analysis, caching, frontend screens) on test coverage, error handling robustness, and documentation completeness. Agents use this to know where to invest effort.

---

## Principle 3: Agent Legibility is the Goal

### What the article says
Code should be optimized for an agent's ability to reason about it. Prefer "boring" well-documented technologies. Avoid opaque dependencies. Pull external context into the repo. Favor technologies with stable APIs and strong representation in training data.

### SpotiBye today
- Backend: TypeScript on Cloudflare Workers + Hono — well-documented, good choice.
- Frontend: Python + CustomTkinter — reasonable, but UI layer has limited agent training signal.
- External knowledge (e.g., Spotify API quirks, ReccoBeats integration, February 2026 migration findings) exists in docs but isn't connected to the code it describes.

### Actions
1. **Co-locate context with code.** Add doc-block comments at the top of these files pointing to the relevant design doc:
   - `src/backend/services/spotify.ts` → `docs/february-2026-spotify-migration-findings.md`
   - `src/backend/services/reccobeats.ts` → wherever ReccoBeats integration is documented
   - `src/backend/routes/export.ts` → `docs/plans/resumable-export-cursor-persistence-plan.md`

2. **Add a `references/` section inside `docs/`** for third-party API summaries:
   - `spotify-api-reference.md` — key endpoints used, known rate limits, quirks
   - `cloudflare-workers-constraints.md` — CPU time limits, KV limits, D1 constraints relevant to this app

3. **Annotate non-obvious architectural choices inline** so agents don't "fix" them:
   - Why JWT is used in `services/jwt.ts` rather than session cookies
   - Why caching is structured the way it is in `services/cache.ts`

---

## Principle 4: Enforce Architecture and Taste Mechanically

### What the article says
Strict layered architecture enforced by custom linters and structural tests prevents architectural drift at agent throughput. Enforce boundaries; allow autonomy within them. Write lint error messages as remediation instructions for the agent.

### SpotiBye today
- Backend has implicit layering (routes → services → types) but no enforcement.
- Frontend has a similar structure (screens → services → auth/caching/utils) but no enforcement.
- No custom linters exist.

### Actions

#### Backend (TypeScript)
1. **Define the layer contract in `ARCHITECTURE.md`:**
   ```
   routes/  →  services/  →  types/
   middleware/ is cross-cutting (auth, caching)
   routes must not import from other routes
   services must not import from routes
   ```

2. **Add an ESLint rule** (extend existing `.eslintrc.json`) enforcing no-restricted-imports between layers. Write the error message as a direct instruction: `"Routes must not call other routes directly. Extract shared logic to a service."`

3. **Add a Vitest structural test** (`tests/architecture.test.ts`) that statically checks import relationships using a simple regex/AST scan.

#### Frontend (Python)
1. **Define the layer contract:**
   ```
   screens/  →  services/  →  auth/ | caching/ | config/
   ui/ components are leaf nodes — no business logic
   utils/ has no imports from other app layers
   ```

2. **Add a pytest structural test** (`src/frontend/tests/test_architecture.py`) that walks imports and asserts no layer violations.

3. **Enforce naming conventions** for consistency — add a note to `AGENTS.md` (e.g., "service files are named `<domain>_service.py`, screen files are named `<Domain>Screen`").

#### Shared taste invariants (add to `.github/copilot-instructions.md`)
- No bare `except:` — always catch a specific exception type
- No `print()` in non-test code — use the logger
- All route handlers must validate input at the boundary before passing to services
- All exported data shapes must be defined as a TypeScript type or Python dataclass/TypedDict — no ad-hoc dicts

---

## Principle 5: Golden Principles and Continuous Garbage Collection

### What the article says
Encode "golden principles" — opinionated, mechanical rules — directly into the repo. Run recurring background cleanup tasks (doc-gardening, deduplication, style normalization) rather than spending a fixed chunk of time on it manually.

### SpotiBye today
- No golden principles document exists.
- Technical debt is partially tracked in `dev-docs/TO_DO.md` but informally.

### Actions
1. **Create `docs/golden-principles.md`** with explicit, mechanical rules such as:
   - Prefer shared utility functions over duplicated helpers — if something appears twice, extract it
   - Never probe a Spotify API response shape without validating it first (parse-don't-validate)
   - All Spotify API calls go through `services/spotify.ts` — no direct `fetch` to Spotify in routes
   - Export cursors are always persisted before any destructive step
   - Cache keys are always namespaced: `<user_id>:<resource_type>:<identifier>`

2. **Convert `dev-docs/TO_DO.md` into `docs/tech-debt-tracker.md`** with structured entries:
   ```
   | Area | Issue | Severity | First Seen |
   ```

3. **Add a recurring prompt** (saved in `docs/exec-plans/active/doc-gardening.md`) for periodic agent runs that:
   - Scan for golden principle violations and open fix PRs
   - Check that all services in `src/backend/services/` have a corresponding doc-block pointing to design docs
   - Update `QUALITY_SCORE.md`

---

## Principle 6: Application Legibility for Agents

### What the article says
Wire observability (logs, metrics, traces) and UI inspection (Chrome DevTools Protocol, screenshots) directly into the agent runtime so it can validate its own work, reproduce bugs, and run acceptance tests without human involvement.

### SpotiBye today
- Backend has Cloudflare-native logging — not locally inspectable in a dev loop.
- Frontend is a desktop GUI (CustomTkinter) — not browser-based.
- No structured logging format is enforced.

### Actions
1. **Enforce structured logging in the backend.** Replace any `console.log` calls in `src/backend/` with a structured logger that emits JSON. Add a golden principle and lint rule for this.

2. **Add a local dev observability note** in `ARCHITECTURE.md` explaining how to tail Cloudflare Worker logs with `wrangler tail` and what signals to look for during a dev loop.

3. **Add a smoke test script** (`scripts/smoke-test.sh` or similar) that:
   - Starts the Cloudflare dev worker (`wrangler dev`)
   - Runs a sequence of API calls exercising the main flows (auth, export, analysis)
   - Can be invoked by an agent to validate a change without manual QA

4. **For the frontend**, add a headless mode or a test harness that exercises key screen transitions programmatically (even if minimal), so agents can validate UI flow changes without a human clicking through.

---

## Principle 7: Short-Lived PRs and Minimal Blocking Gates

### What the article says
At agent throughput, corrections are cheap and waiting is expensive. Keep PRs small, test flakes non-blocking, and merge fast.

### SpotiBye today
- No CI configuration is visible at the repo root (no `.github/workflows/`).

### Actions
1. **Add a minimal CI workflow** (`.github/workflows/ci.yml`) that runs on every PR:
   - Backend: `npm run lint && npm run typecheck && npx vitest run`
   - Frontend: `pytest src/frontend/tests/`
   - Fail fast on type errors and lint errors; treat test flakes as follow-up items

2. **Add a PR template** (`.github/pull_request_template.md`) with a short checklist:
   - [ ] Golden principles respected
   - [ ] Relevant docs updated if behavior changed
   - [ ] CHANGELOG.md updated if user-visible

3. **Enforce small PRs** — add a note to `AGENTS.md`: "PRs should change one logical thing. If a change is larger than ~400 lines, split it."

---

## Quick-Start Checklist

In priority order, these are the highest-leverage moves:

| # | Action | Effort | Leverage |
|---|--------|--------|----------|
| 1 | Create `AGENTS.md` at repo root | Low | High — unlocks all agent runs |
| 2 | Create `ARCHITECTURE.md` | Medium | High — prevents structural drift |
| 3 | Create `docs/golden-principles.md` | Low | High — continuous quality enforcement |
| 4 | Add `docs/index.md` | Low | Medium — progressive disclosure for agents |
| 5 | Add structural lint rules (backend) | Medium | High — mechanically enforced architecture |
| 6 | Add structural test (frontend) | Medium | High — same for Python layer |
| 7 | Add CI workflow | Medium | Medium — fast feedback loop |
| 8 | Structured logging in backend | Low | Medium — agent-observable runtime |
| 9 | Smoke test script | Medium | Medium — agent self-validation |
| 10 | Migrate `docs/plans/` → exec-plan structure | Low | Medium — better plan discoverability |

---

## What Not to Do

- **Don't create one giant `AGENTS.md`** with all conventions. It rots, crowds context, and stops being read.
- **Don't put architecture decisions in Slack or external docs.** If the agent can't read it from the repo, it doesn't exist.
- **Don't over-engineer abstractions** just for agent consumption. Prefer boring, well-understood patterns.
- **Don't spend a fixed weekly block on cleanup.** Encode cleanup as recurring agent tasks instead.

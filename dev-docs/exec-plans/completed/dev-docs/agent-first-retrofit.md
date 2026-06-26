# Execution Plan: Agent-First Retrofit

**Source:** `dev-docs/agent-first-retrofit-guide.md`
**Goal:** Retrofit SpotiBye so AI coding agents can navigate, understand, and modify it reliably with minimal human hand-holding.
**Status:** In progress

---

## Phases

### Phase 1 — Navigation & Entry Points (highest leverage, no code changes)

| # | Task | Status | File(s) |
|---|------|--------|---------|
| 1.1 | Create `AGENTS.md` at repo root | ✅ Done | `/AGENTS.md` |
| 1.2 | Create `ARCHITECTURE.md` at repo root | ✅ Done | `/ARCHITECTURE.md` |
| 1.3 | Expand `.github/copilot-instructions.md` with layer rules and golden principle pointers | ✅ Done | `/.github/copilot-instructions.md` |

### Phase 2 — Knowledge Base (docs structure)

| # | Task | Status | File(s) |
|---|------|--------|---------|
| 2.1 | Create `docs/index.md` as navigable map of all docs | ✅ Done | `docs/index.md` |
| 2.2 | Create `dev-docs/guides/golden-principles.md` | ✅ Done | `dev-docs/guides/golden-principles.md` |
| 2.3 | Create `dev-docs/backlog/tech-debt-tracker.md` (structured debt log) | ✅ Done | `dev-docs/backlog/tech-debt-tracker.md` |
| 2.4 | Create `dev-docs/references/spotify-api-reference.md` | ✅ Done | `dev-docs/references/spotify-api-reference.md` |
| 2.5 | Create `dev-docs/references/cloudflare-workers-constraints.md` | ✅ Done | `dev-docs/references/cloudflare-workers-constraints.md` |
| 2.6 | Create `dev-docs/architecture/design-decisions/cloudflare-worker-choice.md` | ✅ Done | `dev-docs/architecture/design-decisions/cloudflare-worker-choice.md` |
| 2.7 | Create `dev-docs/architecture/design-decisions/resumable-export-cursors.md` | ✅ Done | `dev-docs/architecture/design-decisions/resumable-export-cursors.md` |
| 2.8 | Create `dev-docs/exec-plans/` structure with active/completed dirs | ✅ Done | `dev-docs/exec-plans/` |
| 2.9 | Create `QUALITY_SCORE.md` at repo root | ✅ Done | `/QUALITY_SCORE.md` |

### Phase 3 — Mechanical Enforcement

| # | Task | Status | File(s) |
|---|------|--------|---------|
| 3.1 | Add ESLint architectural no-restricted-imports rules to backend | ✅ Done | `src/backend/.eslintrc.json` |
| 3.2 | Add backend structural test | ✅ Done | `src/backend/tests/architecture.test.ts` |
| 3.3 | Add CI workflow | ✅ Done | `.github/workflows/ci.yml` |
| 3.4 | Add PR template | ✅ Done | `.github/pull_request_template.md` |

### Phase 4 — Code Legibility

| # | Task | Status | File(s) |
|---|------|--------|---------|
| 4.1 | Add doc-block comments to backend services pointing to design docs | ✅ Done | `src/backend/services/*.ts` |

---

## Decision Log

- **Kept `docs/plans/` in place** alongside new `dev-docs/exec-plans/`. Existing plan files are left as-is to avoid breaking links; future plans go under `exec-plans/`.
- **Skipped smoke-test script** for now — Cloudflare Worker requires `wrangler dev` which is environment-dependent; deferred to a future task in the tech-debt tracker.
- **Skipped frontend structural test** — Python layer has a simpler structure; add if/when the layer count grows.

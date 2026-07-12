# CLAUDE.md

> Claude Code entry point for SpotiBye. Focused subset of `AGENTS.md` — see that file for Copilot/Codex conventions.

---

## Navigation

- **Code map:** [dev-docs/code-map.md](dev-docs/code-map.md) — file index, Mermaid diagrams, role of every source file
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) — layer contracts, data flow, domain breakdown
- **User docs:** [docs/index.md](docs/index.md) — end-user documentation map
- **Developer docs:** [dev-docs/README.md](dev-docs/README.md) — contributor, agent, architecture, plan, and reference map
- **ReccoBeats API:** [dev-docs/reccobeats-api-contract.md](dev-docs/reccobeats-api-contract.md) — live response shapes, Spotify join via `href`, batch omission semantics
- **Sub-agents:** [.claude/sub-agents/](.claude/sub-agents/) — architecture-analyst, dependency-analyst, test-coverage-analyst, security-scanner, evaluator

---

## Running Tests & Verification

**Quick verification:** Run `./scripts/verify-all.sh` from repo root (silent on success, errors only on failure)

**Node version:** Backend CI runs on Node 24 LTS (pinned in `.nvmrc`, with matching `@types/node@^24`). With nvm/fnm shell integration, the version switches automatically on `cd`; without it, run `nvm use` first. CI's Node 24 environment is the source of truth — if you are on a different local Node, push to a branch and let CI verify.

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

# Type checking (also enforced as a pre-push hook)
.venv/bin/basedpyright src/frontend src/shared --level error
```

---

## Key Principles

1. Parse data shapes at boundaries — never pass raw, unvalidated API responses between layers
2. All Spotify API calls go through `services/spotify.ts` only
3. Export cursors are always persisted before any destructive step
4. Cache keys are namespaced: `<user_id>:<resource_type>:<identifier>`
5. No `console.log` in non-test backend code — use structured logging
6. No bare `except:` in Python — always name the exception type

Full list: [dev-docs/guides/golden-principles.md](dev-docs/guides/golden-principles.md)

---

## Plans & Docs Placement

- `docs/` is for end-user documentation only.
- `dev-docs/` is for developer, maintainer, and agent-facing material.
- New implementation plans → `dev-docs/exec-plans/active/YYYY-MM-DD-topic.md` (checkbox steps, mark complete as you go)
- Completed plans → move to `dev-docs/exec-plans/completed/` and index in its `README.md`
- Design decisions → `dev-docs/architecture/design-decisions/`
- Third-party API references → `dev-docs/references/`
- Short-lived investigations and audits → `dev-docs/investigations/` or `dev-docs/assessments/`
- Before creating a new doc, check `docs/index.md`, `dev-docs/README.md`, and run `rg "<topic>" dev-docs docs`

---

## Sub-Agent Activation

For context-heavy analysis, delegate to sub-agents to keep parent context clean:

- **Architecture analysis** — invoke `architecture-analyst` (triggers on "analyze architecture", "layer violations")
- **Dependency impact** — invoke `dependency-analyst` (triggers on "impact", "dependencies")
- **Test coverage** — invoke `test-coverage-analyst` (triggers on "test coverage", "coverage gaps")
- **Security** — invoke `security-scanner` (triggers on "security", "vulnerability")
- **Behavior evaluation** — invoke `evaluator` (triggers on "evaluate this change", "verify behavior")

---

## Changelog Rule

Any user-visible change must update `CHANGELOG.md` in the same PR.

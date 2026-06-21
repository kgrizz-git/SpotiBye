# CLAUDE.md

> Claude Code entry point for SpotiBye. Focused subset of `AGENTS.md` — see that file for Copilot/Codex conventions.

---

## Navigation

- **Code map:** [dev-docs/code-map.md](dev-docs/code-map.md) — file index, Mermaid diagrams, role of every source file
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) — layer contracts, data flow, domain breakdown
- **All docs:** [docs/index.md](docs/index.md) — full navigable map
- **Sub-agents:** [.claude/sub-agents/](.claude/sub-agents/) — architecture-analyst, dependency-analyst, test-coverage-analyst, security-scanner, evaluator

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

## Key Principles

1. Parse data shapes at boundaries — never pass raw, unvalidated API responses between layers
2. All Spotify API calls go through `services/spotify.ts` only
3. Export cursors are always persisted before any destructive step
4. Cache keys are namespaced: `<user_id>:<resource_type>:<identifier>`
5. No `console.log` in non-test backend code — use structured logging
6. No bare `except:` in Python — always name the exception type

Full list: [docs/golden-principles.md](docs/golden-principles.md)

---

## Plans & Docs Placement

- New implementation plans → `docs/exec-plans/active/YYYY-MM-DD-topic.md` (checkbox steps, mark complete as you go)
- Completed plans → move to `docs/exec-plans/completed/` and index in its `README.md`
- Design decisions → `docs/design-docs/`
- Third-party API references → `docs/references/`
- Short-lived investigations, audits, working notes → `dev-docs/`
- Before creating a new doc, check `docs/index.md` and run `rg "<topic>" dev-docs docs`

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

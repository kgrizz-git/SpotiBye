# Repository Copilot Instructions

> Quick reference for AI coding agents. Full context is in [AGENTS.md](../AGENTS.md) and [ARCHITECTURE.md](../ARCHITECTURE.md).

---

## Layer Architecture Rules

Violations of these rules are bugs, not style preferences. They are enforced by ESLint and structural tests.

**Backend (TypeScript):**
- `routes/` → `services/` → `types/` — one-way dependency only
- Routes must not import from other routes
- Services must not import from routes or middleware
- All `api.spotify.com` calls go through `services/spotify.ts` only — no direct fetch in routes

**Frontend (Python):**
- `screens/` → `services/` → `auth/` | `caching/` | `config/`
- `ui/` components are leaf nodes — no business logic, no service imports
- `utils/` must not import from any other app layer

---

## Golden Principles

Full list: [docs/golden-principles.md](../docs/golden-principles.md)

1. Parse and validate data shapes at every layer boundary — never pass raw unvalidated responses inward
2. All Spotify API calls go through `services/spotify.ts`
3. Export cursors are always persisted before any destructive step
4. Cache keys are namespaced: `<user_id>:<resource_type>:<identifier>`
5. No `console.log` in non-test backend code — structured logging only
6. No bare `except:` in Python — always name the exception type
7. Prefer shared utilities over duplicated helpers

---

## Documentation Conventions

- Use `docs/exec-plans/active/YYYY-MM-DD-topic.md` for new executable plans.
- Executable plans must use checkbox steps (`- [ ]`), and completed steps must be checked off in the plan as implementation proceeds.
- If a plan is tied to `dev-docs/TO_DO.md`, keep the TODO linked while active and mark it complete when the plan moves to completed.
- Move finished plans to `docs/exec-plans/completed/` and update that directory's README index.
- Use `docs/design-docs/` for durable architecture/design decisions and `docs/references/` for third-party API notes.
- Use `dev-docs/` for temporary audits, analysis notes, and implementation context that may later be consolidated.
- Read `docs/index.md` and `dev-docs/README.md` before adding new docs so existing pages are updated instead of duplicated.
- Do not create new root-level `plans/` files.

---

## PR Conventions

- PRs should change one logical thing. Split changes > ~400 lines.
- Every PR description must state what changed and why.
- Architecture violations caught by linters must be fixed before merging.

---

## Changelog Maintenance Rule

When a change affects user-visible behavior, update CHANGELOG.md in the same pull request.

User-visible changes include:
- New features or removed features
- Bug fixes that alter behavior
- UI and UX changes users can notice
- Build and distribution changes that affect delivered artifacts

Changelog updates should:
- Add concise bullet points under the correct unreleased or release version section
- Use sections such as Added, Changed, Fixed, and Known Issues as appropriate
- Keep entries focused on outcomes and user impact

Changelog updates are not required for internal-only changes, such as:
- Refactors with no user-visible behavior changes
- Test-only changes
- Documentation-only updates that do not change product behavior
- CI/internal tooling changes with no user-facing impact

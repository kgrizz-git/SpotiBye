# Maintenance Log

> Append-only log for internal-only work. User-visible changes go in `CHANGELOG.md`.
> One entry per completed PR or internal housekeeping action. Schema:
>
>     ## YYYY-MM-DD — <short outcome>
>     PR: #NN
>     Scope: <area>
>     <one-line outcome>

---

## 2026-09-19 — Docs harness baseline captured

PR: n/a (bootstrap entry; landed via docs-harness housekeeping branch)
Scope: docs-harness

Captured baseline evidence for docs harness housekeeping: 39 `[x]` done lines in TO_DO.md, 3 duplicate `###` sections in CHANGELOG Unreleased, 9 stale Open rows in tech-debt-tracker.md, 2 unindexed root `dev-docs/*.md` files, and the plan↔TODO↔index cross-reference mismatches. Persisted to `dev-docs/investigations/2026-09-19-docs-harness-baseline.md`.

## 2026-06-19 — Legacy plans migrated to exec-plans/completed/legacy

PR: n/a (predates PR-linking; date from tech-debt Done row)
Scope: docs-organization

Consolidated legacy plan files under `dev-docs/exec-plans/completed/legacy/`; active/completed indexes updated.

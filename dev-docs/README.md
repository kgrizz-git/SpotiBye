# Developer Notes

`dev-docs/` holds working notes for maintainers and coding agents. These files can be more tactical than the durable docs in `docs/`.

Use this directory for:

- audits and codebase maps
- temporary implementation context
- investigation notes
- active backend/frontend analysis notes that are not yet stable design docs

Do not use this directory for:

- executable implementation plans; use `docs/exec-plans/active/`
- completed plans; use `docs/exec-plans/completed/`
- durable architecture decisions; use `docs/design-docs/`
- third-party API references; use `docs/references/`

Before adding a new file here, run:

```bash
rg -n "<topic keyword>" dev-docs docs
```

Update an existing note when it already covers the same topic. If a note becomes durable guidance, move or summarize it under `docs/` and update `docs/index.md`.

**Lifecycle rules:**

- Date-prefix tactical notes: `YYYY-MM-DD-topic.md` (e.g., `2026-06-15-bug-review.md`)
- Investigation notes older than 60 days without updates should be reviewed for archival or deletion
- If a note graduates to durable guidance, move it to `docs/` and update `docs/index.md`
- Plans never go here — use `docs/exec-plans/active/`

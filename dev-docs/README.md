# Developer Documentation Index

`dev-docs/` holds developer, maintainer, and agent-facing documentation. User-facing documentation belongs in [`../docs/`](../docs/).

Use this directory for:

- architecture maps, durable design decisions, and project summaries
- contributor setup, debugging, testing, build, and deployment guides
- implementation plans and completed plan archives
- third-party API and platform references
- investigations, assessments, audits, and tactical working notes
- backlog and technical debt tracking

Do not use this directory for:

- end-user installation, usage, FAQ, or troubleshooting pages; use `docs/`
- release notes; use `CHANGELOG.md`
- security policy; use `SECURITY.md`

Before adding a new file, run:

```bash
rg -n "<topic keyword>" dev-docs docs
```

Update an existing page when it already covers the same topic.

---

## Entry Points

| File | Purpose |
|------|---------|
| [`code-map.md`](code-map.md) | File index, Mermaid diagrams, and role of source files |
| [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | Layer contracts, data flow, domain breakdown, and frontend startup/backend connection flow |
| [`guides/golden-principles.md`](guides/golden-principles.md) | Mechanical engineering rules for this repo |
| [`guides/osv-scanner-findings-playbook.md`](guides/osv-scanner-findings-playbook.md) | Decision tree for resolving OSV-Scanner advisories (bump, override, parent-update, suppress) |
| [`dependency-graph.json`](dependency-graph.json) | Machine-readable import graph for impact analysis |

## Architecture

| Path | Purpose |
|------|---------|
| [`architecture/design-decisions/`](architecture/design-decisions/) | Durable design decisions |
| [`architecture/project-summary-overview.md`](architecture/project-summary-overview.md) | High-level project summary |
| [`architecture/project-summary-cloud-migration.md`](architecture/project-summary-cloud-migration.md) | Cloud migration summary |

## Contributor Guides

| File | Purpose |
|------|---------|
| [`guides/environment-setup.md`](guides/environment-setup.md) | Canonical configuration sources, secret locations, and precedence |
| [`guides/developer-guide-backend.md`](guides/developer-guide-backend.md) | Backend development guide |
| [`guides/authentication-flow.md`](guides/authentication-flow.md) | OAuth PKCE flow walkthrough |
| [`guides/build-and-deploy-guide.md`](guides/build-and-deploy-guide.md) | Build and deployment steps |
| [`guides/cloudflare-deployment.md`](guides/cloudflare-deployment.md) | Cloudflare deployment notes |
| [`guides/frontend-distribution-guide.md`](guides/frontend-distribution-guide.md) | Frontend packaging and distribution |
| [`guides/testing-strategy.md`](guides/testing-strategy.md) | Test approach and guidelines |
| [`guides/debugging.md`](guides/debugging.md) | Debugging tips |
| [`guides/export-formats-implementation.md`](guides/export-formats-implementation.md) | Export format implementation notes |
| [`guides/file-length-policy.md`](guides/file-length-policy.md) | File length limits, refactoring, and exemptions guide |
| [`guides/sonarqube-local.md`](guides/sonarqube-local.md) | Run SonarQube Community locally for static-analysis reports |

## References

| File | Purpose |
|------|---------|
| [`references/spotify-api-reference.md`](references/spotify-api-reference.md) | Spotify API endpoints, limits, and quirks |
| [`references/cloudflare-workers-constraints.md`](references/cloudflare-workers-constraints.md) | Cloudflare Worker platform constraints |
| [`reccobeats-api-contract.md`](reccobeats-api-contract.md) | ReccoBeats live API contract: join keys (`href`), omission semantics, field inventory (agent entry point) |

## Plans

| Path | Purpose |
|------|---------|
| [`exec-plans/active/`](exec-plans/active/) | Active execution plans |
| [`exec-plans/completed/`](exec-plans/completed/) | Completed, superseded, and historical plans |

Plan rules:

- New implementation plans go in `dev-docs/exec-plans/active/YYYY-MM-DD-topic.md`.
- Plans must use checkbox steps (`- [ ]`) and executors must mark steps complete (`- [x]`) as work is completed.
- Completed or superseded plans move to `dev-docs/exec-plans/completed/` and must be indexed in [`exec-plans/completed/README.md`](exec-plans/completed/README.md).

## Investigations and Assessments

| Path | Purpose |
|------|---------|
| [`investigations/`](investigations/) | Short-lived or historical research notes |
| [`assessments/`](assessments/) | Engineering assessments and audits |
| [`refactor-assessments/`](refactor-assessments/) | Refactor-specific assessments |

Current notes:

| File | Purpose |
|------|---------|
| [`2026-06-22-backend-deployment-tracking.md`](2026-06-22-backend-deployment-tracking.md) | Backend deployment tracking notes |
| [`2026-06-26-reccobeats-wiring-assessment.md`](2026-06-26-reccobeats-wiring-assessment.md) | ReccoBeats wiring assessment |
| [`investigations/2026-09-19-docs-harness-baseline.md`](investigations/2026-09-19-docs-harness-baseline.md) | Docs harness baseline: TO_DO done count, CHANGELOG duplicates, tech-debt staleness, unindexed files, plan↔TODO↔index mismatches |
| [`agent-first-retrofit-guide.md`](agent-first-retrofit-guide.md) | Historical agent-first repository retrofit guide |
| [`backend-analysis-routes.md`](backend-analysis-routes.md) | Backend route analysis |
| [`bug-fix-plan-2026-06-15.md`](bug-fix-plan-2026-06-15.md) | Historical bug-fix plan |
| [`bug-review-2026-06-15-112416.md`](bug-review-2026-06-15-112416.md) | Bug review notes |
| [`bug-review-2026-06-21-183947.md`](bug-review-2026-06-21-183947.md) | Bug review notes |
| [`playlist-analysis-popup.md`](playlist-analysis-popup.md) | Playlist analysis popup notes |
| [`spotify-api-enrichment.md`](spotify-api-enrichment.md) | Spotify API enrichment notes |
| [`assessments/harness-engineering-assessment.md`](assessments/harness-engineering-assessment.md) | Harness engineering assessment |
| [`investigations/apple-music-api-analysis.md`](investigations/apple-music-api-analysis.md) | Apple Music API feasibility analysis |
| [`investigations/excel-import-feasibility-analysis.md`](investigations/excel-import-feasibility-analysis.md) | Excel import feasibility analysis |
| [`investigations/february-2026-spotify-migration-findings.md`](investigations/february-2026-spotify-migration-findings.md) | Spotify API migration findings |
| [`refactor-assessments/main_screen-refactor-assessment-2026-06-15.md`](refactor-assessments/main_screen-refactor-assessment-2026-06-15.md) | Main screen refactor assessment |

Date-prefix new tactical notes as `YYYY-MM-DD-topic.md`. Investigation notes older than 60 days without updates should be reviewed for archival, deletion, or promotion into durable guidance.

## Backlog and Archives

| Path | Purpose |
|------|---------|
| [`backlog/TO_DO.md`](backlog/TO_DO.md) | Developer backlog |
| [`backlog/tech-debt-tracker.md`](backlog/tech-debt-tracker.md) | Structured technical debt log |
| [`backlog/maintenance-log.md`](backlog/maintenance-log.md) | Internal-only housekeeping log (not for user-visible changes) |
| [`archive/old-docs-backup/`](archive/old-docs-backup/) | Historical docs kept for reference only |

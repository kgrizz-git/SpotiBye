# Docs Index

> Complete navigable map of all documentation in this repository. Agents: start here to find the right doc before writing new ones.

---

## Architecture & Entry Points

| File | Purpose | Status |
|------|---------|--------|
| [`/AGENTS.md`](../AGENTS.md) | Agent entry point — repo map and quick reference | Current |
| [`/ARCHITECTURE.md`](../ARCHITECTURE.md) | Layer contracts, data flows, domain breakdown | Current |
| [`/QUALITY_SCORE.md`](../QUALITY_SCORE.md) | Per-domain quality grades and known gaps | Current |
| [`/CHANGELOG.md`](../CHANGELOG.md) | User-visible changes by release | Current |
| [`/SECURITY.md`](../SECURITY.md) | Security policy | Current |

---

## Design Docs

Decisions made once that govern how things are built.

| File | Decision | Status |
|------|---------|--------|
| [`design-docs/cloudflare-worker-choice.md`](design-docs/cloudflare-worker-choice.md) | Why Cloudflare Workers + Hono was chosen | Current |
| [`design-docs/resumable-export-cursors.md`](design-docs/resumable-export-cursors.md) | Cursor-based resumable export design | Current |

---

## References

Third-party API summaries and platform constraints for agent consumption.

| File | Content |
|------|---------|
| [`references/spotify-api-reference.md`](references/spotify-api-reference.md) | Endpoints used, rate limits, known quirks |
| [`references/cloudflare-workers-constraints.md`](references/cloudflare-workers-constraints.md) | CPU limits, KV limits, Worker constraints |

---

## How-To Guides

| File | Content | Status |
|------|---------|--------|
| [`authentication-flow.md`](authentication-flow.md) | Full OAuth PKCE flow walkthrough | Current |
| [`environment-setup.md`](environment-setup.md) | Dev environment setup instructions | Current |
| [`build-and-deploy-guide.md`](build-and-deploy-guide.md) | Build and deployment steps | Current |
| [`cloudflare-deployment.md`](cloudflare-deployment.md) | Cloudflare-specific deployment notes | Current |
| [`developer-guide-backend.md`](developer-guide-backend.md) | Backend developer guide | Current |
| [`configuration-options.md`](configuration-options.md) | All configuration options | Current |
| [`debugging.md`](debugging.md) | Debugging tips | Current |
| [`testing-strategy.md`](testing-strategy.md) | Test approach and guidelines | Current |
| [`frontend-distribution-guide.md`](frontend-distribution-guide.md) | How to package and distribute the frontend | Current |
| [`installation-instructions.md`](installation-instructions.md) | End-user installation guide | Current |

---

## Troubleshooting

| File | Content |
|------|---------|
| [`troubleshooting-network.md`](troubleshooting-network.md) | Network connectivity issues |
| [`faq-connectivity.md`](faq-connectivity.md) | Connectivity FAQ |

---

## Analysis & Research

| File | Content | Status |
|------|---------|--------|
| [`february-2026-spotify-migration-findings.md`](february-2026-spotify-migration-findings.md) | Spotify API migration findings, Feb 2026 | Current |
| [`apple-music-api-analysis.md`](apple-music-api-analysis.md) | Apple Music API feasibility analysis | Reference |
| [`excel-import-feasibility-analysis.md`](excel-import-feasibility-analysis.md) | Excel import feasibility | Reference |
| [`export-formats-implementation.md`](export-formats-implementation.md) | Export format implementation notes | Current |
| [`api_key_security.md`](api_key_security.md) | API key security analysis | Current |

---

## Project Summaries

| File | Content |
|------|---------|
| [`project-summary-overview.md`](project-summary-overview.md) | High-level project overview |
| [`project-summary-cloud-migration.md`](project-summary-cloud-migration.md) | Cloud migration summary |
| [`user-guide-cloud-backend.md`](user-guide-cloud-backend.md) | User guide for cloud backend |

---

## Plans & Execution

| Path | Content |
|------|---------|
| [`exec-plans/active/`](exec-plans/active/) | Currently active execution plans |
| [`exec-plans/completed/`](exec-plans/completed/) | Completed execution plans |
| [`plans/`](plans/) | Legacy plan files (pre-exec-plans structure) |

---

## Principles & Debt

| File | Content |
|------|---------|
| [`golden-principles.md`](golden-principles.md) | Opinionated, mechanical coding rules |
| [`tech-debt-tracker.md`](tech-debt-tracker.md) | Structured technical debt log |

# Active Execution Plans

> Plans currently in progress. Move a plan to `../completed/` when it is fully executed and all references are updated.

| Plan | Description | Started |
|------|-------------|---------|
| [2026-07-05-backend-url-defaulting-fix.md](./2026-07-05-backend-url-defaulting-fix.md) | Fix `BACKEND_PRESETS` aliasing between "Localhost" and "Cloudflare Dev" (non-functional preset button, lost preset choice on relaunch) | 2026-07-05 |
| [2026-07-06-spotify-token-expiration-handling.md](./2026-07-06-spotify-token-expiration-handling.md) | Handle `invalid_grant` from Spotify token refresh, discard invalid tokens, return auth-required response, redirect to login | 2026-07-06 |
| [2026-07-11-backend-playlist-analysis-progress-bar.md](./2026-07-11-backend-playlist-analysis-progress-bar.md) | In-app progress bar for playlist analysis (ReccoBeats enrichment), granularity fix + UI wiring | 2026-07-11 |
| [2026-07-12-per-track-reccobeats-cache-and-enrichment-refresh.md](./2026-07-12-per-track-reccobeats-cache-and-enrichment-refresh.md) | Global per-track ReccoBeats KV cache, auto miss-fetch on open, refresh buttons, export enrichment; hotfix track for incomplete-analysis UX | 2026-07-12 |
| [2026-07-22-reduce-github-actions-billable-minutes.md](./2026-07-22-reduce-github-actions-billable-minutes.md) | Reduce GitHub Actions billable minutes (Security Scan parallelism, dead Dependabot dirs, duplicate backend PR tests). 3 phases; combined ~190–240 min/mo (Phase 1 ~13–21, Phase 2 ~6–10, Phase 3 ~168–210) | 2026-07-22 |

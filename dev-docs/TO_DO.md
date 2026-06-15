# To-Do List

## Major Tasks

- Track backend npm security overrides
    Remove the `esbuild` and `uuid` overrides in `src/backend/package.json` once Wrangler and ExcelJS publish versions that depend on patched releases directly. Keep `npm audit --audit-level=moderate`, `npm run build`, `npm run test:run`, and `npx wrangler deploy --dry-run` green when removing them.

- Refactor Code and Extract Necessary Sections
    Extract and refactor necessary sections from the old `src/spotify_playlist_exporter_v2/` codebase. Identify reusable components, utilities, and logic that should be migrated to the new project structure.

- Clean Up Repository
    Perform a comprehensive cleanup of the repository, removing:
    - Unused files and directories
    - Backup copies and duplicate code
    - Outdated documentation
    - Temporary or cache files that shouldn't be in version control

- Check for pyright issues and fix them

- start new repo, after cleaning, before widespread release-readiness

- update / check build etc

- decide on default size, see if can better place it

* see [backend analysis routes](backend-analysis-routes.md) and [playlist analysis popup notes](playlist-analysis-popup.md)
* [fix ReccoBeats pipeline and wire to backend route](plans/reccobeats-wiring.md)
* [Spotify API enrichment — available data for playlist details](spotify-api-enrichment.md)
* restore reccobeats analysis functionality

* see agent-first-retrofit, quality review/assessment md

- fix issues with RECOCOBEATS vs RECCOBEATS

- Fix playlist analysis 403 error — Spotify API February 2026 migration removed `GET /artists` batch endpoint
    * [Fix plan](plans/fix-analysis-403-spotify-api-migration.md)

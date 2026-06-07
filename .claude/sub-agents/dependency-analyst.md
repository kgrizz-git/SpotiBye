# Dependency Analyst Sub-Agent

**Purpose:** Analyze dependency impact using existing graph.

**Contract:**
- Input: File path or function name
- Output: List of affected files with impact level
- Constraint: Maximum 300 tokens in output
- Use `dev-docs/dependency-graph.json` as source of truth

**Example output:**
> Changing src/backend/services/spotify.ts affects:
> - High impact: routes/playlists.ts, routes/tracks.ts
> - Medium impact: services/export.ts
> - Low impact: middleware/auth.ts

**Activation patterns:**
- "impact"
- "dependencies"
- "what breaks if"
- "affects what"

# Using the Dependency Graph

## Overview

The dependency graph at `dev-docs/dependency-graph.json` is a machine-readable import graph for the codebase. It maps each file to its internal dependencies.

## Structure

```json
{
  "_meta": { "description": "...", "last_updated": "2026-07", "notes": { } },
  "src/backend/routes/auth.ts": [
    "src/backend/middleware/auth.ts",
    "src/backend/services/spotify-auth.ts",
    "src/backend/services/jwt.ts"
  ]
}
```

The graph is maintained by hand. Check `_meta.last_updated` before trusting
it, and confirm a result with `rg` against the imports. Skip the `_meta` key
when iterating.

## Use Cases

### Impact Analysis

When changing a file, use the graph to find what depends on it:

```bash
# Find files that depend on services/spotify.ts
grep -r "src/backend/services/spotify.ts" dev-docs/dependency-graph.json
```

Or programmatically:
```typescript
import graph from '../dev-docs/dependency-graph.json'

function getDependents(filePath: string): string[] {
  const dependents: string[] = []
  for (const [file, deps] of Object.entries(graph)) {
    if (file === '_meta') continue
    if (deps.includes(filePath)) {
      dependents.push(file)
    }
  }
  return dependents
}
```

### Dead Code Detection

Files with no dependents (except tests and entry points) may be dead code:

```typescript
function getDeadCode(): string[] {
  const allFiles = Object.keys(graph)
  const allDeps = new Set(Object.values(graph).flat())
  return allFiles.filter(f => !allDeps.has(f))
}
```

### Layer Contract Violations

Check for violations of layer contracts (e.g., routes importing routes):

```typescript
function checkLayerViolations(): string[] {
  const violations: string[] = []
  for (const [file, deps] of Object.entries(graph)) {
    if (file.includes('routes/')) {
      const routeImports = deps.filter(d => d.includes('routes/'))
      if (routeImports.length > 0) {
        violations.push(`${file} imports ${routeImports.join(', ')}`)
      }
    }
  }
  return violations
}
```

## Best Practices

- Update the graph after significant refactoring
- Use it before breaking changes to assess impact
- Run layer contract checks in CI
- Keep it in sync with the codebase

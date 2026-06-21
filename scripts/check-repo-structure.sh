#!/usr/bin/env bash
# Structural guardrail: enforces repo organization conventions.
# Run by pre-commit. Exit non-zero to block the commit.

set -euo pipefail

ERRORS=()
WARNINGS=()

# 1. No .md files in dev-docs/plans/ (plans belong in docs/exec-plans/active/)
if find dev-docs/plans -name "*.md" 2>/dev/null | grep -q .; then
  ERRORS+=("Found .md files in dev-docs/plans/ — move plans to docs/exec-plans/active/YYYY-MM-DD-topic.md")
fi

# 2. No .windsurf/rules/ resurrection (.cursor/rules/ is canonical for IDE security rules)
if [ -d ".windsurf/rules" ] && find .windsurf/rules -name "*.md" -o -name "*.mdc" 2>/dev/null | grep -q .; then
  ERRORS+=(".windsurf/rules/ exists with content — .cursor/rules/ is the canonical location; delete .windsurf/rules/")
fi

# 3. No .DS_Store staged
if git diff --cached --name-only | grep -q '\.DS_Store'; then
  ERRORS+=("Staged .DS_Store file — unstage it (git restore --staged '**/.DS_Store')")
fi

# 4. Warn (don't fail) if a plan in active/ looks fully completed
# Heuristic: file has >3 checkboxes and zero unchecked ones
for plan in docs/exec-plans/active/*.md; do
  [ -f "$plan" ] || continue
  total=$(grep -c '\- \[' "$plan" 2>/dev/null || true)
  unchecked=$(grep -c '\- \[ \]' "$plan" 2>/dev/null || true)
  if [ "$total" -gt 3 ] && [ "$unchecked" -eq 0 ]; then
    WARNINGS+=("$plan appears fully completed — consider moving it to docs/exec-plans/completed/")
  fi
done

# Report warnings
for w in "${WARNINGS[@]}"; do
  echo "WARNING: $w" >&2
done

# Report errors and exit 1 if any
if [ ${#ERRORS[@]} -gt 0 ]; then
  for e in "${ERRORS[@]}"; do
    echo "ERROR: $e" >&2
  done
  exit 1
fi

exit 0

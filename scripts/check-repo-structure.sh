#!/usr/bin/env bash
# Structural guardrail: enforces repo organization conventions.
# Run by pre-commit. Exit non-zero to block the commit.

set -euo pipefail

ERRORS=()
WARNINGS=()

error() {
  ERRORS+=("$1")
}

warn() {
  WARNINGS+=("$1")
}

check_absent_dir() {
  local path="$1"
  local reason="$2"

  if [ -d "$path" ] && find "$path" -mindepth 1 2>/dev/null | grep -q .; then
    error "$path exists with content — $reason"
  fi
}

# docs/ is end-user documentation only. Developer-only categories belong under dev-docs/.
check_absent_dir "docs/exec-plans" "move implementation plans to dev-docs/exec-plans/"
check_absent_dir "docs/design-docs" "move design decisions to dev-docs/architecture/design-decisions/"
check_absent_dir "docs/references" "move third-party references to dev-docs/references/"
check_absent_dir "docs/old-docs-backup" "move historical archives to dev-docs/archive/"

# Legacy plan location should not come back.
check_absent_dir "dev-docs/plans" "move plans to dev-docs/exec-plans/active/YYYY-MM-DD-topic.md"

# Heuristic for likely developer-only files accidentally added directly under docs/.
if [ -d "docs" ]; then
  while IFS= read -r file; do
    base=$(basename "$file")
    case "$base" in
      *analysis*.md|*assessment*.md|*developer*.md|*testing*.md|*deployment*.md|*debugging*.md|*migration*.md|*tech-debt*.md|*implementation*.md|*plan*.md)
        error "$file looks developer-facing — move it under dev-docs/ or rename it if it is truly user-facing"
        ;;
    esac
  done < <(find docs -maxdepth 1 -type f -name "*.md" | sort)
fi

# IDE security rules live in .cursor/rules/ only.
if [ -d ".windsurf/rules" ] && find .windsurf/rules \( -name "*.md" -o -name "*.mdc" \) 2>/dev/null | grep -q .; then
  error ".windsurf/rules/ exists with content — .cursor/rules/ is the canonical location; delete .windsurf/rules/"
fi

# No .DS_Store staged.
if git diff --cached --name-only | grep -q '\.DS_Store'; then
  error "Staged .DS_Store file — unstage it (git restore --staged '**/.DS_Store')"
fi

# Active plans must be checkbox-trackable.
for plan in dev-docs/exec-plans/active/*.md; do
  [ -f "$plan" ] || continue
  [ "$(basename "$plan")" != "README.md" ] || continue

  total=$(grep -c '\- \[' "$plan" 2>/dev/null || true)
  unchecked=$(grep -c '\- \[ \]' "$plan" 2>/dev/null || true)

  if [ "$total" -eq 0 ]; then
    error "$plan has no checkbox steps — active plans must use '- [ ]' tracking"
  elif [ "$total" -gt 3 ] && [ "$unchecked" -eq 0 ]; then
    warn "$plan appears fully completed — move it to dev-docs/exec-plans/completed/ and update the index"
  fi
done

# Warn when current user docs are not discoverable from the user index.
if [ -f "docs/index.md" ]; then
  while IFS= read -r file; do
    rel=${file#docs/}
    [ "$rel" = "index.md" ] && continue
    if ! grep -Fq "$rel" docs/index.md; then
      warn "$file is not linked from docs/index.md"
    fi
  done < <(find docs -type f -name "*.md" | sort)
fi

# Warn when current top-level developer docs are not discoverable from the developer index.
if [ -f "dev-docs/README.md" ]; then
  while IFS= read -r file; do
    rel=${file#dev-docs/}
    case "$rel" in
      README.md|exec-plans/completed/*|archive/*)
        continue
        ;;
    esac
    if ! grep -Fq "$rel" dev-docs/README.md; then
      warn "$file is not linked from dev-docs/README.md"
    fi
  done < <(find dev-docs -maxdepth 2 -type f -name "*.md" | sort)
fi

for w in "${WARNINGS[@]}"; do
  echo "WARNING: $w" >&2
done

if [ ${#ERRORS[@]} -gt 0 ]; then
  for e in "${ERRORS[@]}"; do
    echo "ERROR: $e" >&2
  done
  exit 1
fi

exit 0

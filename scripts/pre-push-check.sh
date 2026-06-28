#!/usr/bin/env bash
# SpotiBye pre-push hook — runs pre-commit pre-push checks and prints a clear
# failure summary when git push is blocked.
#
# Installed by scripts/setup-hooks.sh (replaces the default pre-commit pre-push
# hook). Re-run setup-hooks.sh after `pre-commit install` if the summary wrapper
# is overwritten.

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

HOOK_DIR="$REPO_ROOT/.git/hooks"
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT

INSTALL_PYTHON="$REPO_ROOT/.venv/bin/python3"
ARGS=(hook-impl --config=.pre-commit-config.yaml --hook-type=pre-push --hook-dir "$HOOK_DIR")

run_pre_commit() {
  if [ -x "$INSTALL_PYTHON" ]; then
    "$INSTALL_PYTHON" -mpre_commit "${ARGS[@]}" -- "$@"
  elif command -v pre-commit >/dev/null 2>&1; then
    pre-commit "${ARGS[@]}" -- "$@"
  else
    echo 'pre-commit not found. Activate .venv or run: pip install pre-commit' >&2
    return 127
  fi
}

set +e
run_pre_commit "$@" 2>&1 | tee "$LOG"
STATUS=${PIPESTATUS[0]}
set -e

if [ "$STATUS" -eq 0 ]; then
  exit 0
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo " PUSH BLOCKED — one or more pre-push checks failed"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Failed hooks:"
grep -E '\.\.\.(Failed|failed)' "$LOG" | sed 's/^/  /' || true
echo ""
echo "Likely errors (trimmed; warnings omitted):"
grep -Ei '(^FAILED |^=+ .*failed|AssertionError|AttributeError|Error:|E[0-9]+ |F[0-9]+ |error  )' "$LOG" \
  | grep -viE 'warning|no-explicit-any' \
  | head -80 || true
echo ""
echo "Re-run all pre-push checks:"
echo "  pre-commit run --hook-stage pre-push --all-files"
echo ""
echo "Re-run one hook, e.g.:"
echo "  pre-commit run python-tests --hook-stage pre-push --all-files"
echo ""
echo "Emergency bypass (not recommended):"
echo "  git push --no-verify"
echo "════════════════════════════════════════════════════════════════"
exit "$STATUS"

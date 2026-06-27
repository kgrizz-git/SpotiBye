#!/usr/bin/env bash
#
# prune-backups.sh
# -----------------------------------------------------------------------------
# Purpose:
#   Keep the `backups/` directory from accumulating stale code backups. Code
#   backups are created (per project convention) before refactors/modifications.
#   This script removes any *committed* file under `backups/` whose most recent
#   commit is more than KEEP_COMMITS commits behind HEAD, so backups that have
#   outlived their usefulness do not linger in the repository.
#
# Behavior:
#   - Operates only on tracked files in `backups/`. Untracked backups are
#     treated as brand-new (age 0) and are always kept.
#   - "Age" of a backup = number of commits between the commit that last touched
#     the file and HEAD. A backup is pruned when that age is GREATER THAN
#     KEEP_COMMITS (default 5), i.e. it is older than the last KEEP_COMMITS
#     commits.
#   - Pruned files are removed with `git rm` so the deletion is staged. When run
#     as a pre-commit hook and a prune occurs, pre-commit reports that files were
#     modified and aborts the commit; simply re-run the commit (the backups are
#     already staged for deletion) to proceed.
#
# Inputs (environment variables, all optional):
#   KEEP_COMMITS  Number of most-recent commits to keep backups for (default 5).
#   BACKUP_DIR    Directory to prune (default "backups").
#   DRY_RUN       If set to "1", report what would be pruned without deleting.
#
# Outputs:
#   - Deletes (and stages) stale backup files.
#   - Prints a human-readable summary to stdout.
#   - Always exits 0 on success (including when nothing is pruned), so it is a
#     no-op on the common case where there are no stale backups.
#
# Requirements:
#   bash, git. Safe to run repeatedly (idempotent).
# -----------------------------------------------------------------------------

set -euo pipefail

KEEP_COMMITS="${KEEP_COMMITS:-5}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
DRY_RUN="${DRY_RUN:-0}"

# Resolve the repository root; exit quietly if we are not inside a git repo.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$REPO_ROOT"

# Nothing to measure age against if there are no commits yet.
git rev-parse HEAD >/dev/null 2>&1 || exit 0

# Nothing to do if the backups directory does not exist.
[ -d "$BACKUP_DIR" ] || exit 0

pruned=0

# Iterate over tracked files only; untracked backups are newly created (age 0).
while IFS= read -r f; do
    [ -n "$f" ] || continue

    last_commit="$(git log -1 --format=%H -- "$f" 2>/dev/null || true)"
    # No commit history => the path is untracked/new; keep it.
    [ -n "$last_commit" ] || continue

    age="$(git rev-list --count "${last_commit}..HEAD" 2>/dev/null || echo 0)"

    if [ "$age" -gt "$KEEP_COMMITS" ]; then
        if [ "$DRY_RUN" = "1" ]; then
            echo "[dry-run] would prune stale backup ($age commits old): $f"
        else
            git rm -q -- "$f"
            echo "pruned stale backup ($age commits old): $f"
        fi
        pruned=$((pruned + 1))
    fi
done < <(git ls-files "$BACKUP_DIR")

if [ "$pruned" -gt 0 ]; then
    if [ "$DRY_RUN" = "1" ]; then
        echo "prune-backups: $pruned stale backup file(s) would be removed (older than $KEEP_COMMITS commits)."
    else
        echo "prune-backups: removed $pruned stale backup file(s) (older than $KEEP_COMMITS commits)."
    fi
fi

exit 0

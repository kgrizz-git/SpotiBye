#!/bin/bash
# Setup script for pre-commit and pre-push hooks
# Run this after cloning the repository

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "🔧 Setting up Git hooks for SpotiBye..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "❌ pre-commit is not installed"
    echo ""
    echo "Installing pre-commit..."
    pip install pre-commit  # NOSONAR(S8541): local dev tool install; --only-binary would break Kivy source builds
fi

# Install development extras so hook dependencies like pathspec are present
echo ""
echo "📦 Installing Python development dependencies..."
if [ -f "$REPO_ROOT/.venv/bin/pip" ]; then
    "$REPO_ROOT/.venv/bin/pip" install -e ".[development]"  # NOSONAR(S8541): Kivy/KivyMD need source builds on Linux
else
    pip install -e ".[development]"  # NOSONAR(S8541): Kivy/KivyMD need source builds on Linux
fi

# Install the hooks
echo ""
echo "📦 Installing pre-commit hooks..."
pre-commit install --hook-type pre-commit --hook-type pre-push

# Replace the generated pre-push hook with our summary wrapper so failed pushes
# print which hooks failed and how to re-run them.
echo ""
echo "📦 Installing pre-push summary wrapper..."
chmod +x scripts/pre-push-check.sh
cp scripts/pre-push-check.sh .git/hooks/pre-push

echo ""
echo "✅ Hooks installed successfully!"
echo ""
echo "Hook stages:"
echo "  - pre-commit: Fast checks on every commit (secrets, lint/format on staged files)"
echo "  - pre-push:   Full checks before push (tests, Bandit, SAST, typecheck)"
echo ""
echo "To run manually:"
echo "  pre-commit run --all-files"
echo "  pre-commit run --hook-stage pre-push --all-files"
echo "  .git/hooks/pre-push   # same as push, with failure summary"
echo ""
echo "To skip in emergencies:"
echo "  git commit --no-verify"
echo "  git push --no-verify"

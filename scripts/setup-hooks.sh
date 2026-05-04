#!/bin/bash
# Setup script for pre-commit and pre-push hooks
# Run this after cloning the repository

set -e

echo "🔧 Setting up Git hooks for SpotiBye..."

# Check if pre-commit is installed
if ! command -v pre-commit &> /dev/null; then
    echo "❌ pre-commit is not installed"
    echo ""
    echo "Installing pre-commit..."
    pip install pre-commit
fi

# Install the hooks
echo ""
echo "📦 Installing pre-commit hooks..."
pre-commit install --hook-type pre-commit --hook-type pre-push

echo ""
echo "✅ Hooks installed successfully!"
echo ""
echo "Hook stages:"
echo "  - pre-commit: Fast checks on every commit (secrets, linting, SAST)"
echo "  - pre-push:  Full checks before push (tests, security scans)"
echo ""
echo "To run manually:"
echo "  pre-commit run --all-files"
echo ""
echo "To skip in emergencies:"
echo "  git commit --no-verify"
echo "  git push --no-verify"

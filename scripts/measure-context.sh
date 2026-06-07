#!/bin/bash
# Baseline context measurement script
# This script helps measure context window usage before and after harness engineering improvements

echo "=== Context Window Baseline Measurement ==="
echo "Date: $(date)"
echo ""

# Measure AGENTS.md size
echo "AGENTS.md size:"
wc -l AGENTS.md
echo ""

# Count total codeguard rules
echo "Codeguard rules count:"
echo ".cursor/rules/: $(ls -1 .cursor/rules/*.mdc 2>/dev/null | wc -l)"
echo ".github/instructions/: $(ls -1 .github/instructions/*.md 2>/dev/null | wc -l)"
echo ""

# Count skills
echo "Skills count:"
if [ -d ".skills" ]; then
  echo "Total skills: $(find .skills -name "SKILL.md" | wc -l)"
  echo "Skills:"
  find .skills -name "SKILL.md" -exec dirname {} \; | sed 's|.skills/||' | sed 's|/$||'
else
  echo "No .skills directory found"
fi
echo ""

# Count sub-agents
echo "Sub-agents count:"
if [ -d ".claude/sub-agents" ]; then
  echo "Total sub-agents: $(ls -1 .claude/sub-agents/*.md 2>/dev/null | wc -l)"
  echo "Sub-agents:"
  ls -1 .claude/sub-agents/*.md 2>/dev/null | xargs -I {} basename {} .md
else
  echo "No .claude/sub-agents directory found"
fi
echo ""

# Count verification scripts
echo "Verification scripts:"
ls -1 scripts/verify-*.sh 2>/dev/null | wc -l
echo ""

echo "=== End of Measurement ==="
echo ""
echo "To track agent performance metrics, manually record:"
echo "- Average context size per conversation (tokens)"
echo "- Agent task success rate (percentage)"
echo "- Time to first correct solution (seconds)"

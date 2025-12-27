#!/bin/bash
# Claude Code PreCompact hook for roots context preservation
#
# Runs before context compaction to ensure knowledge persists.
# Install: Copy to .claude/hooks/pre-compact.sh in your project
# Config: Add to .claude/settings.json:
#   { "hooks": { "pre-compact": ".claude/hooks/pre-compact.sh" } }

if [ -d ".roots" ]; then
    echo "## Roots Knowledge Summary"
    echo ""
    roots stats
    echo ""
    echo "Run 'roots prime' after compaction to restore full context."
fi

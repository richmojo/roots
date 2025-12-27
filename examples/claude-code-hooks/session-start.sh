#!/bin/bash
# Claude Code SessionStart hook for roots context injection
#
# Install: Copy to .claude/hooks/session-start.sh in your project
# Config: Add to .claude/settings.json:
#   { "hooks": { "session-start": ".claude/hooks/session-start.sh" } }

# Only run if .roots exists
if [ -d ".roots" ]; then
    roots prime
fi

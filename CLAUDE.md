# Roots - Claude Code Instructions

## What is Roots?

Roots is a persistent knowledge base for AI agents. Use it to accumulate domain knowledge that persists across sessions.

## When to Use Roots

**Add knowledge when you discover:**
- Patterns that work (or don't)
- Gotchas and edge cases
- Validated techniques
- Debugging insights
- Domain-specific rules

**Search before reinventing:**
- Before implementing something, search roots for existing knowledge
- Check if past sessions already solved similar problems

## CLI Commands

```bash
# Search for relevant knowledge
roots search "your query"

# Add new knowledge
roots add <branch> "knowledge content" --tier <tier> --tags "tag1,tag2"

# View structure
roots show

# Get specific leaf
roots get <path>
```

## Tiers

| Tier | When to Use |
|------|-------------|
| `leaves` | Raw observations, untested ideas |
| `branches` | Tested once, promising |
| `trunk` | Validated multiple times |
| `roots` | Foundational, high confidence |

## Workflow

1. **Starting a session**: Run `roots prime` to see available knowledge
2. **During work**: Search before building; add discoveries as you go
3. **Ending session**: Consider what's worth preserving for future agents

## Example

```bash
# Found something useful during work
roots add patterns "Funding rate > 0.1% correlates with local tops" \
    --tree trading --tier leaves --confidence 0.6 --tags "funding,reversals"

# Later, after validation
roots update trading/patterns/funding_rate.md --tier trunk --confidence 0.8
```

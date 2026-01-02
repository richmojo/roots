# Roots - Claude Code Instructions

## What is Roots?

Roots is persistent memory for AI agents. Use it to remember things across sessions.

## When to Use Roots

**Remember when you discover:**
- Patterns that work (or don't)
- User preferences and conventions
- Gotchas and edge cases
- Debugging insights
- Domain-specific rules

**Recall before reinventing:**
- Before implementing something, search for existing knowledge
- Check if past sessions already solved similar problems

## CLI Commands

```bash
# Remember something
roots remember "insight or knowledge" --tags tag1,tag2 --confidence 0.8

# Recall by search
roots recall "your query"

# Recall by tag
roots recall --tag trading

# List recent memories
roots list

# Update confidence after validation
roots update <id> --confidence 0.9

# View all tags
roots tags
```

## Workflow

1. **Starting a session**: Run `roots prime` to see available knowledge
2. **During work**: Search before building; add discoveries as you go
3. **Ending session**: Consider what's worth preserving for future agents

## Example

```bash
# Found something useful during work
roots remember "Funding rate > 0.1% often signals local tops" --tags trading,funding --confidence 0.6

# Later, after validation
roots update 1 --confidence 0.9
```

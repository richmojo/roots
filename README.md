# Roots

Persistent memory for AI agents. Remember things across sessions.

## Why Roots?

AI agents forget everything between sessions. Roots gives them persistent memory:

- **Simple** - Just `remember` and `recall`
- **Semantic search** - Find by meaning, not keywords
- **Tags** - Organize without complex hierarchies
- **Fast** - Rust CLI, ~1ms startup
- **Claude Code integration** - Auto-inject context on session start

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/richmojo/roots/main/scripts/install.sh | bash
```

Or manually:

```bash
git clone https://github.com/richmojo/roots.git
cd roots/rust && cargo install --path .
```

### Embedding Server (Optional)

For better search quality than the default lite mode:

```bash
uv tool install "git+https://github.com/richmojo/roots.git[embeddings]"
roots server start
```

## Quick Start

```bash
# Initialize
roots init

# Remember things
roots remember "OI divergence often precedes reversals" --tags trading,thesis --confidence 0.8
roots remember "Always use uv instead of pip" --tags python,tools

# Recall by search
roots recall "market indicators"

# Recall by tag
roots recall --tag trading

# List recent
roots list

# Sync to markdown for browsing
roots sync
```

## Commands

```bash
roots remember <content>     # Add a memory
  --tags <a,b,c>             # Comma-separated tags
  --confidence <0-1>         # How validated (default: 0.5)

roots recall [query]         # Search memories
  --tag <tag>                # Filter by tag
  -n, --limit <N>            # Max results (default: 5)

roots forget <id>            # Delete a memory
roots update <id>            # Modify confidence/tags
roots list                   # Show recent memories
roots tags                   # List all tags
roots stats                  # Show statistics
roots sync                   # Export to markdown for browsing
roots export                 # Dump as JSON or markdown

roots prime                  # Output context (for hooks)
roots context <prompt>       # Find relevant memories for prompt
roots hooks                       # Install Claude Code hooks
roots hooks --context-mode semantic  # With per-message context matching
roots hooks --remove              # Remove hooks

roots config                 # View/set configuration
roots server start|stop|status|model  # Embedding server
```

## Storage

Everything lives in `.roots/memory.db` - a single SQLite file.

```
.roots/
├── memory.db      # All memories (source of truth)
├── config.yaml    # Settings
└── memories/      # Markdown export (from `roots sync`)
    ├── 001_oi_divergence.md
    └── 002_always_use_uv.md
```

## Embedding Models

By default, uses `lite` mode (n-gram hashing) - fast, no dependencies.

For better search quality, run the embedding server:

```bash
# Set model
roots server model bge-base   # Or: bge-small, qwen-0.6b, bge-large

# Start server
roots server start

# Or install as systemd service
roots server install
```

| Alias | Size | Description |
|-------|------|-------------|
| `lite` | 0MB | N-gram hashing, instant |
| `bge-small` | ~130MB | Small, fast |
| `bge-base` | ~400MB | Good balance |
| `qwen-0.6b` | ~1.2GB | High quality |
| `bge-large` | ~1.2GB | Large model |

## Claude Code Integration

```bash
# Install hooks (SessionStart + PreCompact)
roots hooks

# With context matching on each message
roots hooks --context-mode semantic   # Best quality, needs embedding server
roots hooks --context-mode lite       # Fast, uses n-gram hashing
roots hooks --context-mode tags       # Fastest, matches prompt words to tags

# Remove hooks
roots hooks --remove
```

This installs:
- **SessionStart**: Runs `roots prime` to show available memories
- **PreCompact**: Re-injects context before summarization
- **UserPromptSubmit** (with `--context-mode`): Finds relevant memories for each prompt

## Example Workflow

```bash
# During work - capture insights
roots remember "Funding rate > 0.1% often signals local tops" --tags trading

# Later - validate and update confidence
roots update 1 --confidence 0.8

# Before starting - search for relevant context
roots recall "funding rate signals"

# Periodically - sync for human browsing
roots sync
```

## License

MIT

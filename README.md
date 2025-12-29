# Roots

A semantic knowledge base for AI agents. Accumulate and search domain knowledge across sessions.

## Why Roots?

AI agents forget everything between sessions. Roots gives them persistent memory:

- **Semantic search** - Find relevant knowledge by meaning, not just keywords
- **Hierarchical organization** - Trees, branches, and leaves structure your knowledge
- **Confidence tiers** - Track how validated each piece of knowledge is
- **Cross-references** - Link related or contradicting knowledge
- **Claude Code integration** - Hooks to inject context on session start
- **Embedding server** - Fast inference with model loaded once in memory

## Installation

Requires [uv](https://docs.astral.sh/uv/).

```bash
# Lite install (n-gram hashing, no ML model)
uv tool install git+https://github.com/richmojo/roots.git

# Full install with ML embeddings (recommended)
uv tool install "git+https://github.com/richmojo/roots.git[embeddings]"
```

## Quick Start

```bash
# Initialize in your project
roots init

# Create structure
roots tree trading
roots branch trading patterns

# Add knowledge
roots add patterns "MACD crossovers work best in trending markets, not ranging" \
    --tier trunk --confidence 0.8 --tags "indicators,momentum"

# Search
roots search "momentum indicators"

# View structure
roots show
```

## Embedding Server (Recommended)

For fast search (~0.2s instead of ~6s), run the embedding server:

```bash
# Set your preferred model
roots server model qwen-0.6b    # Or: bge-base, bge-large, etc.

# Install as systemd service (auto-starts on login)
roots server install
systemctl --user start roots-embedder

# Check status
roots server status
```

Available models (ordered by size):

| Alias | Size | Description |
|-------|------|-------------|
| `bge-small` | ~130MB | Small, fast |
| `bge-base` | ~400MB | Default, good balance |
| `qwen-0.6b` | ~1.2GB | Qwen 0.6B, high quality |
| `bge-large` | ~1.2GB | Large BGE model |
| `qwen-4b` | ~8GB | Qwen 4B, needs GPU |

Server commands:
```bash
roots server start      # Start daemon
roots server stop       # Stop daemon
roots server status     # Check status
roots server restart    # Restart with new model
roots server model      # Show/set model
roots server install    # Install systemd service
roots server uninstall  # Remove systemd service
```

## Concepts

### Tree Structure

Knowledge is organized hierarchically:

```
.roots/
├── trading/                    # Tree
│   ├── patterns/              # Branch
│   │   ├── macd_crossovers.md # Leaf
│   │   └── volume_spikes.md
│   └── gotchas/
│       └── overfitting.md
└── _index.db                  # Search index
```

### Tiers

Knowledge matures through tiers:

| Tier | Description | Use For |
|------|-------------|---------|
| `leaves` | Raw observations, untested ideas | New discoveries |
| `branches` | Specific techniques, tested once | Promising patterns |
| `trunk` | Core concepts, repeatedly validated | Reliable knowledge |
| `roots` | Foundational truths, high confidence | Unchanging principles |

### Confidence

Score from 0-1 indicating how validated the knowledge is:

- `0.0-0.3`: Speculation, needs testing
- `0.4-0.6`: Observed, limited validation
- `0.7-0.8`: Tested multiple times
- `0.9-1.0`: Proven, high confidence

## CLI Reference

### Structure Commands

```bash
roots init                          # Initialize .roots directory
roots tree <name>                   # Create a tree
roots tree                          # List trees
roots branch <tree> <name>          # Create a branch
roots branch <tree>                 # List branches in tree
roots show [tree]                   # Show tree structure
```

### Knowledge Commands

```bash
# Add knowledge
roots add <branch> "content" \
    --tree <tree> \              # Optional if branch is unique
    --name <name> \              # Optional, auto-generated
    --tier <tier> \              # roots|trunk|branches|leaves
    --confidence <0-1> \
    --tags "tag1,tag2"

# Also supports tree/branch syntax
roots add edge/patterns "content"

# Retrieve
roots get <path>                    # Get specific leaf
roots search <query>                # Semantic search
roots search <query> --tier trunk   # Filter by tier
roots search <query> --tag momentum # Filter by tag

# Link knowledge
roots link <from> <to> --relation supports
roots link <from> <to> --relation contradicts
roots related <path>                # Show related leaves
```

### Configuration

```bash
# Per-project embedding model (stored in .roots/_config.yaml)
roots config model qwen-0.6b
roots config --list-models

# Global server model (stored in ~/.config/roots/config.yaml)
roots server model qwen-0.6b
```

### Maintenance

```bash
roots stats                         # Show statistics
roots reindex                       # Rebuild search index
roots prime                         # Output context (for hooks)
roots prune                         # Find stale/conflicting knowledge
roots tags                          # List all tags
roots self-update                   # Update from GitHub
```

## Claude Code Integration

Install hooks to inject context on session start:

```bash
roots hooks
```

This adds hooks to `.claude/settings.local.json` that run `roots prime` on:
- Session start
- Context compaction

### Context Matching

Optionally match knowledge to each prompt:

```bash
roots hooks --context-mode tags     # Match by tags (fast)
roots hooks --context-mode lite     # N-gram similarity
roots hooks --context-mode semantic # ML embeddings (needs server)
```

### Suggested Workflow

1. **During work**: When you discover something valuable, add it:
   ```bash
   roots add patterns "Funding rate spikes precede reversals" --tier leaves
   ```

2. **After validation**: Promote validated knowledge:
   ```bash
   roots update patterns/funding_rate_spikes.md --tier trunk --confidence 0.7
   ```

3. **Before starting**: Search for relevant context:
   ```bash
   roots search "funding rate trading"
   ```

## Python API

```python
from roots import KnowledgeBase

# Initialize
kb = KnowledgeBase()  # Auto-finds .roots

# Create structure
kb.create_tree("trading")
kb.add_branch("trading", "patterns")

# Add knowledge
path = kb.add_leaf(
    branch="patterns",
    content="MACD crossovers in trending markets",
    tree="trading",
    tier="trunk",
    confidence=0.8,
    tags=["indicators", "momentum"]
)

# Search
results = kb.search("momentum indicators", limit=5)
for r in results:
    print(f"{r.file_path}: {r.score:.3f}")
    print(f"  {r.content[:100]}...")

# Get specific leaf
leaf = kb.get_leaf("trading/patterns/macd_crossovers")
print(leaf.content)

# Link knowledge
kb.link("path/to/leaf1.md", "path/to/leaf2.md", relation="supports")
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ROOTS_PATH` | Override .roots location |

## Storage

- Knowledge stored as markdown with YAML frontmatter
- Index stored in SQLite (`_index.db`)
- Embeddings serialized as binary in SQLite
- Human-readable, git-friendly, portable

## License

MIT

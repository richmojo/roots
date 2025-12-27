# Roots

A semantic knowledge base for AI agents. Accumulate and search domain knowledge across sessions.

## Why Roots?

AI agents forget everything between sessions. Roots gives them persistent memory:

- **Semantic search** - Find relevant knowledge by meaning, not just keywords
- **Hierarchical organization** - Trees, branches, and leaves structure your knowledge
- **Confidence tiers** - Track how validated each piece of knowledge is
- **Cross-references** - Link related or contradicting knowledge
- **Claude Code integration** - Hooks to inject context on session start

## Installation

Requires [uv](https://docs.astral.sh/uv/).

```bash
# Install as a CLI tool
uv tool install git+https://github.com/richmojo/roots.git

# Or clone and install locally
git clone https://github.com/richmojo/roots.git
cd roots
uv tool install .
```

**As a project dependency:**

```bash
# Basic install (uses lightweight embeddings)
uv add git+https://github.com/richmojo/roots.git

# With high-quality embeddings (~500MB model download)
uv add "roots-kb[embeddings] @ git+https://github.com/richmojo/roots.git"
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

### Maintenance

```bash
roots stats                         # Show statistics
roots reindex                       # Rebuild search index
roots prime                         # Output context (for hooks)
```

## Claude Code Integration

Roots shines when integrated with Claude Code hooks. Add context on every session start:

### `.claude/hooks/session-start.sh`

```bash
#!/bin/bash
if [ -d ".roots" ]; then
    roots prime
fi
```

### `.claude/settings.json`

```json
{
  "hooks": {
    "session-start": ".claude/hooks/session-start.sh"
  }
}
```

Now every Claude Code session starts with your accumulated knowledge.

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

### Lightweight Mode

Skip the ~500MB embedding model for faster startup:

```python
# Uses simple n-gram hashing instead of sentence-transformers
kb = KnowledgeBase(use_sentence_transformers=False)
```

Good enough for small knowledge bases. Switch to full embeddings when you have 100+ items.

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

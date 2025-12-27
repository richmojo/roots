"""
Basic usage example for roots.

Shows how to create knowledge structure, add items, and search.
"""

from roots import KnowledgeBase

# Initialize (finds .roots in current or parent directories)
kb = KnowledgeBase()

# Create structure
kb.create_tree("trading", description="Trading domain knowledge")
kb.add_branch("trading", "patterns", description="Market patterns")
kb.add_branch("trading", "gotchas", description="Things to avoid")

# Add knowledge at different tiers
kb.add_leaf(
    branch="patterns",
    tree="trading",
    content="""
    MACD crossovers are most reliable in trending markets.
    In ranging/choppy markets, they generate many false signals.
    Combine with ADX > 25 to filter for trend presence.
    """,
    tier="trunk",  # Well-validated
    confidence=0.8,
    tags=["indicators", "momentum", "trend"],
)

kb.add_leaf(
    branch="patterns",
    tree="trading",
    content="""
    Volume spikes on breakouts confirm the move.
    Breakouts without volume often fail and reverse.
    Look for 2x average volume minimum.
    """,
    tier="trunk",
    confidence=0.75,
    tags=["volume", "breakouts"],
)

kb.add_leaf(
    branch="gotchas",
    tree="trading",
    content="""
    Overfitting in backtests: More parameters != better strategy.
    A simple strategy that works on multiple markets/timeframes
    is more robust than a complex one tuned to one dataset.
    """,
    tier="roots",  # Foundational truth
    confidence=0.95,
    tags=["backtesting", "overfitting"],
)

# Search for relevant knowledge
print("Searching for 'momentum indicators':\n")
results = kb.search("momentum indicators", limit=3)
for r in results:
    print(f"[{r.tier}] {r.file_path} (score: {r.score:.3f})")
    print(f"  {r.content[:100].strip()}...")
    print()

# Show the tree structure
print("\nKnowledge structure:")
print(kb.show_tree())

# Get stats
print("\nStatistics:")
all_leaves = kb.index.get_all_leaves()
by_tier = {}
for entry in all_leaves:
    by_tier[entry.tier] = by_tier.get(entry.tier, 0) + 1

print(f"  Total items: {len(all_leaves)}")
for tier, count in sorted(by_tier.items()):
    print(f"  {tier}: {count}")

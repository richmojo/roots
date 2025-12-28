"""
roots - A semantic knowledge base for AI agents.

Accumulate and search domain knowledge across sessions.
Store insights as markdown files, search via embeddings.

Quick Start:
    from roots import KnowledgeBase

    kb = KnowledgeBase()
    kb.create_tree("trading")
    kb.add_branch("trading", "patterns")
    kb.add_leaf("patterns", "MACD crossovers work best in trending markets", tree="trading")

    results = kb.search("momentum indicators")
"""

from roots.config import RootsConfig, SUGGESTED_MODELS
from roots.knowledge_base import KnowledgeBase, Leaf, SearchResult
from roots.index import IndexEntry

__version__ = "0.1.0"
__all__ = ["KnowledgeBase", "Leaf", "SearchResult", "IndexEntry", "RootsConfig", "SUGGESTED_MODELS"]

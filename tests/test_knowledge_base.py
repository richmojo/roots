"""Tests for the KnowledgeBase class."""

import tempfile
from pathlib import Path

import pytest

from roots import KnowledgeBase


@pytest.fixture
def kb():
    """Create a temporary knowledge base for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        kb = KnowledgeBase(
            roots_path=Path(tmpdir) / ".roots",
            use_sentence_transformers=False,  # Use lite embedder for speed
        )
        yield kb


class TestTreeStructure:
    def test_create_tree(self, kb):
        path = kb.create_tree("trading", description="Trading knowledge")
        assert path.exists()
        assert (path / "_meta.yaml").exists()

    def test_list_trees(self, kb):
        kb.create_tree("trading")
        kb.create_tree("coding")
        trees = kb.list_trees()
        assert "trading" in trees
        assert "coding" in trees

    def test_add_branch(self, kb):
        kb.create_tree("trading")
        path = kb.add_branch("trading", "patterns")
        assert path.exists()
        assert (path / "_meta.yaml").exists()

    def test_list_branches(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")
        kb.add_branch("trading", "gotchas")
        branches = kb.list_branches("trading")
        assert "patterns" in branches
        assert "gotchas" in branches


class TestLeaves:
    def test_add_leaf(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")

        path = kb.add_leaf(
            branch="patterns",
            tree="trading",
            content="MACD crossovers work in trends",
            tier="trunk",
            confidence=0.8,
            tags=["indicators"],
        )

        assert path.endswith(".md")
        leaf = kb.get_leaf(path)
        assert leaf is not None
        assert "MACD" in leaf.content
        assert leaf.tier == "trunk"
        assert leaf.confidence == 0.8
        assert "indicators" in leaf.tags

    def test_auto_find_branch(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "unique_branch")

        # Should find branch without specifying tree
        path = kb.add_leaf(branch="unique_branch", content="Test content")
        assert path is not None

    def test_update_leaf(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")
        path = kb.add_leaf(
            branch="patterns", tree="trading", content="Original", tier="leaves"
        )

        kb.update_leaf(path, content="Updated", tier="trunk", confidence=0.9)

        leaf = kb.get_leaf(path)
        assert leaf.content == "Updated"
        assert leaf.tier == "trunk"
        assert leaf.confidence == 0.9

    def test_delete_leaf(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")
        path = kb.add_leaf(branch="patterns", tree="trading", content="To delete")

        kb.delete_leaf(path)

        assert kb.get_leaf(path) is None


class TestSearch:
    def test_basic_search(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")

        kb.add_leaf(
            branch="patterns",
            tree="trading",
            content="MACD momentum indicator crossovers",
        )
        kb.add_leaf(
            branch="patterns",
            tree="trading",
            content="Volume spikes on breakouts",
        )

        results = kb.search("momentum indicators")
        assert len(results) > 0
        # MACD should rank higher for momentum query
        assert "macd" in results[0].file_path.lower() or "momentum" in results[0].content.lower()

    def test_search_with_tier_filter(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")

        kb.add_leaf(branch="patterns", tree="trading", content="Trunk item", tier="trunk")
        kb.add_leaf(branch="patterns", tree="trading", content="Leaf item", tier="leaves")

        results = kb.search("item", tiers=["trunk"])
        assert all(r.tier == "trunk" for r in results)

    def test_search_with_tag_filter(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")

        kb.add_leaf(
            branch="patterns", tree="trading", content="Tagged", tags=["important"]
        )
        kb.add_leaf(branch="patterns", tree="trading", content="Untagged", tags=[])

        results = kb.search("content", tags=["important"])
        assert all("important" in r.tags for r in results)


class TestLinks:
    def test_link_leaves(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")

        path1 = kb.add_leaf(branch="patterns", tree="trading", content="First")
        path2 = kb.add_leaf(branch="patterns", tree="trading", content="Second")

        kb.link(path1, path2, relation="supports")

        related = kb.get_related(path1)
        assert "supports" in related
        assert any(leaf.file_path == path2 for leaf in related["supports"])


class TestReindex:
    def test_reindex(self, kb):
        kb.create_tree("trading")
        kb.add_branch("trading", "patterns")
        kb.add_leaf(branch="patterns", tree="trading", content="Item 1")
        kb.add_leaf(branch="patterns", tree="trading", content="Item 2")

        count = kb.reindex()
        assert count == 2

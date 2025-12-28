"""
knowledge_base - Main interface for agent knowledge operations.

Provides a tree-structured knowledge base with semantic search.
Knowledge is stored as markdown files with YAML frontmatter,
indexed in SQLite for fast retrieval.
"""

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml

from roots.config import RootsConfig
from roots.embeddings import cosine_similarity, get_embedder
from roots.index import IndexEntry, RootsIndex

Tier = Literal["roots", "trunk", "branches", "leaves"]

# Environment variable for custom roots location
ROOTS_PATH_ENV = "ROOTS_PATH"


@dataclass
class SearchResult:
    """A search result with relevance score."""

    file_path: str
    content: str
    tier: Tier
    confidence: float
    tags: list[str]
    score: float  # Similarity score


@dataclass
class Leaf:
    """A knowledge leaf with full content and metadata."""

    tree: str
    branch: str
    name: str
    content: str
    tier: Tier
    confidence: float
    tags: list[str]
    file_path: str


def find_roots_path() -> Path:
    """
    Find the .roots directory.

    Search order:
    1. ROOTS_PATH environment variable
    2. Walk up from cwd looking for .roots/
    3. Fall back to cwd/.roots/
    """
    # Check environment variable
    if env_path := os.environ.get(ROOTS_PATH_ENV):
        return Path(env_path)

    # Walk up looking for .roots
    current = Path.cwd()
    while current != current.parent:
        roots_path = current / ".roots"
        if roots_path.exists():
            return roots_path
        current = current.parent

    # Fall back to cwd
    return Path.cwd() / ".roots"


class KnowledgeBase:
    """
    Agent knowledge accumulation system.

    Stores knowledge as markdown files in a tree structure:
    .roots/{tree}/{branch}/{leaf}.md

    Provides semantic search via embeddings indexed in SQLite.

    Tier System:
    - roots: Foundational, stable knowledge (high confidence)
    - trunk: Core concepts and patterns
    - branches: Specific techniques and approaches
    - leaves: Individual observations and notes (default)
    """

    def __init__(
        self,
        roots_path: Path | str | None = None,
    ):
        """
        Initialize the knowledge base.

        Args:
            roots_path: Path to .roots directory. If None, auto-detected.
        """
        if roots_path is None:
            roots_path = find_roots_path()
        self.roots_path = Path(roots_path)
        self.roots_path.mkdir(parents=True, exist_ok=True)

        self.index = RootsIndex(self.roots_path / "_index.db")
        self.config = RootsConfig(self.roots_path)
        self._embedder = None

    @property
    def embedder(self):
        """Lazy load embedder based on config."""
        if self._embedder is None:
            model_name, model_type = self.config.get_resolved_model()
            self._embedder = get_embedder(model_name, model_type)
        return self._embedder

    def reset_embedder(self) -> None:
        """Reset embedder (call after changing model config)."""
        self._embedder = None

    # -------------------------------------------------------------------------
    # Tree/Branch/Leaf Structure
    # -------------------------------------------------------------------------

    def create_tree(self, name: str, description: str = "") -> Path:
        """
        Create a new knowledge tree.

        Args:
            name: Tree name (will be slugified for directory name)
            description: Optional description

        Returns:
            Path to the created tree directory
        """
        tree_path = self.roots_path / self._slugify(name)
        tree_path.mkdir(exist_ok=True)

        meta_path = tree_path / "_meta.yaml"
        if not meta_path.exists():
            meta = {
                "name": name,
                "description": description,
                "created_at": datetime.now().isoformat(),
            }
            meta_path.write_text(yaml.dump(meta, default_flow_style=False))

        return tree_path

    def add_branch(self, tree: str, branch: str, description: str = "") -> Path:
        """
        Add a branch to a tree.

        Args:
            tree: Tree name
            branch: Branch name
            description: Optional description

        Returns:
            Path to the created branch directory
        """
        tree_path = self.roots_path / self._slugify(tree)
        if not tree_path.exists():
            self.create_tree(tree)

        branch_path = tree_path / self._slugify(branch)
        branch_path.mkdir(exist_ok=True)

        meta_path = branch_path / "_meta.yaml"
        if not meta_path.exists():
            meta = {
                "name": branch,
                "description": description,
                "created_at": datetime.now().isoformat(),
            }
            meta_path.write_text(yaml.dump(meta, default_flow_style=False))

        return branch_path

    def add_leaf(
        self,
        branch: str,
        content: str,
        name: str | None = None,
        tree: str | None = None,
        tier: Tier = "leaves",
        confidence: float = 0.5,
        tags: list[str] | None = None,
    ) -> str:
        """
        Add a knowledge leaf to a branch.

        Args:
            branch: Branch name (or tree/branch path)
            content: The knowledge content
            name: Optional name (auto-generated if not provided)
            tree: Tree name (required if branch doesn't include tree)
            tier: Knowledge tier (roots, trunk, branches, leaves)
            confidence: Confidence score 0-1
            tags: Optional tags for categorization

        Returns:
            Relative file path of the created leaf
        """
        tags = tags or []

        # Resolve branch path
        if tree:
            branch_path = self.roots_path / self._slugify(tree) / self._slugify(branch)
        else:
            # Try to find branch in existing trees
            branch_path = self._find_branch(branch)
            if not branch_path:
                raise ValueError(
                    f"Branch '{branch}' not found. Specify tree or create branch first."
                )

        branch_path.mkdir(parents=True, exist_ok=True)

        # Generate name if not provided
        if not name:
            name = self._generate_leaf_name(content)

        # Create markdown file
        file_path = branch_path / f"{self._slugify(name)}.md"
        frontmatter = {
            "tier": tier,
            "confidence": confidence,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
        }

        md_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}"
        file_path.write_text(md_content)

        # Index the leaf
        rel_path = str(file_path.relative_to(self.roots_path))
        self._index_leaf(rel_path, content, tier, confidence, tags)

        return rel_path

    def get_leaf(self, file_path: str) -> Leaf | None:
        """Get a leaf by its file path (with or without .md extension)."""
        # Add .md extension if not present
        if not file_path.endswith(".md"):
            file_path = f"{file_path}.md"

        full_path = self.roots_path / file_path
        if not full_path.exists():
            return None

        content, meta = self._parse_markdown(full_path)
        parts = Path(file_path).parts

        return Leaf(
            tree=parts[0] if len(parts) > 0 else "",
            branch=parts[1] if len(parts) > 1 else "",
            name=parts[-1].replace(".md", "") if parts else "",
            content=content,
            tier=meta.get("tier", "leaves"),
            confidence=meta.get("confidence", 0.5),
            tags=meta.get("tags", []),
            file_path=file_path,
        )

    def update_leaf(
        self,
        file_path: str,
        content: str | None = None,
        tier: Tier | None = None,
        confidence: float | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Update an existing leaf."""
        full_path = self.roots_path / file_path
        if not full_path.exists():
            raise FileNotFoundError(f"Leaf not found: {file_path}")

        old_content, meta = self._parse_markdown(full_path)

        # Update fields
        if content is not None:
            old_content = content
        if tier is not None:
            meta["tier"] = tier
        if confidence is not None:
            meta["confidence"] = confidence
        if tags is not None:
            meta["tags"] = tags

        meta["updated_at"] = datetime.now().isoformat()

        # Write back
        md_content = f"---\n{yaml.dump(meta, default_flow_style=False)}---\n\n{old_content}"
        full_path.write_text(md_content)

        # Re-index
        self._index_leaf(
            file_path,
            old_content,
            meta.get("tier", "leaves"),
            meta.get("confidence", 0.5),
            meta.get("tags", []),
        )

    def delete_leaf(self, file_path: str) -> None:
        """Delete a leaf."""
        full_path = self.roots_path / file_path
        if full_path.exists():
            full_path.unlink()
        self.index.delete_leaf(file_path)

    # -------------------------------------------------------------------------
    # Search and Retrieval
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 10,
        tiers: list[Tier] | None = None,
        tags: list[str] | None = None,
        min_confidence: float = 0.0,
    ) -> list[SearchResult]:
        """
        Semantic search across all knowledge.

        Args:
            query: Natural language query
            limit: Maximum results to return
            tiers: Filter by tiers (default: all)
            tags: Filter by tags (default: all)
            min_confidence: Minimum confidence threshold

        Returns:
            List of search results ordered by relevance
        """
        query_embedding = self.embedder.embed(query)
        all_entries = self.index.get_all_leaves()

        results = []
        for entry in all_entries:
            # Apply filters
            if tiers and entry.tier not in tiers:
                continue
            if tags and not any(t in entry.tags for t in tags):
                continue
            if entry.confidence < min_confidence:
                continue

            # Compute similarity
            score = cosine_similarity(query_embedding, entry.embedding)

            # Get content
            leaf = self.get_leaf(entry.file_path)
            if leaf:
                results.append(
                    SearchResult(
                        file_path=entry.file_path,
                        content=leaf.content,
                        tier=entry.tier,
                        confidence=entry.confidence,
                        tags=entry.tags,
                        score=score,
                    )
                )

        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def get_by_tags(self, tags: list[str], limit: int = 20) -> list[Leaf]:
        """Get all leaves matching any of the given tags."""
        all_entries = self.index.get_all_leaves()
        results = []

        for entry in all_entries:
            if any(t in entry.tags for t in tags):
                leaf = self.get_leaf(entry.file_path)
                if leaf:
                    results.append(leaf)

        return results[:limit]

    def get_by_tier(self, tier: Tier) -> list[Leaf]:
        """Get all leaves of a specific tier."""
        all_entries = self.index.get_all_leaves()
        results = []

        for entry in all_entries:
            if entry.tier == tier:
                leaf = self.get_leaf(entry.file_path)
                if leaf:
                    results.append(leaf)

        return results

    # -------------------------------------------------------------------------
    # Cross-references
    # -------------------------------------------------------------------------

    def link(self, from_path: str, to_path: str, relation: str = "related_to") -> None:
        """
        Create a link between two leaves.

        Args:
            from_path: Source leaf path
            to_path: Target leaf path
            relation: Relationship type (supports, contradicts, related_to)
        """
        self.index.add_link(from_path, to_path, relation)

    def unlink(self, from_path: str, to_path: str, relation: str) -> None:
        """Remove a link between two leaves."""
        self.index.remove_link(from_path, to_path, relation)

    def get_related(self, file_path: str) -> dict[str, list[Leaf]]:
        """
        Get all leaves related to a given leaf.

        Returns:
            Dict mapping relation type to list of related leaves
        """
        links_from = self.index.get_links_from(file_path)
        links_to = self.index.get_links_to(file_path)

        related: dict[str, list[Leaf]] = {}

        for link in links_from:
            leaf = self.get_leaf(link.to_path)
            if leaf:
                related.setdefault(link.relation, []).append(leaf)

        for link in links_to:
            leaf = self.get_leaf(link.from_path)
            if leaf:
                # Reverse relation name for incoming links
                inv_relation = f"is_{link.relation}_by"
                related.setdefault(inv_relation, []).append(leaf)

        return related

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def list_trees(self) -> list[str]:
        """List all knowledge trees."""
        return [
            d.name
            for d in self.roots_path.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        ]

    def list_branches(self, tree: str) -> list[str]:
        """List all branches in a tree."""
        tree_path = self.roots_path / self._slugify(tree)
        if not tree_path.exists():
            return []

        return [
            d.name
            for d in tree_path.iterdir()
            if d.is_dir() and not d.name.startswith("_")
        ]

    def list_leaves(self, tree: str, branch: str) -> list[str]:
        """List all leaves in a branch."""
        branch_path = self.roots_path / self._slugify(tree) / self._slugify(branch)
        if not branch_path.exists():
            return []

        return [f.stem for f in branch_path.glob("*.md") if not f.name.startswith("_")]

    def show_tree(self, tree: str | None = None) -> str:
        """
        Show tree structure as text.

        Args:
            tree: Specific tree to show, or None for all trees
        """
        lines = []

        trees = [tree] if tree else self.list_trees()

        for t in trees:
            lines.append(f"{t}/")
            for branch in self.list_branches(t):
                lines.append(f"  {branch}/")
                for leaf in self.list_leaves(t, branch):
                    leaf_obj = self.get_leaf(
                        f"{self._slugify(t)}/{self._slugify(branch)}/{leaf}.md"
                    )
                    tier_marker = self._tier_marker(leaf_obj.tier if leaf_obj else "leaves")
                    lines.append(f"    {tier_marker} {leaf}")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Index Management
    # -------------------------------------------------------------------------

    def reindex(self) -> int:
        """
        Rebuild the index from all markdown files.

        Clears existing embeddings first to handle model changes.

        Returns:
            Number of leaves indexed
        """
        # Clear existing entries to handle embedding dimension changes
        self.index.clear_leaves()

        count = 0
        for md_file in self.roots_path.rglob("*.md"):
            if md_file.name.startswith("_"):
                continue

            rel_path = str(md_file.relative_to(self.roots_path))
            content, meta = self._parse_markdown(md_file)

            self._index_leaf(
                rel_path,
                content,
                meta.get("tier", "leaves"),
                meta.get("confidence", 0.5),
                meta.get("tags", []),
            )
            count += 1

        return count

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _index_leaf(
        self, file_path: str, content: str, tier: str, confidence: float, tags: list[str]
    ) -> None:
        """Index a leaf in the database."""
        embedding = self.embedder.embed(content)
        content_hash = hashlib.md5(content.encode()).hexdigest()

        entry = IndexEntry(
            file_path=file_path,
            content_hash=content_hash,
            embedding=embedding,
            tier=tier,
            confidence=confidence,
            tags=tags,
            updated_at=datetime.now(),
        )

        self.index.upsert_leaf(entry)

    def _parse_markdown(self, path: Path) -> tuple[str, dict]:
        """Parse markdown file with YAML frontmatter."""
        text = path.read_text()

        # Extract frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
                content = parts[2].strip()
                return content, meta

        return text, {}

    def _find_branch(self, branch: str) -> Path | None:
        """Find a branch by name across all trees."""
        slug = self._slugify(branch)
        for tree in self.list_trees():
            branch_path = self.roots_path / self._slugify(tree) / slug
            if branch_path.exists():
                return branch_path
        return None

    def _generate_leaf_name(self, content: str) -> str:
        """Generate a name from content."""
        # Take first 50 chars, clean up
        name = content[:50].strip()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"\s+", "_", name)
        return name[:40] or "unnamed"

    def _slugify(self, text: str) -> str:
        """Convert text to a valid directory/file name."""
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "_", slug)
        return slug

    def _tier_marker(self, tier: str) -> str:
        """Get a marker for display."""
        markers = {
            "roots": "[R]",
            "trunk": "[T]",
            "branches": "[B]",
            "leaves": "[L]",
        }
        return markers.get(tier, "[?]")

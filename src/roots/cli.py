"""
roots - CLI for agent knowledge base.

Commands:
    init     - Initialize a .roots directory
    tree     - Create/list knowledge trees
    branch   - Create/list branches
    add      - Add knowledge
    search   - Semantic search
    show     - Show tree structure
    get      - Get a specific leaf
    link     - Link related knowledge
    related  - Show related knowledge
    reindex  - Rebuild search index
    stats    - Show statistics
    prime    - Output context for Claude Code hooks
"""

import click

from roots.knowledge_base import KnowledgeBase, find_roots_path


def main():
    """Entry point for the roots CLI."""
    roots()


def get_kb() -> KnowledgeBase:
    """Get the knowledge base instance."""
    return KnowledgeBase()


@click.group()
@click.version_option(package_name="roots-kb")
def roots():
    """Agent knowledge base - accumulate and search domain knowledge."""
    pass


@roots.command("init")
@click.option("--path", "-p", default=".", help="Directory to initialize .roots in")
def init_cmd(path: str):
    """Initialize a .roots directory."""
    from pathlib import Path

    roots_path = Path(path) / ".roots"
    roots_path.mkdir(parents=True, exist_ok=True)
    (roots_path / "_index.db").touch()

    click.echo(f"Initialized roots at: {roots_path}")
    click.echo("\nNext steps:")
    click.echo("  roots tree <name>           # Create a knowledge tree")
    click.echo("  roots branch <tree> <name>  # Create a branch")
    click.echo("  roots add <branch> <text>   # Add knowledge")


@roots.command("tree")
@click.argument("name", required=False)
@click.option("--description", "-d", default="", help="Tree description")
def tree_cmd(name: str | None, description: str):
    """Create a knowledge tree or list existing trees."""
    kb = get_kb()

    if name:
        path = kb.create_tree(name, description)
        click.echo(f"Created tree: {path}")
    else:
        trees = kb.list_trees()
        if trees:
            click.echo("Knowledge trees:")
            for t in trees:
                click.echo(f"  {t}/")
        else:
            click.echo("No knowledge trees yet. Create one with: roots tree <name>")


@roots.command("branch")
@click.argument("tree")
@click.argument("name", required=False)
@click.option("--description", "-d", default="", help="Branch description")
def branch_cmd(tree: str, name: str | None, description: str):
    """Create a branch or list branches in a tree."""
    kb = get_kb()

    if name:
        path = kb.add_branch(tree, name, description)
        click.echo(f"Created branch: {path}")
    else:
        branches = kb.list_branches(tree)
        if branches:
            click.echo(f"Branches in {tree}:")
            for b in branches:
                click.echo(f"  {b}/")
        else:
            click.echo(f"No branches in {tree}. Create one with: roots branch {tree} <name>")


@roots.command("add")
@click.argument("branch")
@click.argument("content")
@click.option("--tree", "-t", default=None, help="Tree name (if branch name is ambiguous)")
@click.option("--name", "-n", default=None, help="Leaf name (auto-generated if not provided)")
@click.option(
    "--tier",
    default="leaves",
    type=click.Choice(["roots", "trunk", "branches", "leaves"]),
)
@click.option("--confidence", "-c", default=0.5, type=float, help="Confidence 0-1")
@click.option("--tags", default="", help="Comma-separated tags")
def add_cmd(
    branch: str,
    content: str,
    tree: str | None,
    name: str | None,
    tier: str,
    confidence: float,
    tags: str,
):
    """Add knowledge to a branch."""
    kb = get_kb()

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    try:
        file_path = kb.add_leaf(
            branch=branch,
            content=content,
            name=name,
            tree=tree,
            tier=tier,
            confidence=confidence,
            tags=tag_list,
        )
        click.echo(f"Added: {file_path}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@roots.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=5, help="Max results")
@click.option("--tier", "-t", multiple=True, help="Filter by tier (can repeat)")
@click.option("--tag", multiple=True, help="Filter by tag (can repeat)")
@click.option("--min-confidence", default=0.0, type=float, help="Minimum confidence")
def search_cmd(query: str, limit: int, tier: tuple, tag: tuple, min_confidence: float):
    """Semantic search across all knowledge."""
    kb = get_kb()

    tiers = list(tier) if tier else None
    tags = list(tag) if tag else None

    results = kb.search(
        query=query,
        limit=limit,
        tiers=tiers,
        tags=tags,
        min_confidence=min_confidence,
    )

    if not results:
        click.echo("No results found.")
        return

    for i, r in enumerate(results, 1):
        click.echo(f"\n[{i}] {r.file_path} (score: {r.score:.3f})")
        click.echo(f"    tier: {r.tier}, confidence: {r.confidence:.2f}")
        if r.tags:
            click.echo(f"    tags: {', '.join(r.tags)}")
        # Truncate content for display
        preview = r.content[:200] + "..." if len(r.content) > 200 else r.content
        click.echo(f"    {preview}")


@roots.command("show")
@click.argument("tree", required=False)
def show_cmd(tree: str | None):
    """Show tree structure."""
    kb = get_kb()
    output = kb.show_tree(tree)
    if output:
        click.echo(output)
    else:
        click.echo("No knowledge trees yet.")


@roots.command("get")
@click.argument("file_path")
def get_cmd(file_path: str):
    """Get a specific leaf by path."""
    kb = get_kb()
    leaf = kb.get_leaf(file_path)

    if not leaf:
        click.echo(f"Not found: {file_path}", err=True)
        raise click.Abort()

    click.echo(f"Tree: {leaf.tree}")
    click.echo(f"Branch: {leaf.branch}")
    click.echo(f"Tier: {leaf.tier}")
    click.echo(f"Confidence: {leaf.confidence}")
    click.echo(f"Tags: {', '.join(leaf.tags) if leaf.tags else 'none'}")
    click.echo(f"\n{leaf.content}")


@roots.command("link")
@click.argument("from_path")
@click.argument("to_path")
@click.option(
    "--relation",
    "-r",
    default="related_to",
    type=click.Choice(["supports", "contradicts", "related_to"]),
)
def link_cmd(from_path: str, to_path: str, relation: str):
    """Link two pieces of knowledge."""
    kb = get_kb()
    kb.link(from_path, to_path, relation)
    click.echo(f"Linked: {from_path} --[{relation}]--> {to_path}")


@roots.command("related")
@click.argument("file_path")
def related_cmd(file_path: str):
    """Show related knowledge for a leaf."""
    kb = get_kb()
    related = kb.get_related(file_path)

    if not related:
        click.echo("No related knowledge found.")
        return

    for relation, leaves in related.items():
        click.echo(f"\n{relation}:")
        for leaf in leaves:
            click.echo(f"  - {leaf.file_path}")


@roots.command("reindex")
def reindex_cmd():
    """Rebuild the search index from markdown files."""
    kb = get_kb()
    count = kb.reindex()
    click.echo(f"Indexed {count} leaves.")


@roots.command("stats")
def stats_cmd():
    """Show knowledge base statistics."""
    kb = get_kb()

    trees = kb.list_trees()
    total_leaves = len(kb.index.get_all_leaves())

    by_tier = {}
    for entry in kb.index.get_all_leaves():
        by_tier[entry.tier] = by_tier.get(entry.tier, 0) + 1

    click.echo(f"Trees: {len(trees)}")
    click.echo(f"Total leaves: {total_leaves}")
    click.echo("\nBy tier:")
    for tier in ["roots", "trunk", "branches", "leaves"]:
        count = by_tier.get(tier, 0)
        if count:
            click.echo(f"  {tier}: {count}")


@roots.command("prime")
def prime_cmd():
    """
    Output roots context for Claude Code hooks.

    Designed for SessionStart/PreCompact hooks to remind agents
    about available knowledge after context compaction.
    """
    kb = get_kb()

    trees = kb.list_trees()
    all_leaves = kb.index.get_all_leaves()

    # Count by tier
    by_tier = {}
    all_tags = set()
    for entry in all_leaves:
        by_tier[entry.tier] = by_tier.get(entry.tier, 0) + 1
        all_tags.update(entry.tags)

    output = []
    output.append("# Roots - Persistent Knowledge Base")
    output.append("")
    output.append("This is a persistent knowledge store for accumulating insights.")
    output.append("**Save anything valuable** that would help future agents:")
    output.append("- Patterns and strategies that work (or don't)")
    output.append("- Domain-specific observations")
    output.append("- Technical insights and gotchas")
    output.append("- Lessons learned from experiments")
    output.append("")
    output.append("Knowledge persists across sessions. Search before reinventing.")
    output.append("")

    if not trees:
        output.append("No knowledge accumulated yet. Use `roots tree <name>` to start.")
    else:
        output.append(f"**{len(all_leaves)} knowledge items** across {len(trees)} trees")
        output.append("")

        # Tier summary
        tier_parts = []
        for tier in ["roots", "trunk", "branches", "leaves"]:
            count = by_tier.get(tier, 0)
            if count:
                tier_parts.append(f"{tier}: {count}")
        if tier_parts:
            output.append(f"Tiers: {', '.join(tier_parts)}")

        # Trees
        output.append("")
        output.append("## Trees")
        for tree in trees:
            branches = kb.list_branches(tree)
            output.append(f"- **{tree}/** ({len(branches)} branches)")

        # Top tags
        if all_tags:
            output.append("")
            output.append("## Tags")
            output.append(f"{', '.join(sorted(all_tags)[:15])}")

        # Roots (always show - foundational knowledge)
        roots_leaves = kb.get_by_tier("roots")
        if roots_leaves:
            output.append("")
            output.append("## Foundational Knowledge (roots)")
            for leaf in roots_leaves[:5]:
                preview = (
                    leaf.content[:100] + "..." if len(leaf.content) > 100 else leaf.content
                )
                output.append(f"- {preview}")

    output.append("")
    output.append("## Commands")
    output.append("```")
    output.append("roots search <query>           # Semantic search")
    output.append("roots show [tree]              # Show structure")
    output.append("roots add <branch> <content> --tier <tier> --tags <tags>")
    output.append("roots tree <name>              # Create tree")
    output.append("roots branch <tree> <name>     # Create branch")
    output.append("roots get <path>               # View a leaf")
    output.append("roots stats                    # Show statistics")
    output.append("```")

    click.echo("\n".join(output))


if __name__ == "__main__":
    main()

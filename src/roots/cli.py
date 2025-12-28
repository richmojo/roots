"""
roots - CLI for agent knowledge base.

Commands:
    init     - Initialize a .roots directory
    hooks    - Install Claude Code hooks
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

import json
from pathlib import Path

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
@click.option("--hooks", is_flag=True, help="Also install Claude Code hooks")
def init_cmd(path: str, hooks: bool):
    """Initialize a .roots directory."""
    roots_path = Path(path) / ".roots"
    roots_path.mkdir(parents=True, exist_ok=True)
    (roots_path / "_index.db").touch()

    click.echo(f"Initialized roots at: {roots_path}")

    if hooks:
        # Also install hooks
        _install_hooks(Path(path))
    else:
        click.echo("\nNext steps:")
        click.echo("  roots hooks                 # Install Claude Code hooks")
        click.echo("  roots tree <name>           # Create a knowledge tree")
        click.echo("  roots branch <tree> <name>  # Create a branch")
        click.echo("  roots add <branch> <text>   # Add knowledge")


def _install_hooks(project_path: Path) -> bool:
    """Install Claude Code hooks for roots. Returns True if successful."""
    claude_dir = project_path / ".claude"
    settings_file = claude_dir / "settings.local.json"

    # Create .claude directory if needed
    claude_dir.mkdir(parents=True, exist_ok=True)

    # Load existing settings or create new
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    # Ensure hooks structure exists
    if "hooks" not in settings:
        settings["hooks"] = {}

    # Define the roots hook
    roots_hook = {
        "matcher": "",
        "hooks": [{"type": "command", "command": "roots prime"}],
    }

    # Add/update SessionStart hook
    session_hooks = settings["hooks"].get("SessionStart", [])
    # Check if roots hook already exists
    has_roots = any(
        any(h.get("command") == "roots prime" for h in entry.get("hooks", []))
        for entry in session_hooks
    )
    if not has_roots:
        session_hooks.append(roots_hook)
        settings["hooks"]["SessionStart"] = session_hooks

    # Add/update PreCompact hook
    compact_hooks = settings["hooks"].get("PreCompact", [])
    has_roots = any(
        any(h.get("command") == "roots prime" for h in entry.get("hooks", []))
        for entry in compact_hooks
    )
    if not has_roots:
        compact_hooks.append(roots_hook)
        settings["hooks"]["PreCompact"] = compact_hooks

    # Write settings
    settings_file.write_text(json.dumps(settings, indent=2) + "\n")
    return True


@roots.command("hooks")
@click.option("--path", "-p", default=".", help="Project directory")
@click.option("--remove", is_flag=True, help="Remove hooks instead of installing")
@click.option(
    "--context-mode",
    type=click.Choice(["none", "tags", "lite", "semantic"]),
    default="none",
    help="Also add prompt context hook with specified mode",
)
def hooks_cmd(path: str, remove: bool, context_mode: str):
    """Install or remove Claude Code hooks for roots.

    This configures SessionStart and PreCompact hooks to run 'roots prime',
    injecting knowledge context at the start of each session and before
    context compaction.

    Optionally add a prompt context hook with --context-mode:
    - tags: Match prompt words against leaf tags (fast)
    - lite: N-gram similarity (fast, basic)
    - semantic: Sentence-transformers (slower, best quality)
    """
    project_path = Path(path).resolve()
    claude_dir = project_path / ".claude"
    settings_file = claude_dir / "settings.local.json"

    if remove:
        if not settings_file.exists():
            click.echo("No Claude Code settings found.")
            return

        settings = json.loads(settings_file.read_text())
        hooks = settings.get("hooks", {})

        # Remove roots hooks
        for hook_type in ["SessionStart", "PreCompact", "UserPromptSubmit"]:
            if hook_type in hooks:
                hooks[hook_type] = [
                    entry
                    for entry in hooks[hook_type]
                    if not any(
                        h.get("command", "").startswith("roots ")
                        for h in entry.get("hooks", [])
                    )
                ]
                if not hooks[hook_type]:
                    del hooks[hook_type]

        settings["hooks"] = hooks
        settings_file.write_text(json.dumps(settings, indent=2) + "\n")
        click.echo("Removed roots hooks from Claude Code settings.")
        return

    # Install hooks
    if _install_hooks(project_path):
        click.echo(f"Installed Claude Code hooks at: {settings_file}")
        click.echo("")
        click.echo("Hooks configured:")
        click.echo("  SessionStart: roots prime")
        click.echo("  PreCompact:   roots prime")

    # Optionally add context hook
    if context_mode != "none":
        settings = json.loads(settings_file.read_text())
        if "hooks" not in settings:
            settings["hooks"] = {}

        context_hook = {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": f"roots context \"$PROMPT\" --mode {context_mode}",
                }
            ],
        }

        # Check if already exists
        prompt_hooks = settings["hooks"].get("UserPromptSubmit", [])
        has_context = any(
            any("roots context" in h.get("command", "") for h in entry.get("hooks", []))
            for entry in prompt_hooks
        )
        if not has_context:
            prompt_hooks.append(context_hook)
            settings["hooks"]["UserPromptSubmit"] = prompt_hooks
            settings_file.write_text(json.dumps(settings, indent=2) + "\n")

        click.echo(f"  UserPromptSubmit: roots context --mode {context_mode}")

    click.echo("")
    click.echo("Knowledge context will be injected on session start and before compaction.")
    if context_mode != "none":
        click.echo(f"Relevant knowledge will be shown for each prompt ({context_mode} matching).")


@roots.command("self-update")
def self_update_cmd():
    """Update roots to the latest version from GitHub."""
    import subprocess
    import sys

    click.echo("Updating roots from GitHub...")

    try:
        result = subprocess.run(
            ["uv", "tool", "install", "git+https://github.com/richmojo/roots.git", "--force"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            click.echo(f"Error updating: {result.stderr}", err=True)
            sys.exit(1)

        click.echo(result.stdout)
        click.echo("Updated successfully! Run 'roots --version' to verify.")

    except FileNotFoundError:
        click.echo("Error: 'uv' not found. Install uv first:", err=True)
        click.echo("  curl -LsSf https://astral.sh/uv/install.sh | sh", err=True)
        sys.exit(1)


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
@click.argument("location")
@click.argument("content")
@click.option("--tree", "-t", default=None, help="Tree name (if not specified in location)")
@click.option("--name", "-n", default=None, help="Leaf name (auto-generated if not provided)")
@click.option(
    "--tier",
    default="leaves",
    type=click.Choice(["roots", "trunk", "branches", "leaves"]),
)
@click.option("--confidence", "-c", default=0.5, type=float, help="Confidence 0-1")
@click.option("--tags", default="", help="Comma-separated tags")
def add_cmd(
    location: str,
    content: str,
    tree: str | None,
    name: str | None,
    tier: str,
    confidence: float,
    tags: str,
):
    """Add knowledge to a branch.

    Location can be:
    - branch name: "patterns" (tree auto-detected or use --tree)
    - tree/branch: "edge/patterns" (explicit tree)
    """
    kb = get_kb()

    # Parse location - support both "branch" and "tree/branch" syntax
    if "/" in location and tree is None:
        parts = location.split("/", 1)
        tree = parts[0]
        branch = parts[1]
    else:
        branch = location

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


@roots.command("tags")
@click.argument("tag", required=False)
def tags_cmd(tag: str | None):
    """List all tags or show leaves with a specific tag.

    Without arguments, lists all tags with counts.
    With a tag argument, shows all leaves tagged with that tag.
    """
    kb = get_kb()
    all_entries = kb.index.get_all_leaves()

    if tag:
        # Show leaves with this tag
        matching = [e for e in all_entries if tag in e.tags]
        if not matching:
            click.echo(f"No leaves found with tag '{tag}'")
            return

        click.echo(f"Leaves tagged '{tag}' ({len(matching)}):\n")
        for entry in matching:
            leaf = kb.get_leaf(entry.file_path)
            if leaf:
                preview = leaf.content[:80] + "..." if len(leaf.content) > 80 else leaf.content
                preview = preview.replace("\n", " ")
                click.echo(f"  [{leaf.tier[0].upper()}] {entry.file_path}")
                click.echo(f"      {preview}")
    else:
        # List all tags with counts
        tag_counts: dict[str, int] = {}
        for entry in all_entries:
            for t in entry.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1

        if not tag_counts:
            click.echo("No tags found.")
            return

        click.echo(f"Tags ({len(tag_counts)}):\n")
        for t, count in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
            click.echo(f"  {t}: {count}")


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
    output.append("ROOTS - Persistent Knowledge Base")
    output.append("")
    output.append("Persistent knowledge store. Save valuable insights for future sessions:")
    output.append("patterns, observations, technical gotchas, lessons learned.")
    output.append("Search before reinventing.")
    output.append("")

    if not trees:
        output.append("No knowledge yet. Start with: roots tree <name>")
    else:
        output.append(f"{len(all_leaves)} items across {len(trees)} trees")

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
        output.append("Trees:")
        for tree in trees:
            branches = kb.list_branches(tree)
            output.append(f"  {tree}/ ({len(branches)} branches)")

        # Top tags
        if all_tags:
            output.append("")
            output.append(f"Tags: {', '.join(sorted(all_tags)[:15])}")

        # Roots (always show - foundational knowledge)
        roots_leaves = kb.get_by_tier("roots")
        if roots_leaves:
            output.append("")
            output.append("Foundational (roots tier):")
            for leaf in roots_leaves[:5]:
                preview = leaf.content[:100].replace("\n", " ").strip()
                if len(leaf.content) > 100:
                    preview += "..."
                output.append(f"  - {preview}")

        # Recent activity (last 5 updated leaves)
        sorted_by_date = sorted(all_leaves, key=lambda e: e.updated_at, reverse=True)
        recent = sorted_by_date[:5]
        if recent:
            output.append("")
            output.append("Recent:")
            for entry in recent:
                leaf = kb.get_leaf(entry.file_path)
                if leaf:
                    date_str = entry.updated_at.strftime("%m-%d")
                    output.append(f"  [{date_str}] {entry.file_path}")

    # Check if context hook is enabled
    claude_settings = Path(".claude/settings.local.json")
    context_hook_enabled = False
    if claude_settings.exists():
        try:
            settings = json.loads(claude_settings.read_text())
            prompt_hooks = settings.get("hooks", {}).get("UserPromptSubmit", [])
            context_hook_enabled = any(
                any("roots context" in h.get("command", "") for h in entry.get("hooks", []))
                for entry in prompt_hooks
            )
        except (json.JSONDecodeError, KeyError):
            pass

    if context_hook_enabled:
        output.append("")
        output.append("Context hook enabled: related paths may appear above prompts.")
        output.append("These are optional references. Use 'roots get <path>' if relevant.")

    output.append("")
    output.append("Commands: roots search <query> | roots get <path> | roots add <branch> <content>")

    click.echo("\n".join(output))


@roots.command("prune")
@click.option("--tree", "-t", default=None, help="Limit to specific tree")
@click.option("--branch", "-b", default=None, help="Limit to specific branch")
@click.option("--dry-run", is_flag=True, help="Show what would be pruned without deleting")
@click.option("--stale-days", default=90, help="Flag leaves not updated in N days")
@click.option("--min-confidence", default=0.3, help="Flag leaves below this confidence")
@click.option("--detect-conflicts", is_flag=True, help="Find semantically similar leaves that may conflict")
def prune_cmd(
    tree: str | None,
    branch: str | None,
    dry_run: bool,
    stale_days: int,
    min_confidence: float,
    detect_conflicts: bool,
):
    """
    Analyze knowledge base for stale, low-quality, or conflicting information.

    Helps maintain a clean knowledge base by identifying:
    - Stale leaves (not updated in N days)
    - Low-confidence leaves that were never validated
    - Potentially conflicting information (semantically similar leaves)

    Use --dry-run to preview without deleting.
    """
    from datetime import datetime, timedelta

    from roots.embeddings import cosine_similarity

    kb = get_kb()
    all_entries = kb.index.get_all_leaves()

    # Filter by tree/branch if specified
    if tree or branch:
        filtered = []
        for entry in all_entries:
            parts = Path(entry.file_path).parts
            if tree and (len(parts) < 1 or parts[0] != tree):
                continue
            if branch and (len(parts) < 2 or parts[1] != branch):
                continue
            filtered.append(entry)
        all_entries = filtered

    if not all_entries:
        click.echo("No leaves found matching criteria.")
        return

    issues_found = []
    now = datetime.now()
    stale_threshold = now - timedelta(days=stale_days)

    # Check for stale and low-confidence
    for entry in all_entries:
        issues = []

        # Stale check
        if entry.updated_at < stale_threshold:
            days_old = (now - entry.updated_at).days
            issues.append(f"stale ({days_old} days)")

        # Low confidence check
        if entry.confidence < min_confidence:
            issues.append(f"low confidence ({entry.confidence:.2f})")

        if issues:
            issues_found.append((entry, issues))

    # Detect potential conflicts (semantically similar leaves)
    conflicts = []
    if detect_conflicts and len(all_entries) > 1:
        click.echo("Analyzing for potential conflicts...")
        for i, entry_a in enumerate(all_entries):
            for entry_b in all_entries[i + 1 :]:
                # Skip if same branch (related content expected)
                parts_a = Path(entry_a.file_path).parts
                parts_b = Path(entry_b.file_path).parts
                if len(parts_a) >= 2 and len(parts_b) >= 2:
                    if parts_a[0] == parts_b[0] and parts_a[1] == parts_b[1]:
                        continue

                similarity = cosine_similarity(entry_a.embedding, entry_b.embedding)
                if similarity > 0.85:  # High similarity threshold
                    conflicts.append((entry_a, entry_b, similarity))

    # Report findings
    if not issues_found and not conflicts:
        click.echo("No issues found. Knowledge base looks healthy.")
        return

    if issues_found:
        click.echo(f"\n## Issues Found ({len(issues_found)} leaves)\n")
        click.echo("Review each leaf and decide: update metadata, delete, or keep as-is.\n")
        for entry, issues in issues_found:
            leaf = kb.get_leaf(entry.file_path)
            click.echo(f"### `{entry.file_path}`")
            click.echo(f"  Issues: {', '.join(issues)}")
            click.echo(f"  Tier: {entry.tier}, Confidence: {entry.confidence}")
            click.echo(f"  Updated: {entry.updated_at.strftime('%Y-%m-%d')}")
            if leaf:
                # Show enough content for agent to make a decision
                content = leaf.content[:300] + "..." if len(leaf.content) > 300 else leaf.content
                click.echo("  Content:")
                for line in content.split("\n"):
                    click.echo(f"    > {line}")
            click.echo("")
            click.echo("  **Actions:**")
            click.echo(f"    - Promote: `roots update {entry.file_path} --tier trunk -c 0.8`")
            click.echo(f"    - Delete: `roots delete {entry.file_path}`")
            click.echo("")

    if conflicts:
        click.echo(f"\n## Potential Conflicts ({len(conflicts)} pairs)\n")
        click.echo("These leaves are semantically very similar but in different branches.")
        click.echo("Review to check for contradicting or redundant information.\n")
        for entry_a, entry_b, sim in conflicts[:10]:  # Limit output
            leaf_a = kb.get_leaf(entry_a.file_path)
            leaf_b = kb.get_leaf(entry_b.file_path)
            click.echo(f"### Similarity: {sim:.2f}")
            click.echo("")
            click.echo(f"**Leaf 1:** `{entry_a.file_path}`")
            click.echo(f"  Tier: {entry_a.tier}, Confidence: {entry_a.confidence}")
            if leaf_a:
                # Show full content for agent review, truncate very long ones
                content_a = leaf_a.content[:500] + "..." if len(leaf_a.content) > 500 else leaf_a.content
                for line in content_a.split("\n"):
                    click.echo(f"  > {line}")
            click.echo("")
            click.echo(f"**Leaf 2:** `{entry_b.file_path}`")
            click.echo(f"  Tier: {entry_b.tier}, Confidence: {entry_b.confidence}")
            if leaf_b:
                content_b = leaf_b.content[:500] + "..." if len(leaf_b.content) > 500 else leaf_b.content
                for line in content_b.split("\n"):
                    click.echo(f"  > {line}")
            click.echo("")
            click.echo("**Action:** Review and decide:")
            click.echo(f"  - Delete older/lower-confidence: `roots delete <path>`")
            click.echo(f"  - Merge into one: Edit the keeper, delete the other")
            click.echo(f"  - Keep both if they're actually different concepts")
            click.echo("")
            click.echo("---")
            click.echo("")

    # Summary
    click.echo("\n## Summary")
    click.echo(f"  Total leaves analyzed: {len(all_entries)}")
    click.echo(f"  Stale/low-confidence: {len(issues_found)}")
    click.echo(f"  Potential conflicts: {len(conflicts)}")

    if not dry_run and issues_found:
        click.echo("\n## Actions")
        click.echo("To remove flagged leaves, review each and run:")
        click.echo("  roots delete <path>")
        click.echo("\nOr promote validated leaves:")
        click.echo("  roots update <path> --tier trunk --confidence 0.8")


@roots.command("delete")
@click.argument("file_path")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def delete_cmd(file_path: str, force: bool):
    """Delete a leaf from the knowledge base."""
    kb = get_kb()

    leaf = kb.get_leaf(file_path)
    if not leaf:
        click.echo(f"Not found: {file_path}", err=True)
        raise click.Abort()

    if not force:
        click.echo(f"Delete: {file_path}")
        click.echo(f"  Tier: {leaf.tier}, Confidence: {leaf.confidence}")
        preview = leaf.content[:100] + "..." if len(leaf.content) > 100 else leaf.content
        click.echo(f"  Content: {preview}")
        if not click.confirm("Confirm deletion?"):
            click.echo("Cancelled.")
            return

    kb.delete_leaf(file_path)
    click.echo(f"Deleted: {file_path}")


@roots.command("update")
@click.argument("file_path")
@click.option("--tier", "-t", type=click.Choice(["roots", "trunk", "branches", "leaves"]))
@click.option("--confidence", "-c", type=float, help="Confidence 0-1")
@click.option("--tags", help="Comma-separated tags (replaces existing)")
def update_cmd(file_path: str, tier: str | None, confidence: float | None, tags: str | None):
    """Update a leaf's metadata (tier, confidence, tags)."""
    kb = get_kb()

    leaf = kb.get_leaf(file_path)
    if not leaf:
        click.echo(f"Not found: {file_path}", err=True)
        raise click.Abort()

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    kb.update_leaf(file_path, tier=tier, confidence=confidence, tags=tag_list)

    # Show updated state
    updated = kb.get_leaf(file_path)
    click.echo(f"Updated: {file_path}")
    click.echo(f"  Tier: {updated.tier}")
    click.echo(f"  Confidence: {updated.confidence}")
    click.echo(f"  Tags: {', '.join(updated.tags) if updated.tags else 'none'}")


@roots.command("context")
@click.argument("prompt")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["tags", "lite", "semantic"]),
    default="tags",
    help="Matching mode: tags (keyword), lite (n-gram), semantic (sentence-transformers)",
)
@click.option("--limit", "-n", default=3, help="Max results to show")
@click.option("--threshold", "-t", default=0.5, type=float, help="Min similarity threshold (lite/semantic only)")
def context_cmd(prompt: str, mode: str, limit: int, threshold: float):
    """
    Find relevant knowledge for a prompt.

    Modes:
    - tags: Match prompt words against leaf tags (fast, no ML)
    - lite: N-gram similarity matching (fast, basic similarity)
    - semantic: Sentence-transformers embeddings (slower, best quality)

    Designed for use in Claude Code hooks to auto-inject context.

    Example hook in .claude/settings.local.json:
      "UserPromptSubmit": [{
        "matcher": "",
        "hooks": [{"type": "command", "command": "roots context \"$PROMPT\" --mode tags"}]
      }]
    """
    kb = get_kb()
    all_entries = kb.index.get_all_leaves()

    if not all_entries:
        return  # Silent exit if no knowledge

    results = []

    if mode == "tags":
        # Extract words from prompt (simple tokenization)
        prompt_words = set(
            word.lower().strip(".,!?\"'()[]{}:;")
            for word in prompt.split()
            if len(word) > 2
        )

        # Score each entry by tag overlap
        for entry in all_entries:
            entry_tags = set(t.lower() for t in entry.tags)
            overlap = prompt_words & entry_tags
            if overlap:
                score = len(overlap) / max(len(entry_tags), 1)
                results.append((entry.file_path, list(overlap)))

        results = results[:limit]

        if results:
            click.echo("Related: " + ", ".join(path for path, _ in results))

    elif mode == "lite":
        from roots.embeddings import LiteEmbedder, cosine_similarity

        embedder = LiteEmbedder()
        prompt_embedding = embedder.embed(prompt)

        # Use lower default threshold for lite mode
        effective_threshold = threshold if threshold != 0.5 else 0.3

        # Score each entry
        for entry in all_entries:
            leaf = kb.get_leaf(entry.file_path)
            if leaf:
                leaf_embedding = embedder.embed(leaf.content)
                score = cosine_similarity(prompt_embedding, leaf_embedding)
                if score >= effective_threshold:
                    results.append((entry.file_path, score))

        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:limit]

        if results:
            click.echo("Related: " + ", ".join(path for path, _ in results))

    elif mode == "semantic":
        from roots.embeddings import cosine_similarity

        # Use the KB's embedder (sentence-transformers if available)
        prompt_embedding = kb.embedder.embed(prompt)

        for entry in all_entries:
            score = cosine_similarity(prompt_embedding, entry.embedding)
            if score >= threshold:
                results.append((entry.file_path, score))

        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:limit]

        if results:
            click.echo("Related: " + ", ".join(path for path, _ in results))


if __name__ == "__main__":
    main()

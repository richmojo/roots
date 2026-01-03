use crate::memory::Memories;
use std::fs;
use std::io::{self, Write};
use std::path::Path;

/// Run the init command
pub fn run_init(path: &str, hooks: bool) -> Result<(), String> {
    let path = Path::new(path);
    let roots_path = path.join(".roots");

    if roots_path.exists() {
        return Err(format!(
            ".roots already exists at {}",
            roots_path.display()
        ));
    }

    let mem = Memories::init(path)?;
    println!("Initialized .roots at {}", mem.roots_path().display());

    if hooks {
        install_hooks(path, "none")?;
    }

    Ok(())
}

/// Run the hooks command
pub fn run_hooks(path: &str, remove: bool, context_mode: &str) -> Result<(), String> {
    let path = Path::new(path);

    if remove {
        remove_hooks(path)
    } else {
        install_hooks(path, context_mode)
    }
}

fn install_hooks(path: &Path, context_mode: &str) -> Result<(), String> {
    let claude_dir = path.join(".claude");
    fs::create_dir_all(&claude_dir)
        .map_err(|e| format!("Failed to create .claude directory: {}", e))?;

    let settings_path = claude_dir.join("settings.json");

    // Read existing settings or create new
    let mut settings: serde_json::Value = if settings_path.exists() {
        let content = fs::read_to_string(&settings_path)
            .map_err(|e| format!("Failed to read settings: {}", e))?;
        serde_json::from_str(&content).unwrap_or(serde_json::json!({}))
    } else {
        serde_json::json!({})
    };

    // Add hooks
    let hooks = settings
        .as_object_mut()
        .ok_or("Invalid settings format")?
        .entry("hooks")
        .or_insert(serde_json::json!({}));

    let hooks_obj = hooks.as_object_mut().ok_or("Invalid hooks format")?;

    // SessionStart hook
    hooks_obj.insert(
        "SessionStart".to_string(),
        serde_json::json!([{
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": "roots prime"
            }]
        }]),
    );

    // PreCompact hook
    hooks_obj.insert(
        "PreCompact".to_string(),
        serde_json::json!([{
            "matcher": "",
            "hooks": [{
                "type": "command",
                "command": "roots prime"
            }]
        }]),
    );

    // UserPromptSubmit hook for context on each message
    if context_mode != "none" {
        let cmd = format!("roots context --mode {} \"$CLAUDE_USER_PROMPT\"", context_mode);
        hooks_obj.insert(
            "UserPromptSubmit".to_string(),
            serde_json::json!([{
                "matcher": "",
                "hooks": [{
                    "type": "command",
                    "command": cmd
                }]
            }]),
        );
    }

    // Write settings
    let json = serde_json::to_string_pretty(&settings)
        .map_err(|e| format!("Failed to serialize settings: {}", e))?;
    fs::write(&settings_path, json)
        .map_err(|e| format!("Failed to write settings: {}", e))?;

    println!("Hooks installed:");
    println!("  SessionStart: roots prime");
    println!("  PreCompact:   roots prime");
    if context_mode != "none" {
        println!("  UserPromptSubmit: roots context --mode {}", context_mode);
    }

    Ok(())
}

fn remove_hooks(path: &Path) -> Result<(), String> {
    let settings_path = path.join(".claude").join("settings.json");

    if !settings_path.exists() {
        println!("No hooks configured.");
        return Ok(());
    }

    let content =
        fs::read_to_string(&settings_path).map_err(|e| format!("Failed to read settings: {}", e))?;
    let mut settings: serde_json::Value =
        serde_json::from_str(&content).map_err(|e| format!("Failed to parse settings: {}", e))?;

    if let Some(obj) = settings.as_object_mut() {
        obj.remove("hooks");
    }

    let json = serde_json::to_string_pretty(&settings)
        .map_err(|e| format!("Failed to serialize settings: {}", e))?;
    fs::write(&settings_path, json).map_err(|e| format!("Failed to write settings: {}", e))?;

    println!("Hooks removed.");
    Ok(())
}

/// Run the remember command
pub fn run_remember(content: &str, tags: &str, confidence: f64) -> Result<(), String> {
    let mem = Memories::open()?;

    let tags_vec: Vec<String> = if tags.is_empty() {
        Vec::new()
    } else {
        tags.split(',').map(|s| s.trim().to_string()).collect()
    };

    let id = mem.remember(content, confidence, &tags_vec)?;

    println!("Remembered [{}]", id);
    if !tags_vec.is_empty() {
        println!("  tags: {}", tags_vec.join(", "));
    }

    Ok(())
}

/// Run the recall command
pub fn run_recall(query: Option<&str>, tag: Option<&str>, limit: usize) -> Result<(), String> {
    let mem = Memories::open()?;

    // Check for embedding model mismatch
    if let Some(stored) = mem.check_model_mismatch()? {
        eprintln!("Warning: Embedding model changed ({} -> {})", stored, mem.current_model());
        eprintln!("Run 'roots reindex' to rebuild embeddings for better search quality.\n");
    }

    if let Some(t) = tag {
        // Search by tag
        let memories = mem.recall_by_tag(t, limit)?;

        if memories.is_empty() {
            println!("No memories with tag: {}", t);
            return Ok(());
        }

        println!("Memories tagged '{}':\n", t);
        for m in memories {
            print_memory(&m);
        }
    } else if let Some(q) = query {
        // Semantic search
        let results = mem.recall(q, limit)?;

        if results.is_empty() {
            println!("No matching memories.");
            return Ok(());
        }

        for r in results {
            print_memory_with_score(&r.memory, r.score);
        }
    } else {
        // Show recent
        let memories = mem.list(limit)?;

        if memories.is_empty() {
            println!("No memories yet. Add one with: roots remember \"...\"");
            return Ok(());
        }

        println!("Recent memories:\n");
        for m in memories {
            print_memory(&m);
        }
    }

    Ok(())
}

/// Run the forget command
pub fn run_forget(id: i64, force: bool) -> Result<(), String> {
    let mem = Memories::open()?;

    let memory = mem
        .get(id)?
        .ok_or_else(|| format!("Memory not found: {}", id))?;

    if !force {
        println!("Forget [{}]:", id);
        let preview: String = memory.content.chars().take(100).collect();
        println!("  {}", preview);

        print!("Confirm? [y/N] ");
        io::stdout().flush().unwrap();

        let mut input = String::new();
        io::stdin().read_line(&mut input).unwrap();

        if !input.trim().eq_ignore_ascii_case("y") {
            println!("Cancelled.");
            return Ok(());
        }
    }

    mem.forget(id)?;
    println!("Forgotten [{}]", id);

    Ok(())
}

/// Run the update command
pub fn run_update(id: i64, confidence: Option<f64>, tags: Option<&str>) -> Result<(), String> {
    let mem = Memories::open()?;

    // Check if exists
    mem.get(id)?
        .ok_or_else(|| format!("Memory not found: {}", id))?;

    let tags_vec: Option<Vec<String>> = tags.map(|t| {
        if t.is_empty() {
            Vec::new()
        } else {
            t.split(',').map(|s| s.trim().to_string()).collect()
        }
    });

    mem.update(id, confidence, tags_vec.as_deref())?;

    println!("Updated [{}]", id);
    if let Some(c) = confidence {
        println!("  confidence: {:.2}", c);
    }
    if let Some(t) = tags {
        println!("  tags: {}", t);
    }

    Ok(())
}

/// Run the list command
pub fn run_list(tag: Option<&str>, limit: usize) -> Result<(), String> {
    let mem = Memories::open()?;

    let memories = if let Some(t) = tag {
        mem.recall_by_tag(t, limit)?
    } else {
        mem.list(limit)?
    };

    if memories.is_empty() {
        if tag.is_some() {
            println!("No memories with that tag.");
        } else {
            println!("No memories yet.");
        }
        return Ok(());
    }

    for m in memories {
        print_memory(&m);
    }

    Ok(())
}

/// Run the tags command
pub fn run_tags() -> Result<(), String> {
    let mem = Memories::open()?;
    let tags = mem.tags()?;

    if tags.is_empty() {
        println!("No tags yet.");
        return Ok(());
    }

    println!("Tags:\n");
    for (tag, count) in tags {
        println!("  {:20} ({})", tag, count);
    }

    Ok(())
}

/// Run the stats command
pub fn run_stats() -> Result<(), String> {
    let mem = Memories::open()?;
    let stats = mem.stats()?;

    println!("Memory Statistics");
    println!("=================\n");

    println!("Total memories: {}", stats.total_memories);
    println!("Total tags:     {}", stats.total_tags);
    println!("Avg confidence: {:.2}", stats.avg_confidence);

    if !stats.by_tag.is_empty() {
        println!("\nTop tags:");
        let mut tags: Vec<_> = stats.by_tag.iter().collect();
        tags.sort_by(|a, b| b.1.cmp(a.1));

        for (tag, count) in tags.iter().take(10) {
            println!("  {:20} {}", tag, count);
        }
    }

    Ok(())
}

/// Run the export command
pub fn run_export(format: &str) -> Result<(), String> {
    let mem = Memories::open()?;
    let memories = mem.list(10000)?; // Get all

    match format {
        "json" => {
            let json = serde_json::to_string_pretty(&memories)
                .map_err(|e| format!("Failed to serialize: {}", e))?;
            println!("{}", json);
        }
        "md" => {
            for m in memories {
                println!("## [{}] {}", m.id, m.created_at);
                if !m.tags.is_empty() {
                    println!("*Tags: {}*\n", m.tags.join(", "));
                }
                println!("{}\n", m.content);
                println!("---\n");
            }
        }
        _ => {
            return Err(format!("Unknown format: {}", format));
        }
    }

    Ok(())
}

// Helper to print a memory
fn print_memory(m: &crate::types::Memory) {
    println!("[{}] confidence: {:.2}", m.id, m.confidence);

    if !m.tags.is_empty() {
        println!("    tags: {}", m.tags.join(", "));
    }

    // Truncate content for display
    let preview: String = m.content.chars().take(200).collect();
    let preview = if m.content.len() > 200 {
        format!("{}...", preview)
    } else {
        preview
    };
    let preview = preview.replace('\n', " ");
    println!("    {}\n", preview);
}

fn print_memory_with_score(m: &crate::types::Memory, score: f64) {
    println!("[{}] score: {:.3}, confidence: {:.2}", m.id, score, m.confidence);

    if !m.tags.is_empty() {
        println!("    tags: {}", m.tags.join(", "));
    }

    let preview: String = m.content.chars().take(200).collect();
    let preview = if m.content.len() > 200 {
        format!("{}...", preview)
    } else {
        preview
    };
    let preview = preview.replace('\n', " ");
    println!("    {}\n", preview);
}

/// Run the sync command - export memories to markdown files
pub fn run_sync() -> Result<(), String> {
    let mem = Memories::open()?;
    let memories = mem.list(10000)?;

    if memories.is_empty() {
        println!("No memories to sync.");
        return Ok(());
    }

    // Create memories directory
    let memories_dir = mem.roots_path().join("memories");
    fs::create_dir_all(&memories_dir)
        .map_err(|e| format!("Failed to create memories directory: {}", e))?;

    // Clear existing files
    if let Ok(entries) = fs::read_dir(&memories_dir) {
        for entry in entries.flatten() {
            if entry.path().extension().map_or(false, |e| e == "md") {
                fs::remove_file(entry.path()).ok();
            }
        }
    }

    // Write each memory as a markdown file
    for m in &memories {
        let slug = slugify(&m.content, 40);
        let filename = format!("{:03}_{}.md", m.id, slug);
        let filepath = memories_dir.join(&filename);

        let content = format!(
            "# {}\n\n\
             - **ID:** {}\n\
             - **Confidence:** {:.0}%\n\
             - **Tags:** {}\n\
             - **Created:** {}\n\
             - **Updated:** {}\n\n\
             ---\n\n\
             {}\n",
            first_line(&m.content),
            m.id,
            m.confidence * 100.0,
            if m.tags.is_empty() { "(none)".to_string() } else { m.tags.join(", ") },
            &m.created_at[..10], // Just the date
            &m.updated_at[..10],
            m.content
        );

        fs::write(&filepath, content)
            .map_err(|e| format!("Failed to write {}: {}", filename, e))?;
    }

    println!("Synced {} memories to {}/", memories.len(), memories_dir.display());

    Ok(())
}

/// Create a slug from content for filenames
fn slugify(text: &str, max_len: usize) -> String {
    let first = first_line(text);
    let slug: String = first
        .chars()
        .take(max_len)
        .map(|c| {
            if c.is_ascii_alphanumeric() {
                c.to_ascii_lowercase()
            } else {
                '_'
            }
        })
        .collect();

    // Collapse multiple underscores
    let mut result = String::new();
    let mut last_underscore = false;
    for c in slug.chars() {
        if c == '_' {
            if !last_underscore && !result.is_empty() {
                result.push(c);
                last_underscore = true;
            }
        } else {
            result.push(c);
            last_underscore = false;
        }
    }

    // Trim trailing underscores
    result.trim_end_matches('_').to_string()
}

/// Get the first line of text
fn first_line(text: &str) -> &str {
    text.lines().next().unwrap_or(text).trim()
}

/// Run the reindex command - rebuild all embeddings with current model
pub fn run_reindex() -> Result<(), String> {
    let mem = Memories::open()?;

    let stored = mem.get_stored_model()?;
    let current = mem.current_model();

    println!("Current model: {}", current);
    if let Some(ref s) = stored {
        if s != current {
            println!("Stored model:  {} (mismatch!)", s);
        }
    }

    println!("\nRebuilding embeddings...");
    let count = mem.reindex()?;

    println!("Reindexed {} memories with model: {}", count, current);

    Ok(())
}

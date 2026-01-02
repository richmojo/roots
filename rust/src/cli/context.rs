use crate::memory::Memories;

/// Run the prime command - output context for Claude Code hooks
pub fn run_prime() -> Result<(), String> {
    let mem = match Memories::open() {
        Ok(m) => m,
        Err(_) => {
            // Silent exit if no memory store
            return Ok(());
        }
    };

    let stats = mem.stats()?;

    if stats.total_memories == 0 {
        return Ok(());
    }

    println!("# Memory Context\n");
    println!("Available: {} memories\n", stats.total_memories);

    // Show tags
    let tags = mem.tags()?;
    if !tags.is_empty() {
        println!("Topics: {}\n", tags.iter().map(|(t, _)| t.as_str()).collect::<Vec<_>>().join(", "));
    }

    // Show high-confidence memories
    let top = mem.recall("", 5)?;

    if !top.is_empty() {
        println!("## Key Memories\n");
        for r in top.iter().filter(|r| r.memory.confidence >= 0.7) {
            let preview: String = r.memory.content.chars().take(150).collect();
            println!("- [{}] ({:.0}%) {}", r.memory.id, r.memory.confidence * 100.0, preview.replace('\n', " "));
        }
    }

    println!("\nUse `roots recall <query>` to search memories.");

    Ok(())
}

/// Run the context command - find relevant memories for a prompt
pub fn run_context(prompt: &str, mode: &str, limit: usize, threshold: f64) -> Result<(), String> {
    let mem = match Memories::open() {
        Ok(m) => m,
        Err(_) => {
            // Silent exit if no memory store
            return Ok(());
        }
    };

    let results = match mode {
        "tags" => {
            // Extract words from prompt and match against tags
            let words: Vec<&str> = prompt.split_whitespace().collect();
            let tags = mem.tags()?;
            let matching_tags: Vec<String> = tags
                .iter()
                .filter(|(tag, _)| words.iter().any(|w| w.to_lowercase().contains(&tag.to_lowercase())))
                .map(|(tag, _)| tag.clone())
                .collect();

            if matching_tags.is_empty() {
                Vec::new()
            } else {
                // Get memories with matching tags
                let mut all = Vec::new();
                for tag in &matching_tags {
                    all.extend(mem.recall_by_tag(tag, limit)?);
                }
                // Convert to SearchResult with score 1.0
                all.into_iter()
                    .take(limit)
                    .map(|m| crate::types::SearchResult { memory: m, score: 1.0 })
                    .collect()
            }
        }
        "lite" | "semantic" => {
            // Both use embedding search (lite embedder or server)
            mem.recall(prompt, limit * 2)?
        }
        _ => Vec::new(),
    };

    let filtered: Vec<_> = results
        .into_iter()
        .filter(|r| r.score >= threshold)
        .take(limit)
        .collect();

    if filtered.is_empty() {
        return Ok(());
    }

    println!("# Relevant Memories\n");

    for r in filtered {
        println!("## [{}] (relevance: {:.0}%)", r.memory.id, r.score * 100.0);

        if !r.memory.tags.is_empty() {
            println!("*Tags: {}*\n", r.memory.tags.join(", "));
        }

        // Output content (truncated)
        let content: String = r.memory.content.chars().take(500).collect();
        println!("{}", content);

        if r.memory.content.len() > 500 {
            println!("...\n");
        } else {
            println!();
        }
    }

    Ok(())
}

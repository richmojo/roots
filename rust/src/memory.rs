use crate::config::{find_roots_path, RootsConfig};
use crate::embeddings::{cosine_similarity, get_embedder, Embedder};
use crate::index::MemoryStore;
use crate::types::{Memory, MemoryStats, SearchResult};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

/// The main memory interface
pub struct Memories {
    roots_path: PathBuf,
    store: MemoryStore,
    embedder: Box<dyn Embedder>,
}

impl Memories {
    /// Open an existing memory store
    pub fn open() -> Result<Self, String> {
        let roots_path =
            find_roots_path().ok_or("No .roots directory found. Run 'roots init' first.")?;
        Self::open_at(roots_path)
    }

    /// Open a memory store at a specific path
    pub fn open_at(roots_path: PathBuf) -> Result<Self, String> {
        if !roots_path.exists() {
            return Err(format!("Path does not exist: {}", roots_path.display()));
        }

        let db_path = roots_path.join("memory.db");
        let store =
            MemoryStore::open(&db_path).map_err(|e| format!("Failed to open store: {}", e))?;

        let config = RootsConfig::new(roots_path.clone());
        let (model_name, model_type) = config.get_resolved_model();
        let embedder = get_embedder(Some(&model_name), &model_type, true);

        Ok(Self {
            roots_path,
            store,
            embedder,
        })
    }

    /// Initialize a new memory store
    pub fn init(path: &Path) -> Result<Self, String> {
        let roots_path = path.join(".roots");
        fs::create_dir_all(&roots_path)
            .map_err(|e| format!("Failed to create .roots directory: {}", e))?;

        Self::open_at(roots_path)
    }

    /// Get the roots path
    pub fn roots_path(&self) -> &Path {
        &self.roots_path
    }

    // =========================================================================
    // Core operations
    // =========================================================================

    /// Remember something new
    pub fn remember(
        &self,
        content: &str,
        confidence: f64,
        tags: &[String],
    ) -> Result<i64, String> {
        let embedding = self
            .embedder
            .embed(content)
            .map_err(|e| format!("Failed to embed content: {}", e))?;

        self.store
            .add(content, confidence, &embedding, tags)
            .map_err(|e| format!("Failed to add memory: {}", e))
    }

    /// Recall memories by semantic search
    pub fn recall(&self, query: &str, limit: usize) -> Result<Vec<SearchResult>, String> {
        let query_embedding = self
            .embedder
            .embed(query)
            .map_err(|e| format!("Failed to embed query: {}", e))?;

        let all = self
            .store
            .get_all_with_embeddings()
            .map_err(|e| format!("Failed to get memories: {}", e))?;

        let mut results: Vec<SearchResult> = all
            .into_iter()
            .map(|(memory, embedding)| {
                let score = cosine_similarity(&query_embedding, &embedding);
                SearchResult { memory, score }
            })
            .collect();

        // Sort by score descending
        results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));

        Ok(results.into_iter().take(limit).collect())
    }

    /// Recall memories by tag
    pub fn recall_by_tag(&self, tag: &str, limit: usize) -> Result<Vec<Memory>, String> {
        self.store
            .get_by_tag(tag, limit)
            .map_err(|e| format!("Failed to get memories: {}", e))
    }

    /// Full-text search
    #[allow(dead_code)]
    pub fn search_text(&self, query: &str, limit: usize) -> Result<Vec<Memory>, String> {
        self.store
            .search_fts(query, limit)
            .map_err(|e| format!("Failed to search: {}", e))
    }

    /// Get a specific memory
    pub fn get(&self, id: i64) -> Result<Option<Memory>, String> {
        self.store
            .get(id)
            .map_err(|e| format!("Failed to get memory: {}", e))
    }

    /// List recent memories
    pub fn list(&self, limit: usize) -> Result<Vec<Memory>, String> {
        self.store
            .list(limit)
            .map_err(|e| format!("Failed to list memories: {}", e))
    }

    /// Update a memory
    pub fn update(
        &self,
        id: i64,
        confidence: Option<f64>,
        tags: Option<&[String]>,
    ) -> Result<(), String> {
        self.store
            .update(id, confidence, tags)
            .map_err(|e| format!("Failed to update memory: {}", e))?;
        Ok(())
    }

    /// Forget a memory
    pub fn forget(&self, id: i64) -> Result<bool, String> {
        self.store
            .delete(id)
            .map_err(|e| format!("Failed to delete memory: {}", e))
    }

    // =========================================================================
    // Stats and metadata
    // =========================================================================

    /// Get statistics
    pub fn stats(&self) -> Result<MemoryStats, String> {
        let count = self
            .store
            .count()
            .map_err(|e| format!("Failed to count: {}", e))?;

        let tags = self
            .store
            .get_all_tags()
            .map_err(|e| format!("Failed to get tags: {}", e))?;

        let by_tag: HashMap<String, usize> = tags.into_iter().collect();

        // Calculate average confidence
        let memories = self
            .store
            .list(1000)
            .map_err(|e| format!("Failed to list: {}", e))?;

        let avg_confidence = if memories.is_empty() {
            0.0
        } else {
            memories.iter().map(|m| m.confidence).sum::<f64>() / memories.len() as f64
        };

        Ok(MemoryStats {
            total_memories: count,
            total_tags: by_tag.len(),
            by_tag,
            avg_confidence,
        })
    }

    /// Get all tags with counts
    pub fn tags(&self) -> Result<Vec<(String, usize)>, String> {
        self.store
            .get_all_tags()
            .map_err(|e| format!("Failed to get tags: {}", e))
    }
}

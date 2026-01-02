use serde::{Deserialize, Serialize};

/// A memory entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Memory {
    pub id: i64,
    pub content: String,
    pub confidence: f64,
    pub tags: Vec<String>,
    pub created_at: String,
    pub updated_at: String,
    pub last_accessed_at: Option<String>,
    pub access_count: i64,
}

/// Search result with similarity score
#[derive(Debug, Clone)]
pub struct SearchResult {
    pub memory: Memory,
    pub score: f64,
}

/// Statistics about the memory store
#[derive(Debug, Clone, Default)]
pub struct MemoryStats {
    pub total_memories: usize,
    pub total_tags: usize,
    pub by_tag: std::collections::HashMap<String, usize>,
    pub avg_confidence: f64,
}

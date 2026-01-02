use crate::types::Memory;
use rusqlite::{params, Connection, Result};
use std::path::Path;

const SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    embedding BLOB,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed_at TEXT,
    access_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tags (
    memory_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (memory_id, tag),
    FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

-- Full-text search (will error if already exists, that's ok)
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    content=memories,
    content_rowid=id
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
"#;

/// Memory store backed by SQLite
pub struct MemoryStore {
    conn: Connection,
}

impl MemoryStore {
    /// Open or create the memory database
    pub fn open(db_path: &Path) -> Result<Self> {
        let conn = Connection::open(db_path)?;
        conn.execute_batch(SCHEMA)?;
        Ok(Self { conn })
    }

    /// Open an in-memory database (for testing)
    #[allow(dead_code)]
    pub fn in_memory() -> Result<Self> {
        let conn = Connection::open_in_memory()?;
        conn.execute_batch(SCHEMA)?;
        Ok(Self { conn })
    }

    // -------------------------------------------------------------------------
    // Embedding serialization
    // -------------------------------------------------------------------------

    fn serialize_embedding(embedding: &[f32]) -> Vec<u8> {
        embedding.iter().flat_map(|f| f.to_le_bytes()).collect()
    }

    fn deserialize_embedding(data: &[u8]) -> Vec<f32> {
        data.chunks_exact(4)
            .map(|chunk| f32::from_le_bytes([chunk[0], chunk[1], chunk[2], chunk[3]]))
            .collect()
    }

    // -------------------------------------------------------------------------
    // Memory operations
    // -------------------------------------------------------------------------

    /// Add a new memory, returns the ID
    pub fn add(&self, content: &str, confidence: f64, embedding: &[f32], tags: &[String]) -> Result<i64> {
        let now = chrono::Utc::now().to_rfc3339();
        let embedding_bytes = Self::serialize_embedding(embedding);

        self.conn.execute(
            "INSERT INTO memories (content, confidence, embedding, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5)",
            params![content, confidence, embedding_bytes, now, now],
        )?;

        let id = self.conn.last_insert_rowid();

        // Add tags
        for tag in tags {
            self.conn.execute(
                "INSERT OR IGNORE INTO tags (memory_id, tag) VALUES (?1, ?2)",
                params![id, tag.to_lowercase()],
            )?;
        }

        Ok(id)
    }

    /// Get a memory by ID
    pub fn get(&self, id: i64) -> Result<Option<Memory>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, content, confidence, created_at, updated_at, last_accessed_at, access_count FROM memories WHERE id = ?1"
        )?;

        let mut rows = stmt.query(params![id])?;

        if let Some(row) = rows.next()? {
            let memory_id: i64 = row.get(0)?;
            let tags = self.get_tags(memory_id)?;

            Ok(Some(Memory {
                id: memory_id,
                content: row.get(1)?,
                confidence: row.get(2)?,
                tags,
                created_at: row.get(3)?,
                updated_at: row.get(4)?,
                last_accessed_at: row.get(5)?,
                access_count: row.get(6)?,
            }))
        } else {
            Ok(None)
        }
    }

    /// Get all memories with their embeddings (for vector search)
    pub fn get_all_with_embeddings(&self) -> Result<Vec<(Memory, Vec<f32>)>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, content, confidence, embedding, created_at, updated_at, last_accessed_at, access_count FROM memories"
        )?;

        let mut results = Vec::new();
        let mut rows = stmt.query([])?;

        while let Some(row) = rows.next()? {
            let memory_id: i64 = row.get(0)?;
            let embedding_bytes: Vec<u8> = row.get(3)?;
            let tags = self.get_tags(memory_id)?;

            let memory = Memory {
                id: memory_id,
                content: row.get(1)?,
                confidence: row.get(2)?,
                tags,
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
                last_accessed_at: row.get(6)?,
                access_count: row.get(7)?,
            };

            results.push((memory, Self::deserialize_embedding(&embedding_bytes)));
        }

        Ok(results)
    }

    /// Full-text search
    #[allow(dead_code)]
    pub fn search_fts(&self, query: &str, limit: usize) -> Result<Vec<Memory>> {
        let mut stmt = self.conn.prepare(
            "SELECT m.id, m.content, m.confidence, m.created_at, m.updated_at, m.last_accessed_at, m.access_count
             FROM memories m
             JOIN memories_fts fts ON m.id = fts.rowid
             WHERE memories_fts MATCH ?1
             LIMIT ?2"
        )?;

        let mut results = Vec::new();
        let mut rows = stmt.query(params![query, limit as i64])?;

        while let Some(row) = rows.next()? {
            let memory_id: i64 = row.get(0)?;
            let tags = self.get_tags(memory_id)?;

            results.push(Memory {
                id: memory_id,
                content: row.get(1)?,
                confidence: row.get(2)?,
                tags,
                created_at: row.get(3)?,
                updated_at: row.get(4)?,
                last_accessed_at: row.get(5)?,
                access_count: row.get(6)?,
            });
        }

        Ok(results)
    }

    /// Get memories by tag
    pub fn get_by_tag(&self, tag: &str, limit: usize) -> Result<Vec<Memory>> {
        let mut stmt = self.conn.prepare(
            "SELECT m.id, m.content, m.confidence, m.created_at, m.updated_at, m.last_accessed_at, m.access_count
             FROM memories m
             JOIN tags t ON m.id = t.memory_id
             WHERE t.tag = ?1
             ORDER BY m.updated_at DESC
             LIMIT ?2"
        )?;

        let mut results = Vec::new();
        let mut rows = stmt.query(params![tag.to_lowercase(), limit as i64])?;

        while let Some(row) = rows.next()? {
            let memory_id: i64 = row.get(0)?;
            let tags = self.get_tags(memory_id)?;

            results.push(Memory {
                id: memory_id,
                content: row.get(1)?,
                confidence: row.get(2)?,
                tags,
                created_at: row.get(3)?,
                updated_at: row.get(4)?,
                last_accessed_at: row.get(5)?,
                access_count: row.get(6)?,
            });
        }

        Ok(results)
    }

    /// List recent memories
    pub fn list(&self, limit: usize) -> Result<Vec<Memory>> {
        let mut stmt = self.conn.prepare(
            "SELECT id, content, confidence, created_at, updated_at, last_accessed_at, access_count
             FROM memories
             ORDER BY updated_at DESC
             LIMIT ?1"
        )?;

        let mut results = Vec::new();
        let mut rows = stmt.query(params![limit as i64])?;

        while let Some(row) = rows.next()? {
            let memory_id: i64 = row.get(0)?;
            let tags = self.get_tags(memory_id)?;

            results.push(Memory {
                id: memory_id,
                content: row.get(1)?,
                confidence: row.get(2)?,
                tags,
                created_at: row.get(3)?,
                updated_at: row.get(4)?,
                last_accessed_at: row.get(5)?,
                access_count: row.get(6)?,
            });
        }

        Ok(results)
    }

    /// Update a memory
    pub fn update(&self, id: i64, confidence: Option<f64>, tags: Option<&[String]>) -> Result<bool> {
        let now = chrono::Utc::now().to_rfc3339();

        if let Some(conf) = confidence {
            self.conn.execute(
                "UPDATE memories SET confidence = ?1, updated_at = ?2 WHERE id = ?3",
                params![conf, now, id],
            )?;
        }

        if let Some(new_tags) = tags {
            // Replace all tags
            self.conn.execute("DELETE FROM tags WHERE memory_id = ?1", params![id])?;
            for tag in new_tags {
                self.conn.execute(
                    "INSERT OR IGNORE INTO tags (memory_id, tag) VALUES (?1, ?2)",
                    params![id, tag.to_lowercase()],
                )?;
            }
            self.conn.execute(
                "UPDATE memories SET updated_at = ?1 WHERE id = ?2",
                params![now, id],
            )?;
        }

        Ok(true)
    }

    /// Record an access to a memory
    #[allow(dead_code)]
    pub fn record_access(&self, id: i64) -> Result<()> {
        let now = chrono::Utc::now().to_rfc3339();
        self.conn.execute(
            "UPDATE memories SET last_accessed_at = ?1, access_count = access_count + 1 WHERE id = ?2",
            params![now, id],
        )?;
        Ok(())
    }

    /// Delete a memory
    pub fn delete(&self, id: i64) -> Result<bool> {
        // Tags will be deleted via ON DELETE CASCADE
        let count = self.conn.execute("DELETE FROM memories WHERE id = ?1", params![id])?;
        Ok(count > 0)
    }

    /// Get count of memories
    pub fn count(&self) -> Result<usize> {
        let count: i64 = self.conn.query_row("SELECT COUNT(*) FROM memories", [], |row| row.get(0))?;
        Ok(count as usize)
    }

    /// Get all unique tags
    pub fn get_all_tags(&self) -> Result<Vec<(String, usize)>> {
        let mut stmt = self.conn.prepare(
            "SELECT tag, COUNT(*) as count FROM tags GROUP BY tag ORDER BY count DESC"
        )?;

        let mut results = Vec::new();
        let mut rows = stmt.query([])?;

        while let Some(row) = rows.next()? {
            results.push((row.get(0)?, row.get::<_, i64>(1)? as usize));
        }

        Ok(results)
    }

    // Helper to get tags for a memory
    fn get_tags(&self, memory_id: i64) -> Result<Vec<String>> {
        let mut stmt = self.conn.prepare("SELECT tag FROM tags WHERE memory_id = ?1")?;
        let mut tags = Vec::new();
        let mut rows = stmt.query(params![memory_id])?;

        while let Some(row) = rows.next()? {
            tags.push(row.get(0)?);
        }

        Ok(tags)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_and_get() {
        let store = MemoryStore::in_memory().unwrap();

        let id = store.add(
            "Test memory content",
            0.8,
            &[1.0, 2.0, 3.0],
            &["test".to_string(), "example".to_string()],
        ).unwrap();

        let memory = store.get(id).unwrap().unwrap();
        assert_eq!(memory.content, "Test memory content");
        assert_eq!(memory.confidence, 0.8);
        assert_eq!(memory.tags, vec!["test", "example"]);
    }

    #[test]
    fn test_get_by_tag() {
        let store = MemoryStore::in_memory().unwrap();

        store.add("Memory 1", 0.5, &[1.0], &["rust".to_string()]).unwrap();
        store.add("Memory 2", 0.5, &[1.0], &["rust".to_string(), "cli".to_string()]).unwrap();
        store.add("Memory 3", 0.5, &[1.0], &["python".to_string()]).unwrap();

        let rust_memories = store.get_by_tag("rust", 10).unwrap();
        assert_eq!(rust_memories.len(), 2);
    }

    #[test]
    fn test_delete() {
        let store = MemoryStore::in_memory().unwrap();

        let id = store.add("To delete", 0.5, &[1.0], &["test".to_string()]).unwrap();
        assert!(store.get(id).unwrap().is_some());

        store.delete(id).unwrap();
        assert!(store.get(id).unwrap().is_none());
    }
}

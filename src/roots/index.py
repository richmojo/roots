"""
index - SQLite index for embeddings and cross-links.

Stores vector embeddings for semantic search and
cross-references between knowledge files.
"""

import json
import sqlite3
import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class IndexEntry:
    """A leaf's index entry with embedding."""

    file_path: str
    content_hash: str
    embedding: list[float]
    tier: str
    confidence: float
    tags: list[str]
    updated_at: datetime


@dataclass
class Link:
    """A cross-reference between two leaves."""

    from_path: str
    to_path: str
    relation: str  # supports, contradicts, related_to


class RootsIndex:
    """SQLite index for embeddings and links."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leaves (
                    file_path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    tier TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    tags TEXT DEFAULT '[]',
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    from_path TEXT NOT NULL,
                    to_path TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (from_path, to_path, relation)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_leaves_tier ON leaves(tier)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_links_from ON links(from_path)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_links_to ON links(to_path)
            """)

    def upsert_leaf(self, entry: IndexEntry) -> None:
        """Insert or update a leaf's index entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO leaves (file_path, content_hash, embedding, tier, confidence, tags, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    embedding = excluded.embedding,
                    tier = excluded.tier,
                    confidence = excluded.confidence,
                    tags = excluded.tags,
                    updated_at = excluded.updated_at
                """,
                (
                    entry.file_path,
                    entry.content_hash,
                    self._serialize_embedding(entry.embedding),
                    entry.tier,
                    entry.confidence,
                    json.dumps(entry.tags),
                    entry.updated_at.isoformat(),
                ),
            )

    def get_leaf(self, file_path: str) -> IndexEntry | None:
        """Get a leaf's index entry."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM leaves WHERE file_path = ?", (file_path,)
            ).fetchone()

            if not row:
                return None

            return IndexEntry(
                file_path=row[0],
                content_hash=row[1],
                embedding=self._deserialize_embedding(row[2]),
                tier=row[3],
                confidence=row[4],
                tags=json.loads(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
            )

    def get_all_leaves(self) -> list[IndexEntry]:
        """Get all indexed leaves."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM leaves").fetchall()

            return [
                IndexEntry(
                    file_path=row[0],
                    content_hash=row[1],
                    embedding=self._deserialize_embedding(row[2]),
                    tier=row[3],
                    confidence=row[4],
                    tags=json.loads(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                )
                for row in rows
            ]

    def delete_leaf(self, file_path: str) -> None:
        """Remove a leaf from the index."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM leaves WHERE file_path = ?", (file_path,))
            conn.execute(
                "DELETE FROM links WHERE from_path = ? OR to_path = ?",
                (file_path, file_path),
            )

    def add_link(self, from_path: str, to_path: str, relation: str) -> None:
        """Add a cross-reference between two leaves."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO links (from_path, to_path, relation, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (from_path, to_path, relation, datetime.now().isoformat()),
            )

    def get_links_from(self, file_path: str) -> list[Link]:
        """Get all links originating from a leaf."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT from_path, to_path, relation FROM links WHERE from_path = ?",
                (file_path,),
            ).fetchall()

            return [Link(from_path=r[0], to_path=r[1], relation=r[2]) for r in rows]

    def get_links_to(self, file_path: str) -> list[Link]:
        """Get all links pointing to a leaf."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT from_path, to_path, relation FROM links WHERE to_path = ?",
                (file_path,),
            ).fetchall()

            return [Link(from_path=r[0], to_path=r[1], relation=r[2]) for r in rows]

    def remove_link(self, from_path: str, to_path: str, relation: str) -> None:
        """Remove a specific link."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM links WHERE from_path = ? AND to_path = ? AND relation = ?",
                (from_path, to_path, relation),
            )

    def _serialize_embedding(self, embedding: list[float]) -> bytes:
        """Serialize embedding to bytes for storage."""
        return struct.pack(f"{len(embedding)}f", *embedding)

    def _deserialize_embedding(self, data: bytes) -> list[float]:
        """Deserialize embedding from bytes."""
        n_floats = len(data) // 4
        return list(struct.unpack(f"{n_floats}f", data))

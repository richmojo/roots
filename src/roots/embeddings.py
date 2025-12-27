"""
embeddings - Vector embedding generation for semantic search.

Supports two modes:
- Full: Uses sentence-transformers for high-quality local embeddings
- Lite: Falls back to TF-IDF style vectors when sentence-transformers unavailable
"""

import hashlib
from typing import Protocol

import numpy as np


class EmbedderProtocol(Protocol):
    """Protocol for embedding implementations."""

    def embed(self, text: str) -> list[float]: ...
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """Generate embeddings using sentence-transformers (high quality, ~500MB model)."""

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()


class LiteEmbedder:
    """
    Lightweight embedder using character n-gram hashing.

    Not as good as sentence-transformers, but:
    - Zero dependencies beyond numpy
    - Instant startup
    - Good enough for small knowledge bases
    """

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        """Generate embedding using character n-gram hashing."""
        text = text.lower().strip()
        vector = np.zeros(self.dim, dtype=np.float32)

        # Character trigrams
        for i in range(len(text) - 2):
            trigram = text[i : i + 3]
            h = int(hashlib.md5(trigram.encode()).hexdigest(), 16)
            idx = h % self.dim
            vector[idx] += 1.0

        # Word unigrams
        for word in text.split():
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            idx = h % self.dim
            vector[idx] += 2.0  # Weight words more than trigrams

        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed(t) for t in texts]


def get_embedder(use_sentence_transformers: bool = True) -> EmbedderProtocol:
    """
    Get the best available embedder.

    Args:
        use_sentence_transformers: If True, try to use sentence-transformers.
            Falls back to LiteEmbedder if not available.

    Returns:
        An embedder instance.
    """
    if use_sentence_transformers:
        try:
            # Check if sentence-transformers is available
            import sentence_transformers  # noqa: F401

            return SentenceTransformerEmbedder()
        except ImportError:
            pass

    return LiteEmbedder()


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

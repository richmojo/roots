"""
roots - Embedding server for AI agent memory.

The CLI is now written in Rust. This Python package provides
the embedding server for semantic search.

Usage:
    # Start embedding server (called by Rust CLI)
    roots server start
    roots server stop
    roots server status
"""

from roots.config import SUGGESTED_MODELS, get_server_model, resolve_model
from roots.embeddings import (
    EmbedderProtocol,
    LiteEmbedder,
    SentenceTransformerEmbedder,
    ServerEmbedder,
    get_embedder,
)
from roots.server import EmbeddingClient, EmbeddingServer, start_server, stop_server

__version__ = "0.2.0"
__all__ = [
    # Server
    "EmbeddingServer",
    "EmbeddingClient",
    "start_server",
    "stop_server",
    # Embeddings
    "EmbedderProtocol",
    "LiteEmbedder",
    "SentenceTransformerEmbedder",
    "ServerEmbedder",
    "get_embedder",
    # Config
    "SUGGESTED_MODELS",
    "get_server_model",
    "resolve_model",
]

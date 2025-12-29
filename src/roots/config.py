"""
config - Configuration management for roots.

Handles persistent settings stored in .roots/_config.yaml.
Also supports global config in ~/.config/roots/config.yaml for the embedding server.
"""

from pathlib import Path
from typing import Any

import yaml

# Global config location (used by embedding server)
GLOBAL_CONFIG_DIR = Path.home() / ".config" / "roots"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

# Suggested embedding models (user can use any model, these are just suggestions)
SUGGESTED_MODELS = [
    # Lightweight / Fast
    {
        "alias": "lite",
        "name": "lite",
        "type": "lite",
        "size": "0MB",
        "description": "N-gram hashing - zero dependencies, instant startup",
    },
    {
        "alias": "minilm",
        "name": "sentence-transformers/all-MiniLM-L6-v2",
        "type": "sentence-transformers",
        "size": "~90MB",
        "description": "Fast general-purpose embeddings",
    },
    {
        "alias": "bge-small",
        "name": "BAAI/bge-small-en-v1.5",
        "type": "sentence-transformers",
        "size": "~130MB",
        "description": "Small BGE model, good quality",
    },
    # Medium
    {
        "alias": "bge-base",
        "name": "BAAI/bge-base-en-v1.5",
        "type": "sentence-transformers",
        "size": "~400MB",
        "description": "Default. Good balance of quality and speed",
    },
    {
        "alias": "qwen-0.6b",
        "name": "Qwen/Qwen3-Embedding-0.6B",
        "type": "sentence-transformers",
        "size": "~1.2GB",
        "description": "Qwen 0.6B - efficient and capable",
    },
    # Large / High Quality
    {
        "alias": "bge-large",
        "name": "BAAI/bge-large-en-v1.5",
        "type": "sentence-transformers",
        "size": "~1.2GB",
        "description": "Large BGE model, higher quality",
    },
    {
        "alias": "qwen-4b",
        "name": "Qwen/Qwen3-Embedding-4B",
        "type": "sentence-transformers",
        "size": "~8GB",
        "description": "Qwen 4B - high quality, needs GPU",
    },
    {
        "alias": "qwen-8b",
        "name": "Qwen/Qwen3-Embedding-8B",
        "type": "sentence-transformers",
        "size": "~16GB",
        "description": "Qwen 8B - best quality, needs GPU",
    },
]

# Build lookup by alias
MODEL_ALIASES = {m["alias"]: m for m in SUGGESTED_MODELS}

DEFAULT_MODEL = "bge-base"


def resolve_model(model_input: str) -> tuple[str, str]:
    """
    Resolve a model input to (model_name, model_type).

    Args:
        model_input: Either an alias (e.g., "qwen-4b") or a full model name
                    (e.g., "Qwen/Qwen3-Embedding-4B")

    Returns:
        Tuple of (model_name, model_type)
    """
    # Check if it's an alias
    if model_input in MODEL_ALIASES:
        info = MODEL_ALIASES[model_input]
        return info["name"], info["type"]

    # Special case for lite
    if model_input == "lite":
        return "lite", "lite"

    # Assume it's a direct model name (sentence-transformers compatible)
    return model_input, "sentence-transformers"


# -----------------------------------------------------------------------------
# Global config (for embedding server)
# -----------------------------------------------------------------------------


def get_global_config() -> dict[str, Any]:
    """Get global config (used by embedding server)."""
    if GLOBAL_CONFIG_FILE.exists():
        return yaml.safe_load(GLOBAL_CONFIG_FILE.read_text()) or {}
    return {}


def set_global_config(key: str, value: Any) -> None:
    """Set a global config value."""
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = get_global_config()
    config[key] = value
    GLOBAL_CONFIG_FILE.write_text(yaml.dump(config, default_flow_style=False))


def get_server_model() -> tuple[str, str]:
    """Get the model configured for the embedding server."""
    config = get_global_config()
    model = config.get("server_model", DEFAULT_MODEL)
    return resolve_model(model)


# -----------------------------------------------------------------------------
# Per-project config
# -----------------------------------------------------------------------------


class RootsConfig:
    """Configuration manager for a .roots directory."""

    def __init__(self, roots_path: Path):
        self.roots_path = roots_path
        self.config_file = roots_path / "_config.yaml"
        self._config: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load config from file."""
        if self.config_file.exists():
            self._config = yaml.safe_load(self.config_file.read_text()) or {}
        else:
            self._config = {}

    def _save(self) -> None:
        """Save config to file."""
        self.roots_path.mkdir(parents=True, exist_ok=True)
        self.config_file.write_text(yaml.dump(self._config, default_flow_style=False))

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value."""
        self._config[key] = value
        self._save()

    @property
    def embedding_model(self) -> str:
        """Get the configured embedding model (alias or full name)."""
        return self.get("embedding_model", DEFAULT_MODEL)

    @embedding_model.setter
    def embedding_model(self, value: str) -> None:
        """Set the embedding model (alias or full name)."""
        self.set("embedding_model", value)

    def get_resolved_model(self) -> tuple[str, str]:
        """Get the resolved (model_name, model_type) for the current config."""
        return resolve_model(self.embedding_model)

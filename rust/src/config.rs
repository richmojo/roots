use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

/// Model information
#[derive(Debug, Clone)]
pub struct ModelInfo {
    pub alias: &'static str,
    pub name: &'static str,
    pub model_type: &'static str,
    pub size: &'static str,
    pub description: &'static str,
}

/// Suggested embedding models
pub static SUGGESTED_MODELS: &[ModelInfo] = &[
    // Lightweight / Fast
    ModelInfo {
        alias: "lite",
        name: "lite",
        model_type: "lite",
        size: "0MB",
        description: "N-gram hashing - zero dependencies, instant startup",
    },
    ModelInfo {
        alias: "minilm",
        name: "sentence-transformers/all-MiniLM-L6-v2",
        model_type: "sentence-transformers",
        size: "~90MB",
        description: "Fast general-purpose embeddings",
    },
    ModelInfo {
        alias: "bge-small",
        name: "BAAI/bge-small-en-v1.5",
        model_type: "sentence-transformers",
        size: "~130MB",
        description: "Small BGE model, good quality",
    },
    // Medium
    ModelInfo {
        alias: "bge-base",
        name: "BAAI/bge-base-en-v1.5",
        model_type: "sentence-transformers",
        size: "~400MB",
        description: "Default. Good balance of quality and speed",
    },
    ModelInfo {
        alias: "qwen-0.6b",
        name: "Qwen/Qwen3-Embedding-0.6B",
        model_type: "sentence-transformers",
        size: "~1.2GB",
        description: "Qwen 0.6B - efficient and capable",
    },
    // Large / High Quality
    ModelInfo {
        alias: "bge-large",
        name: "BAAI/bge-large-en-v1.5",
        model_type: "sentence-transformers",
        size: "~1.2GB",
        description: "Large BGE model, higher quality",
    },
    ModelInfo {
        alias: "qwen-4b",
        name: "Qwen/Qwen3-Embedding-4B",
        model_type: "sentence-transformers",
        size: "~8GB",
        description: "Qwen 4B - high quality, needs GPU",
    },
    ModelInfo {
        alias: "qwen-8b",
        name: "Qwen/Qwen3-Embedding-8B",
        model_type: "sentence-transformers",
        size: "~16GB",
        description: "Qwen 8B - best quality, needs GPU",
    },
];

pub const DEFAULT_MODEL: &str = "bge-base";

/// Get model aliases lookup
pub fn model_aliases() -> HashMap<&'static str, &'static ModelInfo> {
    SUGGESTED_MODELS.iter().map(|m| (m.alias, m)).collect()
}

/// Resolve a model input to (model_name, model_type)
pub fn resolve_model(model_input: &str) -> (String, String) {
    let aliases = model_aliases();

    // Check if it's an alias
    if let Some(info) = aliases.get(model_input) {
        return (info.name.to_string(), info.model_type.to_string());
    }

    // Special case for lite
    if model_input == "lite" {
        return ("lite".to_string(), "lite".to_string());
    }

    // Assume it's a direct model name (sentence-transformers compatible)
    (model_input.to_string(), "sentence-transformers".to_string())
}

// -----------------------------------------------------------------------------
// Global config (for embedding server)
// -----------------------------------------------------------------------------

fn global_config_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".config")
        .join("roots")
}

fn global_config_file() -> PathBuf {
    global_config_dir().join("config.yaml")
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct GlobalConfig {
    #[serde(default)]
    server_model: Option<String>,
}

/// Get global config
pub fn get_global_config() -> HashMap<String, String> {
    let path = global_config_file();
    if path.exists() {
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(config) = serde_yaml::from_str::<HashMap<String, String>>(&content) {
                return config;
            }
        }
    }
    HashMap::new()
}

/// Set a global config value
pub fn set_global_config(key: &str, value: &str) -> std::io::Result<()> {
    let dir = global_config_dir();
    fs::create_dir_all(&dir)?;

    let mut config = get_global_config();
    config.insert(key.to_string(), value.to_string());

    let content = serde_yaml::to_string(&config).unwrap_or_default();
    fs::write(global_config_file(), content)
}

/// Get the model configured for the embedding server
pub fn get_server_model() -> (String, String) {
    let config = get_global_config();
    let model = config
        .get("server_model")
        .cloned()
        .unwrap_or_else(|| DEFAULT_MODEL.to_string());
    resolve_model(&model)
}

// -----------------------------------------------------------------------------
// Per-project config
// -----------------------------------------------------------------------------

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
struct ProjectConfigFile {
    #[serde(default)]
    embedding_model: Option<String>,
}

/// Configuration manager for a .roots directory
pub struct RootsConfig {
    roots_path: PathBuf,
    config_file: PathBuf,
    config: HashMap<String, serde_yaml::Value>,
}

impl RootsConfig {
    pub fn new(roots_path: PathBuf) -> Self {
        let config_file = roots_path.join("_config.yaml");
        let mut instance = Self {
            roots_path,
            config_file,
            config: HashMap::new(),
        };
        instance.load();
        instance
    }

    fn load(&mut self) {
        if self.config_file.exists() {
            if let Ok(content) = fs::read_to_string(&self.config_file) {
                if let Ok(config) =
                    serde_yaml::from_str::<HashMap<String, serde_yaml::Value>>(&content)
                {
                    self.config = config;
                }
            }
        }
    }

    fn save(&self) -> std::io::Result<()> {
        fs::create_dir_all(&self.roots_path)?;
        let content = serde_yaml::to_string(&self.config).unwrap_or_default();
        fs::write(&self.config_file, content)
    }

    pub fn get(&self, key: &str) -> Option<String> {
        self.config.get(key).and_then(|v| match v {
            serde_yaml::Value::String(s) => Some(s.clone()),
            serde_yaml::Value::Number(n) => Some(n.to_string()),
            serde_yaml::Value::Bool(b) => Some(b.to_string()),
            _ => None,
        })
    }

    pub fn set(&mut self, key: &str, value: &str) -> std::io::Result<()> {
        self.config
            .insert(key.to_string(), serde_yaml::Value::String(value.to_string()));
        self.save()
    }

    pub fn embedding_model(&self) -> String {
        self.get("embedding_model")
            .unwrap_or_else(|| DEFAULT_MODEL.to_string())
    }

    pub fn set_embedding_model(&mut self, value: &str) -> std::io::Result<()> {
        self.set("embedding_model", value)
    }

    pub fn get_resolved_model(&self) -> (String, String) {
        resolve_model(&self.embedding_model())
    }
}

/// Find the .roots directory, searching upward from current directory
pub fn find_roots_path() -> Option<PathBuf> {
    let mut current = std::env::current_dir().ok()?;

    loop {
        let roots = current.join(".roots");
        if roots.is_dir() {
            return Some(roots);
        }

        if !current.pop() {
            break;
        }
    }

    // Check ROOTS_PATH environment variable
    if let Ok(path) = std::env::var("ROOTS_PATH") {
        let roots = PathBuf::from(path);
        if roots.is_dir() {
            return Some(roots);
        }
    }

    None
}

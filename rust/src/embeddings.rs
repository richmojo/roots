use md5::{Digest, Md5};
use serde::{Deserialize, Serialize};
use std::io::{Read, Write};
use std::os::unix::net::UnixStream;
use std::path::Path;

/// Embedding dimension for lite embedder
const LITE_DIM: usize = 384;

/// Socket path for embedding server
const SOCKET_PATH: &str = "/tmp/roots-embedder.sock";

/// Trait for embedding implementations
pub trait Embedder {
    fn embed(&self, text: &str) -> Result<Vec<f32>, String>;
    fn embed_batch(&self, texts: &[&str]) -> Result<Vec<Vec<f32>>, String>;
}

// =============================================================================
// LiteEmbedder - N-gram hashing (pure Rust, zero deps)
// =============================================================================

/// Lightweight embedder using character n-gram hashing
pub struct LiteEmbedder {
    dim: usize,
}

impl Default for LiteEmbedder {
    fn default() -> Self {
        Self::new()
    }
}

impl LiteEmbedder {
    pub fn new() -> Self {
        Self { dim: LITE_DIM }
    }

    pub fn with_dim(dim: usize) -> Self {
        Self { dim }
    }
}

impl Embedder for LiteEmbedder {
    fn embed(&self, text: &str) -> Result<Vec<f32>, String> {
        let text = text.to_lowercase();
        let text = text.trim();
        let mut vector = vec![0.0f32; self.dim];

        // Character trigrams
        let chars: Vec<char> = text.chars().collect();
        for i in 0..chars.len().saturating_sub(2) {
            let trigram: String = chars[i..i + 3].iter().collect();
            let hash = md5_hash(&trigram);
            let idx = (hash % self.dim as u128) as usize;
            vector[idx] += 1.0;
        }

        // Word unigrams (weighted more than trigrams)
        for word in text.split_whitespace() {
            let hash = md5_hash(word);
            let idx = (hash % self.dim as u128) as usize;
            vector[idx] += 2.0;
        }

        // Normalize
        let norm: f32 = vector.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 0.0 {
            for v in &mut vector {
                *v /= norm;
            }
        }

        Ok(vector)
    }

    fn embed_batch(&self, texts: &[&str]) -> Result<Vec<Vec<f32>>, String> {
        texts.iter().map(|t| self.embed(t)).collect()
    }
}

/// Compute MD5 hash and return as u128
fn md5_hash(text: &str) -> u128 {
    let mut hasher = Md5::new();
    hasher.update(text.as_bytes());
    let result = hasher.finalize();
    u128::from_be_bytes(result.into())
}

// =============================================================================
// ServerEmbedder - Unix socket client for Python embedding server
// =============================================================================

#[derive(Serialize)]
struct EmbedRequest<'a> {
    cmd: &'a str,
    text: &'a str,
}

#[derive(Serialize)]
struct EmbedBatchRequest<'a> {
    cmd: &'a str,
    texts: &'a [&'a str],
}

#[derive(Serialize)]
struct PingRequest<'a> {
    cmd: &'a str,
}

#[derive(Deserialize)]
struct EmbedResponse {
    ok: bool,
    embedding: Option<Vec<f32>>,
    error: Option<String>,
}

#[derive(Deserialize)]
struct EmbedBatchResponse {
    ok: bool,
    embeddings: Option<Vec<Vec<f32>>>,
    error: Option<String>,
}

#[derive(Deserialize)]
struct PingResponse {
    ok: bool,
    model: Option<String>,
    error: Option<String>,
}

/// Embedder that uses the Python embedding server daemon
pub struct ServerEmbedder;

impl ServerEmbedder {
    pub fn new() -> Self {
        Self
    }

    /// Check if the server is running
    pub fn is_running() -> bool {
        if !Path::new(SOCKET_PATH).exists() {
            return false;
        }

        match Self::ping() {
            Ok(_) => true,
            Err(_) => false,
        }
    }

    /// Ping the server and get the model name
    pub fn ping() -> Result<String, String> {
        let request = PingRequest { cmd: "ping" };
        let response: PingResponse = send_request(&request)?;

        if response.ok {
            Ok(response.model.unwrap_or_default())
        } else {
            Err(response.error.unwrap_or_else(|| "Unknown error".to_string()))
        }
    }

    /// Get the model the server is using
    pub fn get_model() -> Result<String, String> {
        Self::ping()
    }
}

impl Default for ServerEmbedder {
    fn default() -> Self {
        Self::new()
    }
}

impl Embedder for ServerEmbedder {
    fn embed(&self, text: &str) -> Result<Vec<f32>, String> {
        let request = EmbedRequest { cmd: "embed", text };
        let response: EmbedResponse = send_request(&request)?;

        if response.ok {
            response
                .embedding
                .ok_or_else(|| "No embedding in response".to_string())
        } else {
            Err(response.error.unwrap_or_else(|| "Unknown error".to_string()))
        }
    }

    fn embed_batch(&self, texts: &[&str]) -> Result<Vec<Vec<f32>>, String> {
        let request = EmbedBatchRequest {
            cmd: "embed_batch",
            texts,
        };
        let response: EmbedBatchResponse = send_request(&request)?;

        if response.ok {
            response
                .embeddings
                .ok_or_else(|| "No embeddings in response".to_string())
        } else {
            Err(response.error.unwrap_or_else(|| "Unknown error".to_string()))
        }
    }
}

/// Send a request to the embedding server and parse the response
fn send_request<R, T>(request: &R) -> Result<T, String>
where
    R: Serialize,
    T: for<'de> Deserialize<'de>,
{
    // Connect to socket
    let mut stream =
        UnixStream::connect(SOCKET_PATH).map_err(|e| format!("Failed to connect to server: {}", e))?;

    // Set timeout
    stream
        .set_read_timeout(Some(std::time::Duration::from_secs(60)))
        .map_err(|e| format!("Failed to set timeout: {}", e))?;

    // Send request
    let json = serde_json::to_string(request).map_err(|e| format!("Failed to serialize: {}", e))?;
    stream
        .write_all(json.as_bytes())
        .map_err(|e| format!("Failed to send: {}", e))?;

    // Shutdown write side to signal end of request
    stream
        .shutdown(std::net::Shutdown::Write)
        .map_err(|e| format!("Failed to shutdown write: {}", e))?;

    // Read response (up to 1MB)
    let mut buffer = Vec::new();
    stream
        .take(1024 * 1024)
        .read_to_end(&mut buffer)
        .map_err(|e| format!("Failed to read response: {}", e))?;

    // Parse response
    serde_json::from_slice(&buffer).map_err(|e| format!("Failed to parse response: {}", e))
}

// =============================================================================
// Cosine similarity
// =============================================================================

/// Compute cosine similarity between two vectors
pub fn cosine_similarity(vec_a: &[f32], vec_b: &[f32]) -> f64 {
    if vec_a.len() != vec_b.len() {
        return 0.0;
    }

    let dot: f32 = vec_a.iter().zip(vec_b.iter()).map(|(a, b)| a * b).sum();
    let norm_a: f32 = vec_a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = vec_b.iter().map(|x| x * x).sum::<f32>().sqrt();

    if norm_a == 0.0 || norm_b == 0.0 {
        0.0
    } else {
        (dot / (norm_a * norm_b)) as f64
    }
}

// =============================================================================
// Embedder factory
// =============================================================================

/// Get an embedder for the specified model
pub fn get_embedder(model_name: Option<&str>, model_type: &str, use_server: bool) -> Box<dyn Embedder> {
    // Lite mode
    if model_type == "lite" || model_name == Some("lite") {
        return Box::new(LiteEmbedder::new());
    }

    // Try server if requested
    if use_server {
        if ServerEmbedder::is_running() {
            if let Ok(server_model) = ServerEmbedder::get_model() {
                let requested_model = model_name.unwrap_or("BAAI/bge-base-en-v1.5");
                if server_model == requested_model {
                    return Box::new(ServerEmbedder::new());
                }
            }
        }
    }

    // Fall back to lite if server not available
    // In Rust we can't load sentence-transformers, so we always fall back to lite
    // or server. The user should start the Python server for ML embeddings.
    eprintln!(
        "Warning: Embedding server not running. Using lite embedder.\n\
         For better quality, start the server: roots server start"
    );
    Box::new(LiteEmbedder::new())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lite_embedder() {
        let embedder = LiteEmbedder::new();
        let embedding = embedder.embed("hello world").unwrap();

        assert_eq!(embedding.len(), LITE_DIM);

        // Check normalization (should be unit vector)
        let norm: f32 = embedding.iter().map(|x| x * x).sum::<f32>().sqrt();
        assert!((norm - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_cosine_similarity() {
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![1.0, 0.0, 0.0];
        assert!((cosine_similarity(&a, &b) - 1.0).abs() < 0.001);

        let c = vec![0.0, 1.0, 0.0];
        assert!(cosine_similarity(&a, &c).abs() < 0.001);
    }

    #[test]
    fn test_similar_texts_have_higher_similarity() {
        let embedder = LiteEmbedder::new();

        let a = embedder.embed("the quick brown fox").unwrap();
        let b = embedder.embed("the quick brown dog").unwrap();
        let c = embedder.embed("completely different text").unwrap();

        let sim_ab = cosine_similarity(&a, &b);
        let sim_ac = cosine_similarity(&a, &c);

        // Similar texts should have higher similarity
        assert!(sim_ab > sim_ac);
    }
}

use crate::config::{get_global_config, get_server_model, resolve_model, set_global_config, SUGGESTED_MODELS};
use crate::embeddings::ServerEmbedder;
use std::fs;
use std::process::Command;

/// Run server start command
pub fn run_start(foreground: bool) -> Result<(), String> {
    if ServerEmbedder::is_running() {
        let model = ServerEmbedder::get_model().unwrap_or_else(|_| "unknown".to_string());
        println!("Server already running with model: {}", model);
        return Ok(());
    }

    let (model_name, model_type) = get_server_model();

    if model_type == "lite" {
        return Err(
            "Lite mode doesn't need a server.\n\
             To use ML embeddings, set a model first:\n\
             roots server model bge-base"
                .to_string(),
        );
    }

    println!("Starting embedding server with model: {}", model_name);

    // Check if sentence-transformers is installed, install if needed
    let check = Command::new("uv")
        .args(["run", "python", "-c", "import sentence_transformers"])
        .output();

    if check.is_err() || !check.unwrap().status.success() {
        println!("Installing sentence-transformers (first time only)...");
        let install = Command::new("uv")
            .args(["add", "sentence-transformers"])
            .status()
            .map_err(|e| format!("Failed to install sentence-transformers: {}", e))?;

        if !install.success() {
            return Err("Failed to install sentence-transformers".to_string());
        }
    }

    // Use uv run to handle Python environment
    let server_cmd = if foreground {
        format!("uv run python -m roots.server --model '{}'", model_name)
    } else {
        format!(
            "nohup uv run python -m roots.server --model '{}' > /tmp/roots-server.log 2>&1 &",
            model_name
        )
    };

    let status = Command::new("sh")
        .arg("-c")
        .arg(&server_cmd)
        .status()
        .map_err(|e| format!("Failed to start server: {}", e))?;

    if foreground {
        // Foreground mode - command returned
        if !status.success() {
            return Err("Server exited with error".to_string());
        }
    } else {
        // Background mode - poll until server is ready (model loading can take a while)
        println!("Waiting for model to load...");
        let mut ready = false;
        for i in 0..60 {
            std::thread::sleep(std::time::Duration::from_secs(1));
            if ServerEmbedder::is_running() {
                ready = true;
                break;
            }
            if i > 0 && i % 10 == 0 {
                println!("Still loading... ({} seconds)", i);
            }
        }

        if ready {
            println!("Server started successfully.");
        } else {
            return Err(
                "Server failed to start. Check /tmp/roots-server.log for details.".to_string(),
            );
        }
    }

    Ok(())
}

/// Run server stop command
pub fn run_stop() -> Result<(), String> {
    if !ServerEmbedder::is_running() {
        println!("Server not running.");
        return Ok(());
    }

    // Send stop command
    use std::io::Write;
    use std::os::unix::net::UnixStream;

    let socket_path = "/tmp/roots-embedder.sock";

    let mut stream = UnixStream::connect(socket_path)
        .map_err(|e| format!("Failed to connect to server: {}", e))?;

    let request = serde_json::json!({"cmd": "stop"});
    let json = serde_json::to_string(&request).unwrap();

    stream.write_all(json.as_bytes()).ok();
    stream.shutdown(std::net::Shutdown::Write).ok();

    println!("Server stopped.");
    Ok(())
}

/// Run server status command
pub fn run_status() -> Result<(), String> {
    if ServerEmbedder::is_running() {
        let model = ServerEmbedder::get_model().unwrap_or_else(|_| "unknown".to_string());
        println!("Server: running");
        println!("Model:  {}", model);
        println!("Socket: /tmp/roots-embedder.sock");
    } else {
        println!("Server: not running");

        let (model_name, _) = get_server_model();
        println!("Configured model: {}", model_name);
        println!("\nStart with: roots server start");
    }

    Ok(())
}

/// Run server restart command
pub fn run_restart() -> Result<(), String> {
    if ServerEmbedder::is_running() {
        run_stop()?;
        std::thread::sleep(std::time::Duration::from_secs(1));
    }

    run_start(false)
}

/// Run server model command
pub fn run_model(model: Option<&str>, list: bool) -> Result<(), String> {
    if list {
        print_server_models()?;
        return Ok(());
    }

    match model {
        Some(m) => {
            let (model_name, model_type) = resolve_model(m);

            if model_type == "lite" {
                return Err(
                    "Lite mode doesn't use the server.\n\
                     Use: roots config model lite"
                        .to_string(),
                );
            }

            set_global_config("server_model", m)
                .map_err(|e| format!("Failed to save config: {}", e))?;

            println!("Server model set to: {}", model_name);

            if ServerEmbedder::is_running() {
                println!("\nRestart the server to use the new model:");
                println!("  roots server restart");
            }
        }
        None => {
            let (model_name, model_type) = get_server_model();

            // Find alias
            let alias = SUGGESTED_MODELS
                .iter()
                .find(|m| m.name == model_name)
                .map(|m| m.alias);

            println!("Current server model:");
            if let Some(a) = alias {
                println!("  {} ({})", a, model_name);
            } else {
                println!("  {}", model_name);
            }
            println!("  type: {}", model_type);

            if ServerEmbedder::is_running() {
                println!("\nServer is running with this model.");
            }
        }
    }

    Ok(())
}

fn print_server_models() -> Result<(), String> {
    let config = get_global_config();
    let current = config.get("server_model").cloned().unwrap_or_default();

    println!("Available server models:\n");
    println!(
        "{:2} {:12} {:10} {}",
        "", "Alias", "Size", "Description"
    );
    println!("{}", "-".repeat(60));

    for model in SUGGESTED_MODELS {
        // Skip lite - it doesn't use the server
        if model.alias == "lite" {
            continue;
        }

        let marker = if model.alias == current || model.name == current {
            " *"
        } else {
            "  "
        };

        println!(
            "{} {:12} {:10} {}",
            marker, model.alias, model.size, model.description
        );
    }

    println!("\n* = currently configured");
    println!("\nSet model with: roots server model <alias>");

    Ok(())
}

/// Run server install command (systemd)
pub fn run_install() -> Result<(), String> {
    let home = dirs::home_dir().ok_or("Could not find home directory")?;
    let systemd_dir = home.join(".config/systemd/user");

    fs::create_dir_all(&systemd_dir)
        .map_err(|e| format!("Failed to create systemd directory: {}", e))?;

    let (model_name, _) = get_server_model();

    let service_content = format!(
        r#"[Unit]
Description=Roots Embedding Server
After=network.target

[Service]
Type=simple
ExecStart=/bin/sh -c "uv run python -m roots.server --model '{}'"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"#,
        model_name
    );

    let service_path = systemd_dir.join("roots-embedder.service");
    fs::write(&service_path, service_content)
        .map_err(|e| format!("Failed to write service file: {}", e))?;

    // Enable and start the service
    Command::new("systemctl")
        .args(["--user", "daemon-reload"])
        .status()
        .map_err(|e| format!("Failed to reload systemd: {}", e))?;

    Command::new("systemctl")
        .args(["--user", "enable", "roots-embedder"])
        .status()
        .map_err(|e| format!("Failed to enable service: {}", e))?;

    Command::new("systemctl")
        .args(["--user", "start", "roots-embedder"])
        .status()
        .map_err(|e| format!("Failed to start service: {}", e))?;

    println!("Installed systemd user service: roots-embedder");
    println!("\nThe server will now start automatically on login.");
    println!("\nManage with:");
    println!("  systemctl --user status roots-embedder");
    println!("  systemctl --user restart roots-embedder");
    println!("  systemctl --user stop roots-embedder");

    Ok(())
}

/// Run server uninstall command
pub fn run_uninstall() -> Result<(), String> {
    // Stop and disable the service
    Command::new("systemctl")
        .args(["--user", "stop", "roots-embedder"])
        .status()
        .ok();

    Command::new("systemctl")
        .args(["--user", "disable", "roots-embedder"])
        .status()
        .ok();

    // Remove the service file
    let home = dirs::home_dir().ok_or("Could not find home directory")?;
    let service_path = home.join(".config/systemd/user/roots-embedder.service");

    if service_path.exists() {
        fs::remove_file(&service_path)
            .map_err(|e| format!("Failed to remove service file: {}", e))?;
    }

    Command::new("systemctl")
        .args(["--user", "daemon-reload"])
        .status()
        .ok();

    println!("Removed systemd user service: roots-embedder");

    Ok(())
}

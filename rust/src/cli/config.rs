use crate::config::{
    find_roots_path, resolve_model, RootsConfig, DEFAULT_MODEL, SUGGESTED_MODELS,
};

/// Run the config command
pub fn run_config(
    key: Option<&str>,
    value: Option<&str>,
    list_models: bool,
) -> Result<(), String> {
    if list_models {
        print_models()?;
        return Ok(());
    }

    let roots_path = find_roots_path().ok_or("No .roots directory found. Run 'roots init' first.")?;
    let mut config = RootsConfig::new(roots_path);

    match (key, value) {
        (None, None) => {
            // Show current config
            println!("Current configuration:\n");

            let model = config.embedding_model();
            let (model_name, model_type) = resolve_model(&model);

            // Find if this is an alias
            let alias = SUGGESTED_MODELS
                .iter()
                .find(|m| m.name == model_name || m.alias == model)
                .map(|m| m.alias)
                .unwrap_or(&model);

            println!("  model: {}", alias);
            if alias != &model_name {
                println!("    -> {}", model_name);
            }
            println!("    type: {}", model_type);
        }
        (Some(k), None) => {
            // Show specific key
            if k == "model" || k == "embedding_model" {
                let model = config.embedding_model();
                let (model_name, model_type) = resolve_model(&model);
                println!("model: {}", model);
                println!("  -> {}", model_name);
                println!("  type: {}", model_type);
            } else if let Some(v) = config.get(k) {
                println!("{}: {}", k, v);
            } else {
                println!("{}: (not set)", k);
            }
        }
        (Some(k), Some(v)) => {
            // Set key=value
            if k == "model" || k == "embedding_model" {
                let (model_name, model_type) = resolve_model(v);

                if model_type == "lite" {
                    println!("Setting model to lite (n-gram hashing)");
                } else {
                    println!("Setting model to: {}", model_name);
                    println!("  type: {}", model_type);
                    println!("\nNote: You may need to restart the embedding server:");
                    println!("  roots server restart");
                }

                config.set_embedding_model(v).map_err(|e| format!("Failed to save: {}", e))?;
            } else {
                config.set(k, v).map_err(|e| format!("Failed to save: {}", e))?;
            }
            println!("Set {} = {}", k, v);
        }
        (None, Some(_)) => {
            return Err("Key required when setting a value".to_string());
        }
    }

    Ok(())
}

fn print_models() -> Result<(), String> {
    let roots_path = find_roots_path();
    let current = roots_path
        .as_ref()
        .map(|p| RootsConfig::new(p.clone()).embedding_model())
        .unwrap_or_else(|| DEFAULT_MODEL.to_string());

    println!("Available embedding models:\n");
    println!(
        "{:2} {:12} {:10} {}",
        "", "Alias", "Size", "Description"
    );
    println!("{}", "-".repeat(60));

    for model in SUGGESTED_MODELS {
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
    println!("\nSet model with: roots config model <alias>");

    Ok(())
}

use clap::{Parser, Subcommand};

mod cli;
mod config;
mod embeddings;
mod index;
mod memory;
mod types;

#[derive(Parser)]
#[command(name = "roots")]
#[command(version)]
#[command(about = "Persistent memory for AI agents")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Initialize a .roots directory
    Init {
        /// Directory to initialize .roots in
        #[arg(short, long, default_value = ".")]
        path: String,

        /// Also install Claude Code hooks
        #[arg(long)]
        hooks: bool,
    },

    /// Install Claude Code hooks
    Hooks {
        /// Directory containing .roots
        #[arg(short, long, default_value = ".")]
        path: String,

        /// Remove hooks instead of installing
        #[arg(long)]
        remove: bool,

        /// Add context hook on user message
        #[arg(long)]
        on_message: bool,
    },

    /// Remember something
    Remember {
        /// Content to remember
        content: String,

        /// Comma-separated tags
        #[arg(short, long, default_value = "")]
        tags: String,

        /// Confidence (0-1)
        #[arg(short, long, default_value = "0.5")]
        confidence: f64,
    },

    /// Recall memories by search
    Recall {
        /// Search query (omit for recent)
        query: Option<String>,

        /// Search by tag instead
        #[arg(short, long)]
        tag: Option<String>,

        /// Maximum results
        #[arg(short = 'n', long, default_value = "5")]
        limit: usize,
    },

    /// Forget a memory
    Forget {
        /// Memory ID to forget
        id: i64,

        /// Skip confirmation
        #[arg(short, long)]
        force: bool,
    },

    /// Update a memory
    Update {
        /// Memory ID
        id: i64,

        /// New confidence
        #[arg(short, long)]
        confidence: Option<f64>,

        /// New tags (comma-separated, replaces existing)
        #[arg(short, long)]
        tags: Option<String>,
    },

    /// List recent memories
    List {
        /// Filter by tag
        #[arg(short, long)]
        tag: Option<String>,

        /// Maximum results
        #[arg(short = 'n', long, default_value = "10")]
        limit: usize,
    },

    /// List all tags
    Tags,

    /// Show statistics
    Stats,

    /// Export memories to stdout
    Export {
        /// Output format
        #[arg(short, long, default_value = "json", value_parser = ["json", "md"])]
        format: String,
    },

    /// Sync memories to markdown files for browsing
    Sync,

    /// Output context for Claude Code hooks
    Prime,

    /// Find relevant memories for a prompt
    Context {
        /// The prompt to find context for
        prompt: String,

        /// Maximum results
        #[arg(short = 'n', long, default_value = "3")]
        limit: usize,

        /// Minimum similarity threshold
        #[arg(short, long, default_value = "0.3")]
        threshold: f64,
    },

    /// View or set configuration
    Config {
        /// Config key
        key: Option<String>,

        /// Config value
        value: Option<String>,

        /// List available models
        #[arg(long)]
        list_models: bool,
    },

    /// Manage embedding server
    #[command(subcommand)]
    Server(ServerCommands),
}

#[derive(Subcommand)]
enum ServerCommands {
    /// Start the embedding server
    Start {
        /// Run in foreground
        #[arg(short, long)]
        foreground: bool,
    },

    /// Stop the embedding server
    Stop,

    /// Check server status
    Status,

    /// Restart the server
    Restart,

    /// View or set server model
    Model {
        /// Model name or alias
        model: Option<String>,

        /// List available models
        #[arg(short, long)]
        list: bool,
    },

    /// Install systemd user service
    Install,

    /// Remove systemd user service
    Uninstall,
}

fn main() {
    let cli = Cli::parse();

    let result = match cli.command {
        Commands::Init { path, hooks } => cli::memory::run_init(&path, hooks),
        Commands::Hooks { path, remove, on_message } => cli::memory::run_hooks(&path, remove, on_message),
        Commands::Remember {
            content,
            tags,
            confidence,
        } => cli::memory::run_remember(&content, &tags, confidence),
        Commands::Recall { query, tag, limit } => {
            cli::memory::run_recall(query.as_deref(), tag.as_deref(), limit)
        }
        Commands::Forget { id, force } => cli::memory::run_forget(id, force),
        Commands::Update {
            id,
            confidence,
            tags,
        } => cli::memory::run_update(id, confidence, tags.as_deref()),
        Commands::List { tag, limit } => cli::memory::run_list(tag.as_deref(), limit),
        Commands::Tags => cli::memory::run_tags(),
        Commands::Stats => cli::memory::run_stats(),
        Commands::Export { format } => cli::memory::run_export(&format),
        Commands::Sync => cli::memory::run_sync(),
        Commands::Prime => cli::context::run_prime(),
        Commands::Context {
            prompt,
            limit,
            threshold,
        } => cli::context::run_context(&prompt, limit, threshold),
        Commands::Config {
            key,
            value,
            list_models,
        } => cli::config::run_config(key.as_deref(), value.as_deref(), list_models),
        Commands::Server(cmd) => match cmd {
            ServerCommands::Start { foreground } => cli::server::run_start(foreground),
            ServerCommands::Stop => cli::server::run_stop(),
            ServerCommands::Status => cli::server::run_status(),
            ServerCommands::Restart => cli::server::run_restart(),
            ServerCommands::Model { model, list } => cli::server::run_model(model.as_deref(), list),
            ServerCommands::Install => cli::server::run_install(),
            ServerCommands::Uninstall => cli::server::run_uninstall(),
        },
    };

    if let Err(e) = result {
        eprintln!("Error: {}", e);
        std::process::exit(1);
    }
}

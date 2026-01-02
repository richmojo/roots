#!/bin/bash
set -e

# Roots installer
# Usage: curl -fsSL https://raw.githubusercontent.com/richmojo/roots/main/scripts/install.sh | bash

REPO="https://github.com/richmojo/roots.git"
INSTALL_DIR="${ROOTS_INSTALL_DIR:-$HOME/.local/bin}"

info() { echo -e "\033[0;34m[info]\033[0m $1"; }
success() { echo -e "\033[0;32m[ok]\033[0m $1"; }
error() { echo -e "\033[0;31m[error]\033[0m $1" >&2; exit 1; }

# Check for required tools
check_deps() {
    if ! command -v cargo &> /dev/null; then
        info "Cargo not found. Installing rustup..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
    fi

    if ! command -v git &> /dev/null; then
        error "Git is required. Install it first."
    fi
}

# Build and install
install_roots() {
    local tmpdir=$(mktemp -d)
    trap "rm -rf $tmpdir" EXIT

    info "Cloning roots..."
    git clone --depth 1 "$REPO" "$tmpdir" 2>/dev/null

    info "Building (this may take a minute)..."
    cd "$tmpdir/rust"
    cargo build --release --quiet

    # Install binary
    mkdir -p "$INSTALL_DIR"
    cp target/release/roots "$INSTALL_DIR/"

    success "Installed roots to $INSTALL_DIR/roots"
}

# Check PATH
check_path() {
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        echo ""
        info "Add to your shell profile:"
        echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
    fi
}

# Optional: install Python embedding server
install_embeddings() {
    echo ""
    read -p "Install embedding server for better search? (y/N) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v uv &> /dev/null; then
            info "Installing Python embedding server..."
            uv tool install "git+$REPO[embeddings]" --quiet
            success "Embedding server installed"
        elif command -v pip &> /dev/null; then
            info "Installing Python embedding server..."
            pip install "git+$REPO[embeddings]" --quiet
            success "Embedding server installed"
        else
            info "Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"
            info "Then run: uv tool install 'git+$REPO[embeddings]'"
        fi
    fi
}

main() {
    echo ""
    echo "  roots - persistent memory for AI agents"
    echo ""

    check_deps
    install_roots
    check_path

    # Only prompt if interactive
    if [ -t 0 ]; then
        install_embeddings
    fi

    echo ""
    success "Done! Run 'roots init' to get started."
    echo ""
    echo "  Quick start:"
    echo "    roots init                    # Initialize in current directory"
    echo "    roots remember \"something\"    # Save a memory"
    echo "    roots recall \"query\"          # Search memories"
    echo "    roots hooks                   # Install Claude Code hooks"
    echo ""
}

main

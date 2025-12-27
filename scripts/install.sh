#!/bin/bash
# Install roots from GitHub using uv
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/richmojo/roots/main/scripts/install.sh | bash

set -e

echo "Installing roots..."

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Error: 'uv' not found."
    echo ""
    echo "Install uv first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install from GitHub
uv tool install git+https://github.com/richmojo/roots.git

echo ""
echo "Installed! Run 'roots --help' to get started."
echo ""
echo "Quick start:"
echo "  roots init --hooks    # Initialize with Claude Code hooks"
echo "  roots tree <name>     # Create a knowledge tree"

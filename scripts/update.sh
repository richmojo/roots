#!/bin/bash
# Update roots to the latest version from GitHub
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/richmojo/roots/main/scripts/update.sh | bash
#   # or
#   roots self-update

set -e

echo "Updating roots..."

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Error: 'uv' not found."
    exit 1
fi

# Reinstall from GitHub (--force to overwrite)
uv tool install git+https://github.com/richmojo/roots.git --force

echo ""
echo "Updated! Current version:"
roots --version

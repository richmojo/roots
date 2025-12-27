#!/bin/bash
# Install roots-kb globally using pipx or uv
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/richmojo/roots/main/scripts/install.sh | bash
#
# Or manually:
#   pipx install roots-kb
#   uv tool install roots-kb

set -e

echo "Installing roots-kb..."

# Check for uv first (preferred)
if command -v uv &> /dev/null; then
    echo "Using uv..."
    uv tool install roots-kb
    echo ""
    echo "✓ Installed! Run 'roots --help' to get started."
    exit 0
fi

# Fall back to pipx
if command -v pipx &> /dev/null; then
    echo "Using pipx..."
    pipx install roots-kb
    echo ""
    echo "✓ Installed! Run 'roots --help' to get started."
    exit 0
fi

# Neither found
echo "Error: Neither 'uv' nor 'pipx' found."
echo ""
echo "Install one of:"
echo "  - uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
echo "  - pipx: python -m pip install --user pipx"
echo ""
echo "Then run this script again, or install manually:"
echo "  uv tool install roots-kb"
echo "  pipx install roots-kb"
exit 1

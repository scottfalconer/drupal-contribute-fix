#!/usr/bin/env bash
# Setup ddev cspell command for Drupal contrib development
# Based on: https://github.com/jameswilson/ddev-drupal-contrib/tree/cspell

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in a DDEV project
if [ ! -f .ddev/config.yaml ]; then
    error "Not in a DDEV project directory. Please run this from a DDEV project root."
    exit 1
fi

# Create .ddev/commands/web directory if it doesn't exist
mkdir -p .ddev/commands/web

info "Installing ddev cspell command..."

# Download the cspell command from the custom fork
curl -fsSL https://raw.githubusercontent.com/jameswilson/ddev-drupal-contrib/refs/heads/cspell/commands/web/cspell \
    -o .ddev/commands/web/cspell

# Make it executable
chmod +x .ddev/commands/web/cspell

info "Installing cspell dependencies (Drupal core Node packages)..."

# Check if Drupal core exists
if [ ! -d "web/core" ]; then
    error "Drupal core not found at web/core. Please ensure Drupal is installed."
    exit 1
fi

# Install Node dependencies for cspell
# This supports both npm and Yarn 4+ PnP
ddev exec "cd web/core && yarn cache clean && yarn install"

info "cspell setup complete!"
info "You can now run: ddev cspell"

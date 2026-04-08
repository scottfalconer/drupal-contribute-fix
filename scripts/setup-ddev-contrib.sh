#!/usr/bin/env bash
# Setup ddev-drupal-contrib for local Drupal contrib development
# Based on: https://github.com/ddev/ddev-drupal-contrib

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

info "Setting up ddev-drupal-contrib..."

# Install ddev-drupal-contrib
info "Installing ddev-drupal-contrib addon..."
ddev get ddev/ddev-drupal-contrib

# Restart DDEV to apply changes
info "Restarting DDEV..."
ddev restart

info "ddev-drupal-contrib setup complete!"
info "Available commands:"
echo "  - ddev poser (Composer)"
echo "  - ddev phpstan"
echo "  - ddev phpcs"
echo "  - ddev phpcbf"
echo "  - ddev phpunit"
echo ""
warn "Note: cspell is not included by default. Run setup-cspell.sh to add it."

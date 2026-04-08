#!/usr/bin/env bash
# Setup drupalorg-cli for Drupal.org issue and MR management
# Based on: https://github.com/mglaman/drupalorg-cli

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

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if PHP is available
if ! command -v php &> /dev/null; then
    error "PHP is not installed or not in PATH. drupalorg-cli requires PHP 8.1+."
    exit 1
fi

# Check PHP version
PHP_VERSION=$(php -r 'echo PHP_VERSION;')
PHP_MAJOR=$(php -r 'echo PHP_MAJOR_VERSION;')
PHP_MINOR=$(php -r 'echo PHP_MINOR_VERSION;')

if [ "$PHP_MAJOR" -lt 8 ] || ([ "$PHP_MAJOR" -eq 8 ] && [ "$PHP_MINOR" -lt 1 ]); then
    error "drupalorg-cli requires PHP 8.1+. Current version: $PHP_VERSION"
    exit 1
fi

info "PHP version: $PHP_VERSION ✓"

# Check if Composer is available
if ! command -v composer &> /dev/null; then
    error "Composer is not installed or not in PATH. Install from https://getcomposer.org"
    exit 1
fi

info "Composer found ✓"

# Check if drupalorg-cli is already installed
if command -v drupalorg &> /dev/null; then
    CURRENT_VERSION=$(drupalorg --version 2>/dev/null | head -n1 || echo "unknown")
    warn "drupalorg-cli is already installed: $CURRENT_VERSION"
    echo ""
    read -p "Update to latest version? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Skipping installation."
        exit 0
    fi
fi

# Install drupalorg-cli globally via Composer
info "Installing drupalorg-cli via Composer..."
composer global require mglaman/drupalorg-cli

# Check if Composer global bin is in PATH
COMPOSER_BIN_DIR=$(composer global config bin-dir --absolute 2>/dev/null || echo "$HOME/.composer/vendor/bin")

if ! echo "$PATH" | grep -q "$COMPOSER_BIN_DIR"; then
    warn "Composer global bin directory is not in your PATH!"
    echo ""
    echo "Add this to your ~/.bashrc, ~/.zshrc, or shell profile:"
    echo ""
    echo "  export PATH=\"\$PATH:$COMPOSER_BIN_DIR\""
    echo ""
    echo "Then run: source ~/.bashrc (or ~/.zshrc)"
fi

# Verify installation
if command -v drupalorg &> /dev/null; then
    VERSION=$(drupalorg --version 2>/dev/null | head -n1 || echo "installed")
    success "drupalorg-cli installed successfully!"
    echo ""
    info "Version: $VERSION"
    echo ""
    info "Common commands:"
    echo "  drupalorg issue:show <nid> --format=llm"
    echo "  drupalorg issue:get-fork <nid> --format=llm"
    echo "  drupalorg issue:setup-remote <nid>"
    echo "  drupalorg issue:checkout <nid> <branch>"
    echo "  drupalorg mr:list <nid> --format=llm"
    echo "  drupalorg mr:status <nid> <mr-iid> --format=llm"
    echo "  drupalorg mr:logs <nid> <mr-iid>"
    echo ""
    info "See full documentation: https://github.com/mglaman/drupalorg-cli"
else
    error "Installation completed but 'drupalorg' command not found in PATH."
    echo ""
    echo "Try closing and reopening your terminal, or add Composer bin to PATH:"
    echo "  export PATH=\"\$PATH:$COMPOSER_BIN_DIR\""
    exit 1
fi

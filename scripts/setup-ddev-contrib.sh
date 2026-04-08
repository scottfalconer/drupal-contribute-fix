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

# Set up git excludes for DDEV and generated files
info "Setting up git excludes for DDEV files..."

# Check if we're in a git repository
if [ ! -d .git ]; then
    warn "Not in a git repository. Skipping git excludes setup."
else
    # Create or append to .git/info/exclude
    cat >> .git/info/exclude <<EOF

# DDEV and contrib development files (added by setup-ddev-contrib.sh)
/.ddev/
/recipes/
/vendor/
/web/
/.gitignore
/composer.lock
/phpcs.xml.dist
/phpstan.neon
/phpstan-baseline.neon
EOF

    info "Git excludes configured. Run 'git status' after running CI commands to see if additional files need excluding."
fi

info "ddev-drupal-contrib setup complete!"
info "Available commands:"
echo "  - ddev poser (Composer)"
echo "  - ddev phpstan"
echo "  - ddev phpcs"
echo "  - ddev phpcbf"
echo "  - ddev phpunit"
echo ""
warn "Note: cspell is not included by default. Run setup-ddev-cspell.sh to add it."
echo ""
info "After running CI commands (ddev phpcs, ddev phpstan), check 'git status' for any new untracked files."
info "Add them to .git/info/exclude as needed to keep your commits clean."

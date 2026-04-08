#!/usr/bin/env bash
# Setup workspace for working on a Drupal contrib merge request
# Based on workflow: https://github.com/ddev/ddev-drupal-contrib/pull/55#issuecomment-4171026900

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

usage() {
    echo "Usage: $0 <module_name> <issue_id> <branch_name>"
    echo ""
    echo "Example:"
    echo "  $0 recaptcha_v3 3580901 'NNNNNNN-pass-gitlab-ci'"
    echo ""
    echo "This will:"
    echo "  1. Clone the module from drupalcode.org"
    echo "  2. Add the issue fork remote"
    echo "  3. Checkout the MR branch"
    echo "  4. Set up git excludes for DDEV files"
    exit 1
}

# Check arguments
if [ $# -lt 3 ]; then
    usage
fi

MODULE_NAME="$1"
ISSUE_ID="$2"
BRANCH_NAME="$3"

info "Setting up workspace for ${MODULE_NAME} issue #${ISSUE_ID}..."

# Create a working directory
WORK_DIR="${MODULE_NAME}"
if [ -d "$WORK_DIR" ]; then
    error "Directory $WORK_DIR already exists. Please remove it or choose a different location."
    exit 1
fi

# Clone the module repository
info "Cloning ${MODULE_NAME} from drupalcode.org..."
git clone "https://git.drupalcode.org/project/${MODULE_NAME}.git" "$WORK_DIR"

cd "$WORK_DIR"

# Add issue fork remote
info "Adding issue fork remote..."
ISSUE_REMOTE="${MODULE_NAME}-${ISSUE_ID}"
git remote add "$ISSUE_REMOTE" "git@git.drupal.org:issue/${MODULE_NAME}-${ISSUE_ID}.git"

# Fetch issue fork
info "Fetching issue fork..."
git fetch "$ISSUE_REMOTE"

# Checkout branch
info "Checking out branch: ${BRANCH_NAME}..."
git checkout -b "$BRANCH_NAME" --track "${ISSUE_REMOTE}/${BRANCH_NAME}"

# Set up git excludes for DDEV files
info "Setting up git excludes for DDEV files..."
cat >> .git/info/exclude <<EOF

# DDEV and contrib development files
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

info "Workspace setup complete!"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. cd ${WORK_DIR}"
echo "  2. Run: ddev config --project-type=drupal --docroot=web"
echo "  3. Run: ddev start"
echo "  4. Run: ../scripts/setup-ddev-contrib.sh"
echo "  5. Run: ../scripts/setup-cspell.sh"
echo "  6. Run: ../scripts/run-local-ci.sh"

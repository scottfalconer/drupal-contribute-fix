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
    echo "  $0 recaptcha_v3 3580901 '3580901-pass-gitlab-ci'"
    echo ""
    echo "This will:"
    echo "  1. Clone the module from drupalcode.org"
    echo "  2. Add the issue fork remote"
    echo "  3. Checkout the MR branch"
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

# List available branches in the issue fork
info "Available branches in issue fork:"
AVAILABLE_BRANCHES=$(git branch -r | grep "$ISSUE_REMOTE/" | sed "s|.*$ISSUE_REMOTE/||" | grep -v HEAD || true)

if [ -z "$AVAILABLE_BRANCHES" ]; then
    warn "No branches found in issue fork. This may be an error."
else
    echo "$AVAILABLE_BRANCHES" | while read -r branch; do
        # Get last commit date for this branch
        LAST_COMMIT=$(git log -1 --format="%cr" "${ISSUE_REMOTE}/${branch}" 2>/dev/null || echo "unknown")
        if [ "$branch" = "$BRANCH_NAME" ]; then
            echo -e "${GREEN}  * $branch${NC} (selected, last commit: $LAST_COMMIT)"
        else
            echo "    $branch (last commit: $LAST_COMMIT)"
        fi
    done
fi

# Check if the specified branch exists
if ! git show-ref --verify --quiet "refs/remotes/${ISSUE_REMOTE}/${BRANCH_NAME}"; then
    echo ""
    error "Branch '${BRANCH_NAME}' not found in issue fork!"
    echo ""
    echo "Available branches:"
    echo "$AVAILABLE_BRANCHES"
    echo ""
    echo "Tip: Use 'drupalorg mr:list ${ISSUE_ID}' to see all merge requests and their branches."
    exit 1
fi

# Checkout branch
info "Checking out branch: ${BRANCH_NAME}..."
git checkout -b "$BRANCH_NAME" --track "${ISSUE_REMOTE}/${BRANCH_NAME}"

info "Workspace setup complete!"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. cd ${WORK_DIR}"
echo "  2. Run: ddev config --project-type=drupal --docroot=web"
echo "  3. Run: ddev start"
echo "  4. Run: ../scripts/setup-ddev-contrib.sh"
echo "  5. Run: ../scripts/setup-ddev-cspell.sh"
echo "  6. Run: ../scripts/run-local-ci.sh"

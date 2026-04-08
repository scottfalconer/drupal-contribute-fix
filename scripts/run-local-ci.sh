#!/usr/bin/env bash
# Run local CI checks that mirror Drupal GitLab CI
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

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if we're in a DDEV project
if [ ! -f .ddev/config.yaml ]; then
    error "Not in a DDEV project directory. Please run this from a DDEV project root."
    exit 1
fi

# Track overall success
OVERALL_SUCCESS=0

# Function to run a command and track result
run_check() {
    local check_name="$1"
    local command="$2"
    local fix_command="${3:-}"

    echo ""
    info "Running ${check_name}..."

    if eval "$command"; then
        success "${check_name} passed!"
    else
        error "${check_name} failed!"
        OVERALL_SUCCESS=1

        if [ -n "$fix_command" ]; then
            echo -e "${BLUE}[FIX]${NC} Try running: ${fix_command}"
        fi
    fi
}

# PHPStan - Static analysis
run_check "PHPStan" "ddev phpstan" ""

# PHPCS - Coding standards check
run_check "PHPCS" "ddev phpcs" "ddev phpcbf"

# CSpell - Spell checking
if [ -f .ddev/commands/web/cspell ]; then
    run_check "CSpell" "ddev cspell" ""
else
    warn "CSpell command not found. Run setup-cspell.sh to install it."
fi

# Summary
echo ""
echo "=================================================="
if [ $OVERALL_SUCCESS -eq 0 ]; then
    success "All CI checks passed! ✓"
    echo ""
    info "You can now commit your changes and push to the MR:"
    echo "  git add <changed-files>"
    echo "  git commit -m \"Issue #<nid> by <username>: <description>\""
    echo "  git push"
else
    error "Some CI checks failed. Please fix the issues above."
    echo ""
    info "Common fixes:"
    echo "  - Run 'ddev phpcbf' to auto-fix coding standards issues"
    echo "  - Check PHPStan output for type errors and fix manually"
    echo "  - Add unknown words to .cspell-project-words.txt for spell check"
fi
echo "=================================================="

exit $OVERALL_SUCCESS

#!/usr/bin/env bash
# Install the Drupal.org CLI in the Composer global project.
set -euo pipefail

if [[ $# -eq 1 && $1 == --help ]]; then
    printf 'Usage: %s\n' "${0##*/}"
    printf 'Install or update mglaman/drupalorg-cli with Composer global require.\n'
    printf 'This changes your global Composer project. It requires PHP 8.1+ and Composer.\n'
    printf 'Composer plugins and scripts are disabled for these commands.\n'
    exit 0
fi
if [[ $# -ne 0 ]]; then
    printf 'Error: No arguments are supported. Use --help for instructions.\n' >&2
    exit 2
fi
if ! command -v php >/dev/null 2>&1 || ! command -v composer >/dev/null 2>&1; then
    printf 'Error: Install PHP 8.1+ and Composer. Add both commands to PATH.\n' >&2
    exit 1
fi
if ! php -r 'exit(version_compare(PHP_VERSION, "8.1.0", ">=") ? 0 : 1);'; then
    printf 'Error: PHP 8.1 or later is required.\n' >&2
    exit 1
fi

# Keep the existing plugin policy. Do not run unrelated global project scripts.
composer global require --no-interaction --no-plugins --no-scripts mglaman/drupalorg-cli
composer_bin=$(composer global config --no-interaction --no-plugins --no-scripts bin-dir --absolute)
binary="$composer_bin/drupalorg"
if [[ ! -x $binary ]]; then
    printf 'Error: The installed command is missing or is not executable: %s\n' "$binary" >&2
    exit 1
fi
# Check the installed binary, not a different copy that is already on PATH.
"$binary" --version
printf 'Installed command: %s\n' "$binary"
case ":${PATH-}:" in
    *":$composer_bin:"*) ;;
    *)
        printf 'Add this directory to PATH in your shell configuration:\n'
        printf '  export PATH=%q:"$PATH"\n' "$composer_bin"
        ;;
esac

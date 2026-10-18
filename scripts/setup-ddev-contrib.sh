#!/usr/bin/env bash
# Install the official DDEV add-on and its project dependencies.
set -euo pipefail

if [[ $# -eq 1 && $1 == --help ]]; then
    printf 'Usage: %s\n' "${0##*/}"
    printf 'Run in a configured DDEV project root. Install dependencies and restart DDEV.\n'
    exit 0
fi
if [[ $# -ne 0 ]]; then
    printf 'Error: No arguments are supported. Use --help for instructions.\n' >&2
    exit 2
fi
if [[ ! -f .ddev/config.yaml ]]; then
    printf 'Error: Run this command from a DDEV project root.\n' >&2
    exit 1
fi
if ! command -v ddev >/dev/null 2>&1; then
    printf 'Error: Install DDEV and add it to PATH.\n' >&2
    exit 1
fi

ddev add-on get ddev/ddev-drupal-contrib
ddev restart
ddev poser
ddev symlink-project
printf 'DDEV contrib setup is complete. Review the files with git status.\n'

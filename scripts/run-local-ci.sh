#!/usr/bin/env bash
# Run selected local checks. This is not a full Drupal GitLab CI pipeline.
set -euo pipefail

usage() {
    printf 'Usage: %s [--cspell]\n' "${0##*/}"
    printf 'Run ddev phpstan and ddev phpcs. Add --cspell to run ddev cspell.\n'
    printf 'A failed or unavailable check returns a nonzero exit code.\n'
}

checks=(phpstan phpcs)
if [[ $# -eq 1 && $1 == --help ]]; then
    usage
    exit 0
fi
if [[ $# -eq 1 && $1 == --cspell ]]; then
    checks+=(cspell)
elif [[ $# -ne 0 ]]; then
    usage >&2
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

result=0
for check in "${checks[@]}"; do
    printf '\nRun: ddev %s\n' "$check"
    if ddev "$check"; then
        printf 'PASS: ddev %s\n' "$check"
    else
        check_status=$?
        printf 'FAIL: ddev %s (exit %s)\n' "$check" "$check_status" >&2
        result=1
    fi
done

if [[ $result -eq 0 ]]; then
    printf '\nAll selected local checks passed.\n'
else
    printf '\nOne or more selected local checks failed.\n' >&2
fi
printf 'Scope: %s\n' "${checks[*]}"
printf 'Run the project tests and GitLab CI separately.\n'
exit "$result"

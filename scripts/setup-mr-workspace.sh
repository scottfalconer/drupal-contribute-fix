#!/usr/bin/env bash
# Create a local repository for one issue-fork branch.
set -euo pipefail

usage() {
    printf 'Usage: %s <project> <issue_id> <branch>\n' "${0##*/}"
    printf 'Create a new <project> directory. Use the exact issue-fork branch name.\n'
}

if [[ $# -eq 1 && $1 == --help ]]; then
    usage
    exit 0
fi
if [[ $# -ne 3 ]]; then
    usage >&2
    exit 2
fi

project=$1
issue_id=$2
branch=$3
if [[ ! $project =~ ^[a-z][a-z0-9_]*$ || ! $issue_id =~ ^[1-9][0-9]*$ ]]; then
    printf 'Error: Use a project machine name and a positive issue number.\n' >&2
    exit 2
fi
if ! command -v git >/dev/null 2>&1; then
    printf 'Error: Install Git and add it to PATH.\n' >&2
    exit 1
fi
# Check the literal ref. Do not expand Git shortcuts such as @{-1}.
if ! git check-ref-format "refs/heads/$branch" || ! git check-ref-format --branch "$branch" >/dev/null; then
    printf 'Error: Invalid branch name: %s\n' "$branch" >&2
    exit 2
fi
if [[ -e $project || -L $project ]]; then
    printf 'Error: The destination already exists: %s\n' "$project" >&2
    exit 1
fi

issue_remote="${project}-${issue_id}"
issue_url="https://git.drupalcode.org/issue/${issue_remote}.git"
if ! git ls-remote --exit-code --heads "$issue_url" "refs/heads/$branch" >/dev/null; then
    printf 'Error: Cannot read branch %s from %s. Check the issue fork and branch.\n' "$branch" "$issue_url" >&2
    exit 1
fi

# Start with no local branch. The fork can use the same branch name as upstream.
git init --quiet "$project"
cd "$project"
git remote add origin "https://git.drupalcode.org/project/${project}.git"
git remote add "$issue_remote" "$issue_url"
git fetch "$issue_remote" "refs/heads/$branch:refs/remotes/$issue_remote/$branch"
git checkout -b "$branch" --track "$issue_remote/$branch"
printf 'Workspace ready: %s\n' "$PWD"
printf 'Branch: %s (tracks %s/%s)\n' "$branch" "$issue_remote" "$branch"

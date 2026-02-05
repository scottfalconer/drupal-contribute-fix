#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

prefix="${1:-}"
if [[ -z "${prefix}" ]]; then
  if [[ -d "${HOME}/.local/bin" ]]; then
    prefix="${HOME}/.local/bin"
  else
    prefix="${HOME}/.local/bin"
    mkdir -p "${prefix}"
  fi
fi

mkdir -p "${prefix}"

dcf_src="${root_dir}/scripts/contribute_fix.py"
dcf_dst="${prefix}/dcf"
ln -sf "${dcf_src}" "${dcf_dst}"

echo "Installed: ${dcf_dst} -> ${dcf_src}"

# Optional dorg shim (drupal-issue-queue), if available.
dorg_candidates=(
  "${root_dir}/../drupal-issue-queue/scripts/dorg.py"
  "${HOME}/.agents/skills/drupal-issue-queue/scripts/dorg.py"
  "${HOME}/.codex/skills/drupal-issue-queue/scripts/dorg.py"
)
if [[ -n "${CODEX_HOME:-}" ]]; then
  dorg_candidates+=("${CODEX_HOME}/skills/drupal-issue-queue/scripts/dorg.py")
fi

dorg_src=""
for c in "${dorg_candidates[@]}"; do
  if [[ -f "${c}" ]]; then
    dorg_src="${c}"
    break
  fi
done

if [[ -n "${dorg_src}" ]]; then
  dorg_dst="${prefix}/dorg"
  ln -sf "${dorg_src}" "${dorg_dst}"
  echo "Installed: ${dorg_dst} -> ${dorg_src}"
else
  echo "Note: drupal-issue-queue not found; skipping dorg shim."
fi

echo
echo "Ensure '${prefix}' is on your PATH, then you can run:"
echo "  dcf preflight --project <project> --keywords \"...\" --out .drupal-contribute-fix"
echo "  dorg --format md issue <nid>"


"""
Optional integration with the `drupal-issue-queue` skill/tool.

This repo does not require `drupal-issue-queue`, but if it is present we can:
  - point users/agents at the correct `dorg.py` invocation, and/or
  - generate a small markdown summary for the best-match issue.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def find_dorg_script(repo_root: Optional[Path] = None) -> Optional[Path]:
    """
    Find the `drupal-issue-queue` CLI script (dorg.py) if installed locally.

    Search order:
      1) $DRUPAL_ISSUE_QUEUE_DIR/scripts/dorg.py
      2) sibling directory next to this repo (../drupal-issue-queue/scripts/dorg.py)
      3) common Codex skill locations under the current user's home directory
      4) $CODEX_HOME/skills/drupal-issue-queue/scripts/dorg.py
    """
    override = os.environ.get("DRUPAL_ISSUE_QUEUE_DIR")
    if override:
        candidate = Path(override) / "scripts" / "dorg.py"
        if candidate.is_file():
            return candidate

    candidates = []
    if repo_root is not None:
        candidates.append(repo_root.parent / "drupal-issue-queue" / "scripts" / "dorg.py")

    home = Path.home()
    candidates.extend(
        [
            home / ".agents" / "skills" / "drupal-issue-queue" / "scripts" / "dorg.py",
            home / ".codex" / "skills" / "drupal-issue-queue" / "scripts" / "dorg.py",
        ]
    )

    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(Path(codex_home) / "skills" / "drupal-issue-queue" / "scripts" / "dorg.py")

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


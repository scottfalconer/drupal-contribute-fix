"""
Helpers for building Drupal.org URLs.

Notes:
  - The Drupal.org "api-d7" endpoint does NOT support a `text=` filter for
    full-text/keyword searching. Keyword search is done via the HTML UI at:
      /project/issues/search/<project>?text=<keywords>
"""

from __future__ import annotations

from typing import Iterable, Optional
from urllib.parse import quote, quote_plus


def build_project_issue_search_url(project: str, keywords: Optional[Iterable[str]] = None) -> str:
    """
    Build the Drupal.org project issue search (UI) URL for a project + keywords.

    Example:
        build_project_issue_search_url("webform", ["timezone", "datetime"])
        -> https://www.drupal.org/project/issues/search/webform?text=timezone+datetime
    """
    project_slug = quote(str(project).strip(), safe="")
    base = f"https://www.drupal.org/project/issues/search/{project_slug}"

    keyword_list = [str(k).strip() for k in (keywords or []) if str(k).strip()]
    if not keyword_list:
        return base

    query = " ".join(keyword_list)
    return f"{base}?text={quote_plus(query)}"


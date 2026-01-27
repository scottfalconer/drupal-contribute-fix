"""
Drupal.org API client with caching and rate limiting.

Uses only stdlib (urllib) to minimize dependencies.
Respects drupal.org guidelines: single-threaded, cached, appropriate User-Agent.
"""

import json
import hashlib
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List, Any

# API Configuration
API_BASE = "https://www.drupal.org/api-d7"
USER_AGENT = "drupal-contribute-fix/1.0 (https://github.com/drupal-contribute-fix; community contribution helper)"

# Rate limiting
MIN_REQUEST_INTERVAL = 1.0  # seconds between requests
_last_request_time = 0.0

# Cache TTLs (seconds)
CACHE_TTL = {
    "project_nid": 86400,      # 24 hours - projects rarely change
    "issue_list": 3600,        # 1 hour - issues change frequently
    "issue_detail": 1800,      # 30 min - comments/MRs update
    "file_metadata": 86400,    # 24 hours - files are immutable
}

# Issue status code mapping (from drupal.org API docs)
ISSUE_STATUS = {
    1: "Active",
    2: "Fixed",
    3: "Closed (duplicate)",
    4: "Postponed",
    5: "Closed (won't fix)",
    6: "Closed (works as designed)",
    7: "Closed (fixed)",
    8: "Needs review",
    13: "Needs work",
    14: "Reviewed & tested by the community",
    15: "Patch (to be ported)",
    16: "Postponed (maintainer needs more info)",
    17: "Closed (outdated)",
    18: "Closed (cannot reproduce)",
}

# Issue priority mapping
ISSUE_PRIORITY = {
    400: "Critical",
    300: "Major",
    200: "Normal",
    100: "Minor",
}


class DrupalOrgAPIError(Exception):
    """Exception for API errors."""
    pass


class DrupalOrgAPI:
    """Client for Drupal.org REST API."""

    def __init__(self, cache_dir: Optional[Path] = None, offline: bool = False):
        """
        Initialize the API client.

        Args:
            cache_dir: Directory for caching responses. Defaults to ~/.cache/drupal-contribute-fix
            offline: If True, only use cached data, don't make API requests
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "drupal-contribute-fix"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.offline = offline

    def _cache_key(self, url: str, params: Dict[str, Any]) -> str:
        """Generate a cache key from URL and params."""
        key_data = url + json.dumps(params, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def _cache_path(self, cache_key: str) -> Path:
        """Get the cache file path for a key."""
        return self.cache_dir / f"{cache_key}.json"

    def _read_cache(self, cache_key: str, ttl: int) -> Optional[Dict]:
        """Read from cache if valid."""
        cache_path = self._cache_path(cache_key)
        if not cache_path.exists():
            return None

        try:
            stat = cache_path.stat()
            age = time.time() - stat.st_mtime
            if age > ttl:
                return None  # Cache expired

            with open(cache_path, 'r') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _write_cache(self, cache_key: str, data: Dict) -> None:
        """Write data to cache."""
        cache_path = self._cache_path(cache_key)
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
        except OSError:
            pass  # Cache write failure is not critical

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        global _last_request_time
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None,
                 cache_type: str = "issue_list") -> Dict:
        """
        Make an API request with caching and rate limiting.

        Args:
            endpoint: API endpoint (e.g., "node.json")
            params: Query parameters
            cache_type: Type for determining TTL

        Returns:
            JSON response as dict
        """
        params = params or {}
        url = f"{API_BASE}/{endpoint}"

        # Check cache first
        cache_key = self._cache_key(url, params)
        ttl = CACHE_TTL.get(cache_type, 3600)
        cached = self._read_cache(cache_key, ttl)
        if cached is not None:
            return cached

        # If offline mode, fail if not in cache
        if self.offline:
            raise DrupalOrgAPIError(f"Offline mode: no cached data for {endpoint}")

        # Rate limit
        self._rate_limit()

        # Build URL with params
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        # Make request
        request = urllib.request.Request(url)
        request.add_header("User-Agent", USER_AGENT)
        request.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                self._write_cache(cache_key, data)
                return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited - wait and retry once
                time.sleep(5)
                self._rate_limit()
                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        data = json.loads(response.read().decode('utf-8'))
                        self._write_cache(cache_key, data)
                        return data
                except urllib.error.HTTPError as e2:
                    raise DrupalOrgAPIError(f"API request failed after retry: {e2.code} {e2.reason}")
            raise DrupalOrgAPIError(f"API request failed: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            raise DrupalOrgAPIError(f"Network error: {e.reason}")

    def get_project_nid(self, machine_name: str) -> Optional[int]:
        """
        Get the node ID for a project by its machine name.

        Args:
            machine_name: Project machine name (e.g., "metatag", "drupal")

        Returns:
            Project node ID or None if not found
        """
        params = {
            "field_project_machine_name": machine_name,
            "limit": 1,
        }
        result = self._request("node.json", params, cache_type="project_nid")

        nodes = result.get("list", [])
        if nodes:
            return int(nodes[0].get("nid"))
        return None

    def list_project_issues(self, project_nid: int, page: int = 0,
                           limit: int = 50, status: Optional[List[int]] = None) -> Dict:
        """
        List issues for a project.

        Args:
            project_nid: Project node ID
            page: Page number (0-indexed)
            limit: Results per page (max 50)
            status: Filter by status codes (optional)

        Returns:
            API response with 'list' of issues
        """
        params = {
            "type": "project_issue",
            "field_project": project_nid,
            "sort": "changed",
            "direction": "DESC",
            "limit": min(limit, 50),
            "page": page,
        }
        if status:
            # Drupal.org API accepts comma-separated status values
            params["field_issue_status"] = ",".join(str(s) for s in status)

        return self._request("node.json", params, cache_type="issue_list")

    def get_issue(self, issue_nid: int, include_mrs: bool = True) -> Dict:
        """
        Get detailed information about an issue.

        Args:
            issue_nid: Issue node ID
            include_mrs: Include related merge requests

        Returns:
            Issue details
        """
        endpoint = f"node/{issue_nid}.json"
        params = {}
        if include_mrs:
            params["related_mrs"] = 1

        return self._request(endpoint, params, cache_type="issue_detail")

    def get_comments(self, issue_nid: int) -> List[Dict]:
        """
        Get comments for an issue.

        Args:
            issue_nid: Issue node ID

        Returns:
            List of comments
        """
        params = {"node": issue_nid}
        result = self._request("comment.json", params, cache_type="issue_detail")
        return result.get("list", [])

    def get_file(self, fid: int) -> Dict:
        """
        Get file metadata.

        Args:
            fid: File ID

        Returns:
            File metadata including URL
        """
        endpoint = f"file/{fid}.json"
        return self._request(endpoint, cache_type="file_metadata")

    def fetch_issues_batch(self, project_nid: int, max_issues: int = 200) -> List[Dict]:
        """
        Fetch multiple pages of issues.

        Args:
            project_nid: Project node ID
            max_issues: Maximum number of issues to fetch

        Returns:
            List of issues
        """
        issues = []
        page = 0
        per_page = 50

        while len(issues) < max_issues:
            result = self.list_project_issues(project_nid, page=page, limit=per_page)
            batch = result.get("list", [])
            if not batch:
                break
            issues.extend(batch)
            page += 1

            # Check if there are more pages
            if len(batch) < per_page:
                break

        return issues[:max_issues]


def get_status_label(status_code) -> str:
    """Get human-readable label for a status code."""
    try:
        code = int(status_code)
    except (ValueError, TypeError):
        return f"Unknown ({status_code})"
    return ISSUE_STATUS.get(code, f"Unknown ({code})")


def get_priority_label(priority_code) -> str:
    """Get human-readable label for a priority code."""
    try:
        code = int(priority_code)
    except (ValueError, TypeError):
        return f"Unknown ({priority_code})"
    return ISSUE_PRIORITY.get(code, f"Unknown ({code})")


def is_fixed_status(status_code) -> bool:
    """Check if status indicates the issue is fixed."""
    try:
        code = int(status_code)
    except (ValueError, TypeError):
        return False
    return code in (2, 7)  # Fixed, Closed (fixed)


def is_actionable_status(status_code) -> bool:
    """Check if status indicates the issue is open and actionable."""
    try:
        code = int(status_code)
    except (ValueError, TypeError):
        return False
    return code in (1, 8, 13, 14, 16)  # Active, Needs review, Needs work, RTBC, Postponed (needs info)


def has_existing_fix(issue: Dict) -> bool:
    """
    Check if an issue has an existing fix (MR or patch).

    Args:
        issue: Issue data from API

    Returns:
        True if existing fix likely exists
    """
    # Check for related MRs
    if issue.get("related_mrs"):
        return True

    # Check status
    status = issue.get("field_issue_status")
    if status in (2, 7, 14):  # Fixed, Closed (fixed), RTBC
        return True

    return False

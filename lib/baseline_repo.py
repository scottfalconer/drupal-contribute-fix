"""
Baseline repository resolution and checkout.

Determines the correct upstream git repository and ref for generating patches.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class BaselineInfo:
    """Information about the baseline repository."""
    project: str
    git_url: str
    ref: str
    version: Optional[str] = None
    source: str = "fallback"  # "composer_lock", "fallback", "explicit"
    checkout_path: Optional[Path] = None
    contribution_branch: Optional[str] = None  # Recommended branch for contributions


def get_contribution_branch(project_name: str, project_type: str, version: Optional[str] = None) -> str:
    """
    Determine the recommended branch for contributions.

    As of Jan 2026:
    - Drupal core contributions should target 'main' (the primary dev trunk)
    - 11.x is maintained for Drupal-11-specific backports
    - Contrib modules typically use major.x or major.minor.x branches
    """
    if project_type == "core":
        # Core contributions should target main (as of Jan 2026)
        return "main"

    # For contrib, derive from version if available
    if version:
        version = version.lstrip("v")
        if version.startswith("dev-"):
            return version[4:]
        parts = version.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}.x"
        elif parts:
            return f"{parts[0]}.x"

    # Fallback for contrib
    return "2.0.x"


class BaselineError(Exception):
    """Error resolving or checking out baseline."""
    pass


def parse_composer_lock(lock_path: Path) -> Dict:
    """Parse composer.lock file."""
    try:
        with open(lock_path, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise BaselineError(f"Failed to parse composer.lock: {e}")


def find_package_in_lock(lock_data: Dict, package_name: str) -> Optional[Dict]:
    """Find a package in composer.lock data."""
    for package in lock_data.get("packages", []):
        if package.get("name") == package_name:
            return package
    for package in lock_data.get("packages-dev", []):
        if package.get("name") == package_name:
            return package
    return None


def detect_project_from_path(changed_path: str, site_root: Path) -> Tuple[str, str]:
    """
    Detect project name and type from a changed file path.

    Args:
        changed_path: Path to changed file/directory
        site_root: Site root directory

    Returns:
        Tuple of (project_name, project_type)
        project_type is one of: "core", "module", "theme", "profile"
    """
    # Normalize path
    changed_path = str(changed_path)

    # Check for core
    core_patterns = [
        r'/core/',
        r'^core/',
        r'/docroot/core/',
        r'/web/core/',
    ]
    for pattern in core_patterns:
        if re.search(pattern, changed_path):
            return "drupal", "core"

    # Check for contrib modules
    module_patterns = [
        r'/modules/contrib/([^/]+)',
        r'/docroot/modules/contrib/([^/]+)',
        r'/web/modules/contrib/([^/]+)',
    ]
    for pattern in module_patterns:
        match = re.search(pattern, changed_path)
        if match:
            return match.group(1), "module"

    # Check for contrib themes
    theme_patterns = [
        r'/themes/contrib/([^/]+)',
        r'/docroot/themes/contrib/([^/]+)',
        r'/web/themes/contrib/([^/]+)',
    ]
    for pattern in theme_patterns:
        match = re.search(pattern, changed_path)
        if match:
            return match.group(1), "theme"

    # Check for profiles
    profile_patterns = [
        r'/profiles/contrib/([^/]+)',
        r'/docroot/profiles/contrib/([^/]+)',
        r'/web/profiles/contrib/([^/]+)',
    ]
    for pattern in profile_patterns:
        match = re.search(pattern, changed_path)
        if match:
            return match.group(1), "profile"

    raise BaselineError(f"Could not determine project from path: {changed_path}")


def get_composer_package_name(project_name: str, project_type: str) -> str:
    """Get the Composer package name for a Drupal project."""
    if project_name == "drupal" and project_type == "core":
        return "drupal/core"
    return f"drupal/{project_name}"


def get_drupal_git_url(project_name: str) -> str:
    """Get the Git URL for a Drupal.org project."""
    return f"https://git.drupalcode.org/project/{project_name}.git"


def version_to_branch(version: str, project_type: str) -> str:
    """
    Convert a Composer version to a git branch name.

    Examples:
        "10.2.5" -> "10.2.x"
        "2.0.3" -> "2.0.x"
        "dev-2.0.x" -> "2.0.x"
    """
    # Handle dev versions
    if version.startswith("dev-"):
        return version[4:]

    # Strip any leading 'v'
    version = version.lstrip("v")

    # For semantic versions like "10.2.5" -> "10.2.x"
    parts = version.split(".")
    if len(parts) >= 2:
        # For core, use major.minor.x
        if project_type == "core" and len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}.x"
        # For contrib, typically major.x or major.minor.x
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}.x"

    # Fallback: try major.x
    if parts:
        return f"{parts[0]}.x"

    return version


def resolve_baseline(
    project_name: str,
    project_type: str,
    site_root: Optional[Path] = None,
    explicit_ref: Optional[str] = None
) -> BaselineInfo:
    """
    Resolve the baseline repository information.

    Args:
        project_name: Drupal project machine name
        project_type: "core", "module", "theme", or "profile"
        site_root: Site root for finding composer.lock
        explicit_ref: Explicit git ref to use (overrides detection)

    Returns:
        BaselineInfo with git URL and ref
    """
    git_url = get_drupal_git_url(project_name)
    package_name = get_composer_package_name(project_name, project_type)

    # Determine contribution branch (where contributions should be targeted)
    contrib_branch = get_contribution_branch(project_name, project_type)

    # Try composer.lock first
    if site_root:
        lock_path = site_root / "composer.lock"
        if lock_path.exists():
            try:
                lock_data = parse_composer_lock(lock_path)
                package = find_package_in_lock(lock_data, package_name)

                if package:
                    version = package.get("version", "")
                    source = package.get("source", {})
                    # Update contribution branch based on actual version
                    contrib_branch = get_contribution_branch(project_name, project_type, version)

                    # Prefer exact commit ref from source
                    ref = source.get("reference")
                    if ref and explicit_ref is None:
                        return BaselineInfo(
                            project=project_name,
                            git_url=source.get("url", git_url),
                            ref=ref,
                            version=version,
                            source="composer_lock",
                            contribution_branch=contrib_branch,
                        )

                    # Fall back to branch derived from version
                    if version and explicit_ref is None:
                        branch = version_to_branch(version, project_type)
                        return BaselineInfo(
                            project=project_name,
                            git_url=git_url,
                            ref=branch,
                            version=version,
                            source="composer_lock",
                            contribution_branch=contrib_branch,
                        )
            except BaselineError:
                pass  # Fall through to fallback

    # Use explicit ref if provided
    if explicit_ref:
        return BaselineInfo(
            project=project_name,
            git_url=git_url,
            ref=explicit_ref,
            source="explicit",
            contribution_branch=contrib_branch,
        )

    # Fallback: use default branch heuristics
    if project_type == "core":
        # As of Jan 2026, 'main' is Drupal core's primary development trunk
        # Most core contributions should target 'main'
        ref = "main"
    else:
        # For contrib, try common patterns
        ref = "2.0.x"  # Most common for D10+ modules

    return BaselineInfo(
        project=project_name,
        git_url=git_url,
        ref=ref,
        source="fallback",
        contribution_branch=contrib_branch,
    )


def _is_commit_sha(ref: str) -> bool:
    """Check if a ref looks like a commit SHA (40 hex characters)."""
    if not ref:
        return False
    # Full SHA is 40 hex chars, but we also accept short SHAs (7+ chars)
    return bool(re.match(r'^[0-9a-f]{7,40}$', ref.lower()))


def checkout_baseline(
    baseline: BaselineInfo,
    work_dir: Optional[Path] = None,
    shallow: bool = True
) -> Path:
    """
    Clone and checkout the baseline repository.

    Args:
        baseline: BaselineInfo with git URL and ref
        work_dir: Working directory for clone. Defaults to temp dir.
        shallow: Use shallow clone if True (disabled for commit SHAs)

    Returns:
        Path to the checked out repository
    """
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="drupal-contribute-fix-"))

    checkout_path = work_dir / baseline.project

    # Commit SHAs require full clone - shallow clone won't have the commit
    ref_is_sha = _is_commit_sha(baseline.ref)
    use_shallow = shallow and not ref_is_sha

    if ref_is_sha:
        # For SHA refs: full clone, then checkout the specific commit
        clone_cmd = ["git", "clone", baseline.git_url, str(checkout_path)]

        try:
            subprocess.run(
                clone_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise BaselineError(f"Failed to clone {baseline.git_url}: {e.stderr}")

        # Checkout the specific commit
        try:
            subprocess.run(
                ["git", "checkout", baseline.ref],
                cwd=checkout_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise BaselineError(f"Failed to checkout commit {baseline.ref}: {e.stderr}")
    else:
        # For branch/tag refs: try shallow clone with --branch first
        clone_cmd = ["git", "clone"]
        if use_shallow:
            clone_cmd.extend(["--depth", "1"])

        # Try to clone with specific branch/ref
        clone_cmd.extend(["--branch", baseline.ref, baseline.git_url, str(checkout_path)])

        try:
            subprocess.run(
                clone_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            # If branch doesn't exist, clone default branch and try checkout
            clone_cmd = ["git", "clone"]
            if use_shallow:
                clone_cmd.extend(["--depth", "1"])
            clone_cmd.extend([baseline.git_url, str(checkout_path)])

            try:
                subprocess.run(
                    clone_cmd,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                raise BaselineError(f"Failed to clone {baseline.git_url}: {e.stderr}")

            # Try to checkout the specific ref
            if baseline.ref:
                try:
                    subprocess.run(
                        ["git", "checkout", baseline.ref],
                        cwd=checkout_path,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    # If exact ref fails, try fetching it
                    try:
                        subprocess.run(
                            ["git", "fetch", "origin", baseline.ref],
                            cwd=checkout_path,
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        # Some refs (like GitLab MR refs) are not remote-tracking
                        # branches under origin/* and only exist in FETCH_HEAD.
                        if baseline.ref.startswith("refs/"):
                            subprocess.run(
                                ["git", "checkout", "FETCH_HEAD"],
                                cwd=checkout_path,
                                check=True,
                                capture_output=True,
                                text=True,
                            )
                        else:
                            subprocess.run(
                                ["git", "checkout", f"origin/{baseline.ref}"],
                                cwd=checkout_path,
                                check=True,
                                capture_output=True,
                                text=True,
                            )
                    except subprocess.CalledProcessError:
                        raise BaselineError(f"Failed to checkout ref {baseline.ref}: {e.stderr}")

    baseline.checkout_path = checkout_path
    return checkout_path


def get_relative_path_in_project(
    file_path: str,
    project_name: str,
    project_type: str
) -> str:
    """
    Get the path of a file relative to the project root.

    Args:
        file_path: Full path to the file in the site
        project_name: Project machine name
        project_type: "core", "module", "theme", "profile"

    Returns:
        Path relative to project root
    """
    file_path = str(file_path)

    if project_type == "core":
        # Core files: extract path after /core/
        patterns = [
            r'/core/(.*)',
            r'^core/(.*)',
        ]
    else:
        # Contrib: extract path after project directory
        patterns = [
            rf'/(?:modules|themes|profiles)/contrib/{re.escape(project_name)}/(.*)',
            rf'^(?:modules|themes|profiles)/contrib/{re.escape(project_name)}/(.*)',
        ]

    for pattern in patterns:
        match = re.search(pattern, file_path)
        if match:
            return match.group(1)

    # If no pattern matches, return the basename
    return os.path.basename(file_path)

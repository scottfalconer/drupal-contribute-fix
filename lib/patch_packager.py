"""
Diff artifact generation and packaging.

Creates properly-formatted local diff artifacts for MR review.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field


@dataclass
class PatchInfo:
    """Information about a generated local diff artifact."""
    path: Path
    filename: str
    project: str
    description: str
    issue_number: Optional[int] = None
    comment_number: Optional[int] = None
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class ScopeWarning:
    """Warning about change scope."""
    level: str  # "info", "warning", "error"
    message: str
    files: List[str] = field(default_factory=list)


class PatchError(Exception):
    """Error generating diff artifact."""
    pass


# Patterns that indicate potentially problematic changes
HACK_PATTERNS = [
    # Cache bypasses
    (r'\$cache\s*=\s*FALSE', "Cache bypass detected"),
    (r'Cache::invalidateAll', "Broad cache invalidation"),
    (r'\[\'#cache\'\]\s*=\s*\[\'max-age\'\s*=>\s*0\]', "Cache max-age set to 0"),

    # Exception swallowing
    (r'catch\s*\([^)]*\)\s*\{\s*\}', "Empty catch block (swallowed exception)"),
    (r'catch\s*\([^)]*\)\s*\{\s*//\s*ignore', "Ignored exception"),

    # Access bypasses
    (r'->bypassAccessCheck\(\)', "Access check bypass"),
    (r'\$account\s*=\s*NULL', "Potential access bypass with NULL account"),
    (r'\'#access\'\s*=>\s*TRUE', "Hardcoded access grant"),

    # Environment-specific hacks
    (r'getenv\s*\(', "Environment variable usage (may be env-specific)"),
    (r'\$_SERVER\[', "Direct server variable access"),
    (r'\$_ENV\[', "Direct environment variable access"),

    # Hardcoded values
    (r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "Hardcoded URL"),
    (r'/var/www/', "Hardcoded path"),
    (r'/home/', "Hardcoded path"),

    # Debug code
    (r'\bvar_dump\s*\(', "Debug code (var_dump)"),
    (r'\bprint_r\s*\(', "Debug code (print_r)"),
    (r'\bdump\s*\(', "Debug code (dump)"),
    (r'debug_backtrace', "Debug code (backtrace)"),
    (r'\bdd\s*\(', "Debug code (dd)"),
]

# File patterns that may cause issues
PROBLEMATIC_FILES = {
    ".info.yml": "Info YAML files may need reduced diff context (-U1) for clean patching",
    "composer.json": "Composer changes should typically be separate from code changes",
    "composer.lock": "composer.lock should not be in patches",
}

# Files that are packaging artifacts (added by Composer/drupal.org packaging)
# These should be excluded from patches as they don't represent real code changes
PACKAGING_ARTIFACTS = {
    # License files - added by packaging
    "LICENSE.txt",
    "LICENSE",
    "LICENSE.md",
    # Composer artifacts
    "composer.lock",
    # Drupal.org packaging metadata added to info.yml
    # We'll detect these by checking if only 'project' and 'datestamp' lines changed
}

# Patterns in .info.yml that are packaging-only changes
# These patterns match the actual line content (without +/- prefix)
INFO_YML_PACKAGING_LINES = [
    r"^\s*project:\s*['\"]?\w+['\"]?\s*$",
    r"^\s*datestamp:\s*['\"]?\d+['\"]?\s*$",
    r"^\s*version:\s*['\"]?[\d\.x\-]+['\"]?\s*$",
    r"^\s*# Information added by Drupal\.org packaging script.*$",
    r"^\s*$",  # Empty lines
]


def is_packaging_artifact(filepath: str) -> bool:
    """Check if a file is a packaging artifact that should be excluded."""
    filename = os.path.basename(filepath)
    return filename in PACKAGING_ARTIFACTS


def is_packaging_line(line: str) -> bool:
    """Check if a single line (without +/- prefix) is packaging metadata."""
    for pattern in INFO_YML_PACKAGING_LINES:
        if re.match(pattern, line):
            return True
    return False


def is_info_yml_packaging_only(diff_lines: List[str]) -> bool:
    """
    Check if .info.yml changes are only packaging metadata.

    Returns True if the only changes are project/datestamp/version lines
    added by drupal.org packaging scripts.

    Args:
        diff_lines: List of diff-style lines (prefixed with + or -)
    """
    # Get only the actual change lines (not headers)
    change_lines = [
        line for line in diff_lines
        if (line.startswith('+') or line.startswith('-'))
        and not line.startswith('+++') and not line.startswith('---')
    ]

    if not change_lines:
        return True  # No actual changes

    # Check if ALL change lines match packaging patterns
    for line in change_lines:
        # Strip the +/- prefix to get the actual content
        content = line[1:]  # Remove first character (+/-)
        if not is_packaging_line(content):
            return False  # Found a non-packaging change

    return True  # All changes are packaging-only


def filter_packaging_from_diff(diff_content: str) -> str:
    """
    Filter out packaging-only changes from .info.yml files in a diff.

    This removes entire file diffs if they only contain packaging metadata changes.

    Args:
        diff_content: Full git diff output

    Returns:
        Filtered diff with packaging-only .info.yml changes removed
    """
    lines = diff_content.split('\n')
    result_lines = []
    current_file = None
    current_file_lines = []
    in_info_yml = False

    for line in lines:
        # Detect start of new file diff
        if line.startswith('diff --git'):
            # Process previous file if any
            if current_file and current_file_lines:
                if in_info_yml:
                    # Check if it's packaging-only
                    if not is_info_yml_packaging_only(current_file_lines):
                        result_lines.extend(current_file_lines)
                else:
                    result_lines.extend(current_file_lines)

            # Start new file
            current_file_lines = [line]
            # Check if this is an .info.yml file
            match = re.search(r'b/(.+)$', line)
            if match:
                current_file = match.group(1)
                in_info_yml = current_file.endswith('.info.yml')
            else:
                current_file = None
                in_info_yml = False
        else:
            current_file_lines.append(line)

    # Process last file
    if current_file and current_file_lines:
        if in_info_yml:
            if not is_info_yml_packaging_only(current_file_lines):
                result_lines.extend(current_file_lines)
        else:
            result_lines.extend(current_file_lines)

    return '\n'.join(result_lines)


def compute_diffstat_from_patch(diff_content: str, baseline_path: Path) -> Tuple[int, int, int]:
    """
    Compute diffstat from the patch content that will actually be written.

    This keeps report counts consistent with filtered patches (for example when
    packaging-only .info.yml changes are removed).
    """
    if not diff_content.strip():
        return 0, 0, 0

    # Prefer Git's own numstat parser for accuracy (handles renames/binaries).
    try:
        result = subprocess.run(
            ["git", "apply", "--numstat"],
            cwd=baseline_path,
            input=diff_content,
            check=True,
            capture_output=True,
            text=True,
        )
        files_changed = 0
        insertions = 0
        deletions = 0
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            files_changed += 1
            if parts[0].isdigit():
                insertions += int(parts[0])
            if parts[1].isdigit():
                deletions += int(parts[1])
        return files_changed, insertions, deletions
    except subprocess.CalledProcessError:
        # Fall back to lightweight parsing if git numstat parsing fails.
        files_changed = 0
        insertions = 0
        deletions = 0
        for line in diff_content.split('\n'):
            if line.startswith('diff --git '):
                files_changed += 1
            elif line.startswith('+') and not line.startswith('+++'):
                insertions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        return files_changed, insertions, deletions


def sanitize_description(description: str) -> str:
    """Sanitize description for use in filename."""
    # Convert to lowercase, replace spaces/special chars with hyphens
    sanitized = re.sub(r'[^a-z0-9]+', '-', description.lower())
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip('-')
    # Limit length
    return sanitized[:50]


def generate_patch_filename(
    project: str,
    description: str,
    issue_number: Optional[int] = None,
    comment_number: Optional[int] = None
) -> str:
    """
    Generate a Drupal-style diff filename.

    Format: [project]-[description]-[issue]-[comment].diff
    """
    parts = [project, sanitize_description(description)]

    if issue_number:
        parts.append(str(issue_number))
    else:
        parts.append("new")

    if comment_number:
        parts.append(str(comment_number))

    return "-".join(parts) + ".diff"


def detect_hack_patterns(diff_content: str) -> List[ScopeWarning]:
    """Detect potentially problematic patterns in diff content."""
    warnings = []

    # Only check added lines (lines starting with +)
    added_lines = [line for line in diff_content.split('\n') if line.startswith('+')]
    added_content = '\n'.join(added_lines)

    for pattern, message in HACK_PATTERNS:
        if re.search(pattern, added_content, re.IGNORECASE):
            warnings.append(ScopeWarning(
                level="warning",
                message=f"Potential hack: {message}",
            ))

    return warnings


def detect_problematic_files(changed_files: List[str]) -> List[ScopeWarning]:
    """Detect potentially problematic file changes."""
    warnings = []

    for filepath in changed_files:
        filename = os.path.basename(filepath)
        for pattern, message in PROBLEMATIC_FILES.items():
            if filename.endswith(pattern) or filename == pattern:
                warnings.append(ScopeWarning(
                    level="info",
                    message=message,
                    files=[filepath],
                ))

    return warnings


def check_scope(changed_files: List[str], insertions: int, deletions: int) -> List[ScopeWarning]:
    """Check if change scope is appropriate for contribution."""
    warnings = []

    if len(changed_files) > 5:
        warnings.append(ScopeWarning(
            level="warning",
            message=f"Large patch: {len(changed_files)} files changed. Consider splitting.",
            files=changed_files,
        ))
    elif len(changed_files) > 3:
        warnings.append(ScopeWarning(
            level="info",
            message=f"Moderate patch: {len(changed_files)} files changed.",
            files=changed_files,
        ))

    total_changes = insertions + deletions
    if total_changes > 500:
        warnings.append(ScopeWarning(
            level="warning",
            message=f"Large diff: {total_changes} lines changed. Consider splitting.",
        ))
    elif total_changes > 200:
        warnings.append(ScopeWarning(
            level="info",
            message=f"Moderate diff: {total_changes} lines changed.",
        ))

    return warnings


def copy_changes_to_baseline(
    source_path: Path,
    baseline_path: Path,
    changed_files: List[str],
    baseline_prefix: str = ""
) -> Tuple[List[str], List[str], List[str]]:
    """
    Copy changed files from source to baseline.

    Args:
        source_path: Path to source (site module/core directory)
        baseline_path: Path to baseline checkout (repo root)
        changed_files: List of relative file paths (relative to source_path)
        baseline_prefix: Prefix to add when mapping to baseline (e.g., "core/" for core)

    Returns:
        Tuple of (modified_files, new_files, deleted_files)
        File paths in return lists include the baseline_prefix.
    """
    modified = []
    new = []
    deleted = []

    for rel_path in changed_files:
        source_file = source_path / rel_path
        # Apply prefix for baseline path (e.g., lib/Drupal.php -> core/lib/Drupal.php)
        baseline_rel_path = os.path.join(baseline_prefix, rel_path) if baseline_prefix else rel_path
        baseline_file = baseline_path / baseline_rel_path

        if source_file.exists():
            baseline_file.parent.mkdir(parents=True, exist_ok=True)
            if baseline_file.exists():
                # Modified file
                shutil.copy2(source_file, baseline_file)
                modified.append(baseline_rel_path)
            else:
                # New file
                shutil.copy2(source_file, baseline_file)
                new.append(baseline_rel_path)
        else:
            if baseline_file.exists():
                # Deleted file
                baseline_file.unlink()
                deleted.append(baseline_rel_path)

    return modified, new, deleted


def get_changed_files_from_git(
    source_path: Path,
    baseline_path: Path,
    baseline_prefix: str = "",
    detect_deletions: bool = False,
    filter_packaging: bool = True
) -> List[str]:
    """
    Detect changed files by comparing source against baseline.

    Args:
        source_path: Path to source (site module/core directory)
        baseline_path: Path to baseline checkout (repo root)
        baseline_prefix: Prefix for baseline paths (e.g., "core" for core)
        detect_deletions: Whether to detect deleted files (risky with composer)
        filter_packaging: Filter out packaging artifacts (LICENSE.txt, etc.)

    Returns:
        List of relative file paths (relative to source_path).
        Note: These are source-relative paths; use copy_changes_to_baseline
        with the same baseline_prefix to map them correctly.
    """
    changed = []

    # Compute baseline subdir to compare against
    if baseline_prefix:
        baseline_compare_path = baseline_path / baseline_prefix
    else:
        baseline_compare_path = baseline_path

    # Walk through source
    for root, dirs, files in os.walk(source_path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]

        for filename in files:
            if filename.startswith('.'):
                continue

            # Skip packaging artifacts
            if filter_packaging and is_packaging_artifact(filename):
                continue

            source_file = Path(root) / filename
            rel_path = source_file.relative_to(source_path)
            baseline_file = baseline_compare_path / rel_path

            if not baseline_file.exists():
                # New file
                changed.append(str(rel_path))
            else:
                # Check if content differs
                try:
                    source_content = source_file.read_bytes()
                    baseline_content = baseline_file.read_bytes()

                    if source_content != baseline_content:
                        # For .info.yml files, check if it's just packaging metadata
                        if filter_packaging and filename.endswith('.info.yml'):
                            # Generate a simple diff to check
                            source_lines = source_content.decode('utf-8', errors='replace').splitlines()
                            baseline_lines = baseline_content.decode('utf-8', errors='replace').splitlines()

                            # Create diff-style lines for checking
                            diff_lines = []
                            for line in baseline_lines:
                                if line not in source_lines:
                                    diff_lines.append(f"-{line}")
                            for line in source_lines:
                                if line not in baseline_lines:
                                    diff_lines.append(f"+{line}")

                            if is_info_yml_packaging_only(diff_lines):
                                continue  # Skip packaging-only changes

                        changed.append(str(rel_path))
                except OSError:
                    changed.append(str(rel_path))

    # Check for deleted files (disabled by default - risky with composer-installed trees)
    if detect_deletions and baseline_compare_path.exists():
        for root, dirs, files in os.walk(baseline_compare_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]

            for filename in files:
                if filename.startswith('.'):
                    continue

                # Skip packaging artifacts
                if filter_packaging and is_packaging_artifact(filename):
                    continue

                baseline_file = Path(root) / filename
                rel_path = baseline_file.relative_to(baseline_compare_path)
                source_file = source_path / rel_path

                if not source_file.exists():
                    changed.append(str(rel_path))

    return list(set(changed))


def generate_patch(
    baseline_path: Path,
    output_dir: Path,
    project: str,
    description: str,
    issue_number: Optional[int] = None,
    comment_number: Optional[int] = None,
    new_files: Optional[List[str]] = None,
    use_binary: bool = False,
    reduced_context: bool = False,
) -> PatchInfo:
    """
    Generate a local diff artifact from the baseline repository.

    Args:
        baseline_path: Path to baseline repo with changes applied
        output_dir: Directory to write diff artifact
        project: Project name
        description: Short description for filename
        issue_number: Issue number (optional)
        comment_number: Comment number (optional)
        new_files: List of new files to add with intent-to-add
        use_binary: Include binary files in diff
        reduced_context: Use reduced context (-U1) for .info.yml files

    Returns:
        PatchInfo with patch details
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Intent-to-add for new files so they appear in diff
    if new_files:
        for rel_path in new_files:
            try:
                subprocess.run(
                    ["git", "add", "-N", rel_path],
                    cwd=baseline_path,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                pass  # File might not exist or be already tracked

    # Generate diff
    diff_cmd = ["git", "diff"]

    if use_binary:
        diff_cmd.append("--binary")

    if reduced_context:
        diff_cmd.append("-U1")

    try:
        result = subprocess.run(
            diff_cmd,
            cwd=baseline_path,
            check=True,
            capture_output=True,
            text=True,
        )
        diff_content = result.stdout
    except subprocess.CalledProcessError as e:
        raise PatchError(f"Failed to generate diff: {e.stderr}")

    # Filter out packaging-only changes from .info.yml files
    diff_content = filter_packaging_from_diff(diff_content)

    if not diff_content.strip():
        raise PatchError("No changes detected - diff is empty (or only contains packaging metadata)")

    # Compute diffstat from the filtered diff content to avoid count drift.
    files_changed, insertions, deletions = compute_diffstat_from_patch(
        diff_content, baseline_path
    )

    # Generate filename
    filename = generate_patch_filename(project, description, issue_number, comment_number)
    patch_path = output_dir / filename

    # Write local diff artifact
    with open(patch_path, 'w', encoding='utf-8') as f:
        f.write(diff_content)

    # Collect warnings
    warnings = []

    # Get list of changed files
    changed_files = []
    for line in diff_content.split('\n'):
        if line.startswith('diff --git'):
            match = re.search(r'b/(.+)$', line)
            if match:
                changed_files.append(match.group(1))

    # Check for hack patterns
    hack_warnings = detect_hack_patterns(diff_content)
    warnings.extend([w.message for w in hack_warnings])

    # Check for problematic files
    file_warnings = detect_problematic_files(changed_files)
    warnings.extend([w.message for w in file_warnings])

    # Check scope
    scope_warnings = check_scope(changed_files, insertions, deletions)
    warnings.extend([w.message for w in scope_warnings])

    return PatchInfo(
        path=patch_path,
        filename=filename,
        project=project,
        description=description,
        issue_number=issue_number,
        comment_number=comment_number,
        files_changed=files_changed,
        insertions=insertions,
        deletions=deletions,
        warnings=warnings,
    )


def verify_patch_applies(patch_path: Path, baseline_path: Path) -> Tuple[bool, str]:
    """
    Verify that a diff/patch file applies cleanly to the baseline.

    Args:
        patch_path: Path to patch file
        baseline_path: Path to clean baseline checkout

    Returns:
        Tuple of (success, message)
    """
    try:
        result = subprocess.run(
            ["git", "apply", "--check", str(patch_path)],
            cwd=baseline_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, "Patch applies cleanly"
        else:
            return False, f"Patch does not apply: {result.stderr}"
    except subprocess.CalledProcessError as e:
        return False, f"Patch verification failed: {e.stderr}"
    except FileNotFoundError:
        return False, "git not found"

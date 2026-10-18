"""Find local Git work and contribution reports without changing them."""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlsplit

MAX_DIRECTORIES = 2000
MAX_FILE_BYTES = 1024 * 1024
GIT_TIMEOUT_SECONDS = 5
SKIP_DIRECTORIES = {
    ".git", ".hg", ".svn", ".bzr", "vendor", "node_modules", ".venv",
    "venv", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".cache", ".ddev",
}


def _warn(result: Dict, message: str) -> None:
    result["warnings"].append(message)
    result["incomplete"] = True


def _read_text(path: Path, result: Dict) -> Optional[str]:
    """Read a regular file within the size limit. Do not follow a file link."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open("rb") as handle:
            content = handle.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            _warn(result, f"File size limit reached: {path}")
            return None
        return content.decode("utf-8")
    except (OSError, UnicodeError):
        _warn(result, f"Could not read file: {path}")
        return None


def _git(repo: Path, args, result: Dict, allowed_codes=(0,), config_overrides=()) -> Optional[str]:
    """Run a local Git read. Do not refresh the index or fetch missing objects."""
    env = os.environ.copy()
    for name in list(env):
        if name.startswith("GIT_TRACE") or name in {
            "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_NAMESPACE", "GIT_CURL_VERBOSE",
        }:
            env.pop(name, None)
    env.update({
        "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1",
        "GIT_TERMINAL_PROMPT": "0", "GIT_ALLOW_PROTOCOL": "",
    })
    command = ["git", "--no-optional-locks", "--no-pager", "-c", "core.fsmonitor=false"]
    for setting in config_overrides:
        command.extend(["-c", setting])
    command.extend(args)
    try:
        process = subprocess.run(
            command, cwd=repo, env=env, capture_output=True, text=True,
            errors="replace", timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        _warn(result, f"Could not run Git {args[0]} within {GIT_TIMEOUT_SECONDS} seconds: {repo}")
        return None
    if process.returncode not in allowed_codes:
        # Git error text can contain a remote URL with credentials.
        _warn(result, f"Git {args[0]} failed with exit {process.returncode}: {repo}")
        return None
    return process.stdout


def _remote_matches(remote: str, project: str) -> bool:
    """Match Drupal project and issue-fork paths. Do not return remote URLs."""
    try:
        if "://" in remote:
            parsed = urlsplit(remote)
            if parsed.scheme not in {"http", "https", "ssh", "git"}:
                return False
            host, path = parsed.hostname, parsed.path
        else:
            match = re.fullmatch(r"(?:[^@/]+@)?([^/:]+):(.+)", remote)
            if not match:
                return False
            host, path = match.groups()
        if not host or host.lower() not in {"git.drupalcode.org", "git.drupal.org"}:
            return False
        path = path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path == f"project/{project}" or bool(
            re.fullmatch(rf"issue/{re.escape(project)}-[0-9]+", path)
        )
    except ValueError:
        return False


def _project_reason(repo: Path, project: str, result: Dict) -> Optional[str]:
    remotes = _git(repo, ["config", "--get-regexp", r"^remote\..*\.url$"], result, (0, 1))
    if remotes:
        for line in remotes.splitlines():
            fields = line.split(None, 1)
            if len(fields) == 2 and _remote_matches(fields[1], project):
                return "Drupal Git remote"
    composer = _read_text(repo / "composer.json", result)
    if composer is not None:
        try:
            package = json.loads(composer)
        except json.JSONDecodeError:
            _warn(result, f"Could not parse composer.json: {repo}")
            return None
        if isinstance(package, dict) and package.get("name") == f"drupal/{project}":
            return f"Composer package drupal/{project}"
    return None


def _status_entries(output: str):
    """Read porcelain records, including paths that contain newlines."""
    records = iter(output.rstrip("\0").split("\0")) if output else iter(())
    entries = []
    for record in records:
        if record[:2].strip() in {"R", "C"} or any(code in record[:2] for code in "RC"):
            previous_path = next(records, "")
            record = f"{record[:3]}{previous_path} -> {record[3:]}"
        entries.append(record)
    return entries


def _read_status(repo: Path, result: Dict) -> Optional[str]:
    worktree = _git(repo, ["rev-parse", "--show-toplevel"], result)
    if worktree is None:
        return None
    try:
        if Path(worktree.strip()).resolve() != repo.resolve():
            _warn(result, f"Status not read because Git uses a different worktree: {repo}")
            return None
    except (OSError, RuntimeError):
        _warn(result, f"Could not resolve the Git worktree: {repo}")
        return None

    # Reading a split index can update shared-index timestamps, even without locks.
    index = _git(repo, ["rev-parse", "--git-path", "index"], result)
    if index is None:
        return None
    index_path = Path(index.strip())
    if not index_path.is_absolute():
        index_path = repo / index_path
    try:
        if any(path.name.startswith("sharedindex.") for path in index_path.parent.iterdir()):
            _warn(result, f"Status not read because shared-index files are present; they may be stale: {repo}")
            return None
    except OSError:
        _warn(result, f"Could not inspect Git index directory: {repo}")
        return None

    # Status can run clean or process filters. Disable them before reading files.
    filter_keys = _git(repo, [
        "config", "--null", "--name-only", "--get-regexp", r"^filter\..*\.(clean|process|required)$",
    ], result, (0, 1))
    overrides = []
    if filter_keys is not None:
        for prefix in sorted({key.rsplit(".", 1)[0] for key in filter_keys.split("\0") if key}):
            overrides.extend([f"{prefix}.clean=", f"{prefix}.process=", f"{prefix}.required=false"])
        return _git(repo, ["status", "--porcelain=v1", "-z", "--untracked-files=normal", "--ignore-submodules=all"], result,
                    config_overrides=overrides)
    return None


def _repository(repo: Path, reason: str, issue: int, max_commits: int, result: Dict) -> Dict:
    branch = _git(repo, ["symbolic-ref", "--quiet", "--short", "HEAD"], result, (0, 1))
    head = _git(repo, ["rev-parse", "--verify", "--quiet", "HEAD"], result, (0, 1))
    status = _read_status(repo, result)
    entry = {
        "path": str(repo), "project_match": reason,
        "branch": branch.strip() if branch else None,
        "head": head.strip() if head else None,
        "dirty": bool(status) if status is not None else None,
        "status": _status_entries(status) if status is not None else [], "matches": [],
    }
    issue_token = re.compile(rf"(?<![A-Za-z0-9]){issue}(?![A-Za-z0-9])")
    branches = _git(repo, ["for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes"], result)
    if branches is not None:
        names = branches.splitlines()
        # An unborn branch has a symbolic HEAD, but no ref before its first commit.
        if entry["branch"] and entry["branch"] not in names:
            names.append(entry["branch"])
        for name in names:
            if issue_token.search(name):
                entry["matches"].append({
                    "kind": "branch", "value": name, "reason": "Issue number in branch name",
                })
    # Other refs can contain commits even when the current branch is unborn.
    commits = _git(repo, ["log", "--no-show-signature", "--all", f"-n{max_commits}", "--format=%h%x00%s"], result)
    if commits is not None:
        for line in commits.splitlines():
            commit, separator, subject = line.partition("\0")
            if separator and issue_token.search(subject):
                entry["matches"].append({
                    "kind": "commit", "value": f"{commit} {subject}",
                    "reason": "Issue number in commit subject",
                })
    return entry


def _report(path: Path, project: str, issue: int, result: Dict) -> Optional[Dict]:
    text = _read_text(path, result)
    if text is None:
        return None
    fields = {}
    for line in text.splitlines():
        if re.match(r"^\s{0,3}#{2,6}\s", line):
            break
        match = re.fullmatch(r"\s*\*\*(Project|Issue|Related Issue|Generated):\*\*\s*(.*?)\s*", line)
        if match:
            label, value = match.groups()
            if label in fields:
                return None  # Conflicting or repeated metadata is not evidence.
            fields[label] = value
    if fields.get("Project") != project:
        return None
    for label, kind in (("Issue", "issue"), ("Related Issue", "related_issue")):
        value = fields.get(label, "")
        link = re.fullmatch(r"\[[^\]]*\]\(([^)]+)\)", value)
        if link:
            value = link.group(1)
        try:
            url = urlsplit(value.strip("<>"))
            matches = (
                url.scheme in {"http", "https"}
                and url.hostname in {"www.drupal.org", "drupal.org"}
                and (url.path.rstrip("/") == f"/node/{issue}" or
                     url.path.rstrip("/") == f"/project/{project}/issues/{issue}")
            )
        except ValueError:
            matches = False
        if matches:
            report = {"path": str(path), "issue_kind": kind}
            if fields.get("Generated"):
                report["generated_at"] = fields["Generated"]
            return report
    return None


def search_context(
    scan_root: Path, project: str, issue: int, max_depth: int = 6,
    max_repos: int = 50, max_commits: int = 100,
) -> Dict:
    """Search only the specified directory. This function does not write files."""
    root = Path(scan_root)
    result = {
        "scan_root": str(root.absolute()), "project": project, "issue": issue,
        "limits": {"max_depth": max_depth, "max_repos": max_repos, "max_commits": max_commits,
                   "max_directories": MAX_DIRECTORIES, "max_file_bytes": MAX_FILE_BYTES,
                   "git_timeout_seconds": GIT_TIMEOUT_SECONDS},
        "repositories": [], "reports": [], "warnings": [], "incomplete": False,
    }
    if not isinstance(project, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", project):
        _warn(result, "Use a Drupal project machine name.")
        return result
    if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0:
        _warn(result, "Use a positive issue number.")
        return result
    if any(not isinstance(value, int) or isinstance(value, bool) or value < minimum for value, minimum in (
        (max_depth, 0), (max_repos, 1), (max_commits, 1),
    )):
        _warn(result, "Use a depth of zero or more and positive repository and commit limits.")
        return result
    try:
        root = root.expanduser()
        if root.is_symlink() or not root.is_dir():
            _warn(result, "The scan root must be an existing directory, not a symbolic link.")
            return result
        root = root.resolve()
    except (OSError, RuntimeError):
        _warn(result, "Could not resolve the scan root.")
        return result
    result["scan_root"] = str(root)
    visited = 0
    repositories_seen = 0
    repo_limit_reported = False

    def walk_error(error):
        _warn(result, f"Could not read directory: {error.filename}")

    for directory, dirs, files in os.walk(root, topdown=True, followlinks=False, onerror=walk_error):
        visited += 1
        if visited > MAX_DIRECTORIES:
            _warn(result, f"Directory limit reached: {MAX_DIRECTORIES}")
            break
        current = Path(directory)
        depth = len(current.relative_to(root).parts)
        try:
            dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRECTORIES and not (current / name).is_symlink())
            marker = current / ".git"
            is_repository = not marker.is_symlink() and (marker.is_dir() or marker.is_file())
        except OSError:
            _warn(result, f"Could not inspect directory: {current}")
            dirs[:] = []
            continue
        if depth >= max_depth:
            dirs[:] = []
        if is_repository:
            repositories_seen += 1
            if repositories_seen <= max_repos:
                reason = _project_reason(current, project, result)
                if reason:
                    result["repositories"].append(_repository(current, reason, issue, max_commits, result))
            elif not repo_limit_reported:
                _warn(result, f"Repository limit reached: {max_repos}")
                repo_limit_reported = True
        if "REPORT.md" in files:
            report = _report(current / "REPORT.md", project, issue, result)
            if report:
                result["reports"].append(report)
    return result

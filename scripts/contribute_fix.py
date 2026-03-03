#!/usr/bin/env python3
"""
drupal-contribute-fix: Upstream contribution helper for Drupal.

Searches drupal.org issue queue before generating local diffs, detects existing
fixes, and packages minimal upstream-acceptable contributions.

Exit codes:
    0  - PROCEED: MR artifacts + local diff generated
    10 - STOP: Existing upstream fix found
    20 - STOP: Fixed in newer upstream version
    30 - STOP: Analysis-only recommended
    40 - ERROR: Could not complete
    50 - STOP: Security-related issue detected
"""

import argparse
import os
import re
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# Add lib to path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
LIB_DIR = REPO_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

from drupalorg_api import DrupalOrgAPI, DrupalOrgAPIError, is_fixed_status, get_status_label, get_priority_label
from drupalorg_urls import build_project_issue_search_url
from issue_queue_integration import find_dorg_script
from issue_matcher import (
    IssueMatcher,
    IssueCandidate,
    determine_workflow_mode,
    WORKFLOW_MODE_MR,
    WORKFLOW_MODE_PATCH,
    WORKFLOW_MODE_NONE,
)
from baseline_repo import (
    detect_project_from_path,
    resolve_baseline,
    checkout_baseline,
    BaselineError,
)
from patch_packager import (
    copy_changes_to_baseline,
    get_changed_files_from_git,
    generate_patch,
    PatchError,
)
from security_detector import is_security_related, format_security_warning
from validator import validate_files
from report_writer import (
    create_report,
    write_candidates_json,
    write_report,
)


# Exit codes
EXIT_PROCEED = 0
EXIT_EXISTING_FIX = 10
EXIT_FIXED_UPSTREAM = 20
EXIT_ANALYSIS_ONLY = 30
EXIT_ERROR = 40
EXIT_SECURITY = 50


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Drupal upstream contribution helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Preflight command
    preflight = subparsers.add_parser(
        "preflight",
        help="Search upstream without generating local contribution artifacts",
    )
    preflight.add_argument(
        "--project", "-p",
        required=True,
        help="Drupal project machine name (e.g., metatag, drupal)",
    )
    preflight.add_argument(
        "--keywords", "-k",
        nargs="+",
        default=[],
        help="Search keywords (error messages, terms)",
    )
    preflight.add_argument(
        "--paths",
        nargs="+",
        default=[],
        help="Relevant file paths",
    )
    preflight.add_argument(
        "--out", "-o",
        default=".drupal-contribute-fix",
        help="Output directory (default: .drupal-contribute-fix)",
    )
    preflight.add_argument(
        "--offline",
        action="store_true",
        help="Use cached data only, don't make API requests",
    )
    preflight.add_argument(
        "--max-issues",
        type=int,
        default=200,
        help="Maximum issues to fetch for matching (default: 200)",
    )

    # Package command
    package = subparsers.add_parser(
        "package",
        help="Search upstream and generate contribution artifacts",
    )
    package.add_argument(
        "--root", "-r",
        type=Path,
        help="Drupal site root directory",
    )
    package.add_argument(
        "--changed-path", "-c",
        type=Path,
        required=True,
        help="Path to changed module/theme/core directory",
    )
    package.add_argument(
        "--project", "-p",
        help="Drupal project machine name (auto-detected if not provided)",
    )
    package.add_argument(
        "--keywords", "-k",
        nargs="+",
        default=[],
        help="Search keywords (error messages, terms)",
    )
    package.add_argument(
        "--description", "-d",
        default="fix",
        help="Short description for diff filename",
    )
    package.add_argument(
        "--issue", "-i",
        type=int,
        help="Known issue number (uses this issue for gatekeeper check)",
    )
    package.add_argument(
        "--out", "-o",
        default=".drupal-contribute-fix",
        help="Output directory (default: .drupal-contribute-fix)",
    )
    package.add_argument(
        "--offline",
        action="store_true",
        help="Use cached data only",
    )
    package.add_argument(
        "--force",
        action="store_true",
        help="Generate local diff artifact even if existing fix found",
    )
    package.add_argument(
        "--upstream-ref",
        help="Explicit git ref for baseline (overrides detection)",
    )
    package.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip code validation checks",
    )
    package.add_argument(
        "--detect-deletions",
        action="store_true",
        help="Detect deleted files (risky with Composer-installed trees)",
    )
    package.add_argument(
        "--max-issues",
        type=int,
        default=200,
        help="Maximum issues to fetch for matching",
    )
    package.add_argument(
        "--test-steps",
        nargs="+",
        required=True,
        help="Required. Specific test steps for the issue comment",
    )

    # Test command - generate RTBC-style comment for existing MR/diff
    test_cmd = subparsers.add_parser(
        "test",
        help="Generate a Tested-by/RTBC comment for an existing MR or diff artifact",
    )
    test_cmd.add_argument(
        "--issue", "-i",
        type=int,
        required=True,
        help="Issue number to test",
    )
    test_cmd.add_argument(
        "--tested-on",
        required=True,
        help="Environment tested on (e.g., 'Drupal 10.2, PHP 8.2')",
    )
    test_cmd.add_argument(
        "--result",
        choices=["pass", "fail", "partial"],
        required=True,
        help="Test result: pass (works), fail (broken), partial (works with caveats)",
    )
    test_cmd.add_argument(
        "--notes",
        help="Additional notes about the test",
    )
    test_cmd.add_argument(
        "--mr",
        help="Specific MR number tested (e.g., '42')",
    )
    test_cmd.add_argument(
        "--patch",
        help="Specific diff/patch filename tested",
    )
    test_cmd.add_argument(
        "--out", "-o",
        default=".drupal-contribute-fix",
        help="Output directory (default: .drupal-contribute-fix)",
    )

    # Reroll command - help reroll a patch for a different version
    reroll = subparsers.add_parser(
        "reroll",
        help="Reroll an existing patch for a different version/branch",
    )
    reroll.add_argument(
        "--issue", "-i",
        type=int,
        required=True,
        help="Issue number",
    )
    reroll.add_argument(
        "--patch-url",
        required=True,
        help="URL of the patch to reroll",
    )
    reroll.add_argument(
        "--target-ref",
        required=True,
        help="Target branch/ref for the reroll (e.g., '2.0.x')",
    )
    reroll.add_argument(
        "--project", "-p",
        help="Drupal project machine name (auto-detected from patch if not provided)",
    )
    reroll.add_argument(
        "--out", "-o",
        default=".drupal-contribute-fix",
        help="Output directory (default: .drupal-contribute-fix)",
    )

    return parser.parse_args()


def run_preflight(
    project: str,
    keywords: List[str],
    paths: List[str],
    output_dir: Path,
    offline: bool = False,
    max_issues: int = 200,
) -> Tuple[int, List[IssueCandidate], Optional[IssueCandidate], str]:
    """
    Run preflight check - search upstream for existing issues.

    Returns:
        Tuple of (exit_code, candidates, best_match, confidence)
    """
    print(f"Searching drupal.org issue queue for project: {project}")
    print(f"Manual keyword search (Drupal.org UI): {build_project_issue_search_url(project, keywords)}")
    print("Note: Drupal.org api-d7 does not support a `text=` filter (it returns HTTP 412).")

    api = DrupalOrgAPI(offline=offline)

    # Get project node ID
    try:
        project_nid = api.get_project_nid(project)
        if not project_nid:
            print(f"Error: Could not find project '{project}' on drupal.org")
            return EXIT_ERROR, [], None, "none"
    except DrupalOrgAPIError as e:
        print(f"API Error: {e}")
        return EXIT_ERROR, [], None, "none"

    print(f"Found project nid: {project_nid}")

    # Search for matching issues
    matcher = IssueMatcher(api)
    candidates = matcher.find_candidates(
        project_nid=project_nid,
        keywords=keywords,
        file_paths=paths,
        max_issues=max_issues,
    )

    best_match, confidence = matcher.get_best_match_confidence(candidates)

    print(f"\nFound {len(candidates)} relevant issues")
    if best_match:
        print(f"Best match: {best_match.title}")
        print(f"  URL: {best_match.url}")
        print(f"  Status: {best_match.status_label}")
        print(f"  Confidence: {confidence}")
        if best_match.has_mr:
            print(f"  Has MR(s): {', '.join(best_match.mr_urls)}")

        dorg_path = find_dorg_script(REPO_ROOT)
        if dorg_path:
            print(
                "\nOptional deep summary (drupal-issue-queue):\n"
                f"  python3 {dorg_path} --format md issue {best_match.nid} --mode summary --comments 10 --files-limit 0 --resolve-tags none --related-mrs"
            )
            if not offline:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                summary_path = output_dir / f"ISSUE_{best_match.nid}_SUMMARY.md"
                try:
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(dorg_path),
                            "--format",
                            "md",
                            "issue",
                            str(best_match.nid),
                            "--mode",
                            "summary",
                            "--comments",
                            "10",
                            "--files-limit",
                            "0",
                            "--resolve-tags",
                            "none",
                            "--related-mrs",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        summary_path.write_text(result.stdout, encoding="utf-8")
                        print(f"Saved issue summary: {summary_path}")
                    else:
                        print(
                            "Warning: drupal-issue-queue summary failed "
                            f"(exit {result.returncode}): {result.stderr.strip()}",
                            file=sys.stderr,
                        )
                except Exception as e:
                    print(f"Warning: drupal-issue-queue summary error: {e}", file=sys.stderr)
        else:
            print(
                "\nOptional deep summary (drupal-issue-queue skill):\n"
                f"  python scripts/dorg.py issue {best_match.nid} --format md\n"
                "  (run from the drupal-issue-queue directory)"
            )

    return EXIT_PROCEED, candidates, best_match, confidence


def check_existing_fix(
    candidates: List[IssueCandidate],
    best_match: Optional[IssueCandidate],
    confidence: str,
) -> Tuple[bool, str, str]:
    """
    Check if an existing fix likely exists, with workflow-aware logic.

    Per Drupal contribution workflow:
    - If issue is MR-based, recommend reviewing/updating the MR
    - If issue only has historical patch attachments, recommend opening/updating an MR
    - If issue is fixed, recommend using the existing fix

    Returns:
        Tuple of (should_stop, reason, workflow_mode)
    """
    if not best_match:
        return False, "", WORKFLOW_MODE_NONE

    workflow_mode = best_match.workflow_mode

    # Check if issue is already fixed (highest priority)
    if is_fixed_status(best_match.status) and confidence in ("high", "medium"):
        return True, f"Issue already fixed: {best_match.url}", workflow_mode

    # MR-based issue: recommend working via MR workflow
    if workflow_mode == WORKFLOW_MODE_MR and confidence in ("high", "medium"):
        mr_list = ', '.join(best_match.mr_urls[:3])  # Limit to first 3
        reason = (
            f"Issue is MR-based. Review/update the existing MR instead of creating a separate patch submission.\n"
            f"  Issue: {best_match.url}\n"
            f"  MR(s): {mr_list}\n\n"
            f"To test the MR locally, download as `.diff` or `.patch`:\n"
            f"  {best_match.mr_urls[0]}.diff (if available)\n\n"
            f"Note: Don't point Composer directly at MR URLs - download the file instead."
        )
        return True, reason, workflow_mode

    # Patch-only issue: recommend MR-first workflow going forward
    if workflow_mode == WORKFLOW_MODE_PATCH and confidence in ("high", "medium"):
        reason = (
            f"Issue has patch attachments but no active MR.\n"
            f"  Issue: {best_match.url}\n"
            f"  Existing patches: {len(best_match.patch_urls)} attached\n\n"
            f"For new work, use MR workflow: create/get push access to the issue fork, "
            f"push commits, and open/update a merge request."
        )
        return True, reason, workflow_mode

    # Check top candidates for fixed status
    for candidate in candidates[:5]:
        if is_fixed_status(candidate.status):
            return True, f"Related issue already fixed: {candidate.url}", candidate.workflow_mode

    return False, "", workflow_mode


def _extract_patch_urls_from_files(api: DrupalOrgAPI, files: List) -> List[str]:
    """Extract patch/diff URLs from file references."""
    patch_urls = []
    for file_ref in files or []:
        fid = None
        if isinstance(file_ref, dict):
            fid = file_ref.get("fid") or file_ref.get("id")
            if not fid and file_ref.get("url"):
                url = file_ref.get("url", "")
                if url.endswith((".patch", ".diff")):
                    patch_urls.append(url)
                continue
        elif isinstance(file_ref, (int, str)) and str(file_ref).isdigit():
            fid = int(file_ref)

        if fid:
            try:
                file_data = api.get_file(int(fid))
                filename = file_data.get("filename", "")
                url = file_data.get("url", "")
                if filename.endswith((".patch", ".diff")) and url:
                    patch_urls.append(url)
            except Exception:
                continue

    return patch_urls


def collect_patch_urls(api: DrupalOrgAPI, issue_nid: int, issue_data: dict) -> List[str]:
    """Collect patch URLs from issue node and comments."""
    urls = []

    # Node attachments (field_issue_files or legacy upload field)
    node_files = issue_data.get("field_issue_files") or issue_data.get("upload") or []
    urls.extend(_extract_patch_urls_from_files(api, node_files))

    # Comment attachments (most Drupal patches are here)
    try:
        comments = api.get_comments(issue_nid)
        for comment in comments:
            comment_files = comment.get("field_comment_upload") or comment.get("upload") or []
            urls.extend(_extract_patch_urls_from_files(api, comment_files))
    except Exception:
        pass

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            deduped.append(url)

    return deduped


def extract_mr_urls(related_mrs: List) -> List[str]:
    """Extract MR URLs from mixed related_mrs payloads (dicts and/or strings)."""
    urls = []
    for mr in related_mrs or []:
        if isinstance(mr, str):
            if mr:
                urls.append(mr)
            continue
        if isinstance(mr, dict):
            url = mr.get("url")
            if url:
                urls.append(url)

    seen = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def run_package(
    changed_path: Path,
    output_dir: Path,
    project: Optional[str] = None,
    site_root: Optional[Path] = None,
    keywords: List[str] = None,
    description: str = "fix",
    issue_number: Optional[int] = None,
    offline: bool = False,
    force: bool = False,
    upstream_ref: Optional[str] = None,
    skip_validation: bool = False,
    detect_deletions: bool = False,
    max_issues: int = 200,
    test_steps: List[str] = None,
) -> int:
    """
    Run full package workflow - search and generate MR-ready artifacts + local diff.

    Returns:
        Exit code
    """
    keywords = keywords or []
    test_steps = test_steps or []
    output_dir = Path(output_dir)
    changed_path = Path(changed_path).resolve()

    if not any(step.strip() for step in test_steps):
        print("Error: --test-steps is required and must include concrete steps.")
        return EXIT_ERROR

    # Detect site root if not provided
    if site_root is None:
        # Walk up to find composer.json
        current = changed_path
        while current != current.parent:
            if (current / "composer.json").exists():
                site_root = current
                break
            current = current.parent

    # Detect project from path
    if project is None:
        try:
            project, project_type = detect_project_from_path(
                str(changed_path),
                site_root or changed_path.parent
            )
            print(f"Detected project: {project} ({project_type})")
        except BaselineError as e:
            print(f"Error: {e}")
            return EXIT_ERROR
    else:
        # Determine project type from path
        path_str = str(changed_path).lower()
        if "/core/" in path_str or project == "drupal":
            project_type = "core"
        elif "/themes/" in path_str:
            project_type = "theme"
        else:
            project_type = "module"

    # Get list of files in the changed directory for keywords extraction
    file_paths = []
    if changed_path.is_dir():
        for root, dirs, files in os.walk(changed_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if not f.startswith('.'):
                    file_paths.append(os.path.relpath(os.path.join(root, f), changed_path))

    # Step 1: Run preflight or fetch known issue
    candidates = []
    best_match = None
    confidence = "none"

    api = DrupalOrgAPI(offline=offline)

    if issue_number is not None:
        # User provided a known issue - fetch it and run gatekeeper check
        print(f"Fetching issue #{issue_number}...")
        try:
            issue_data = api.get_issue(issue_number, include_mrs=True)
            if not issue_data:
                print(f"Warning: Could not fetch issue #{issue_number}")
            else:
                # Build an IssueCandidate from the issue data
                # Find MRs from issue detail
                related_mrs = issue_data.get("related_mrs", []) or []
                mr_urls = extract_mr_urls(related_mrs)
                has_mr = bool(mr_urls)

                # Find patches from node AND comments
                patch_urls = collect_patch_urls(api, issue_number, issue_data)
                has_patch = bool(patch_urls)

                status_code = issue_data.get("field_issue_status")
                priority_code = issue_data.get("field_issue_priority")
                best_match = IssueCandidate(
                    nid=issue_number,
                    title=issue_data.get("title", f"Issue #{issue_number}"),
                    url=f"https://www.drupal.org/node/{issue_number}",
                    status=int(status_code) if status_code else 0,
                    status_label=get_status_label(status_code),
                    priority=int(priority_code) if priority_code else 0,
                    priority_label=get_priority_label(priority_code),
                    has_mr=has_mr,
                    has_patch=has_patch,
                    mr_urls=mr_urls,
                    patch_urls=patch_urls,
                    workflow_mode=determine_workflow_mode(has_mr, has_patch),
                    score=100.0,  # High score since user explicitly chose this issue
                    score_breakdown={"user_specified": 100.0},
                )
                candidates = [best_match]
                confidence = "high"  # User specified = high confidence

                print(f"Issue: {best_match.title}")
                print(f"  Status: {best_match.status_label}")
                if has_mr:
                    print(f"  Has MR(s): {', '.join(mr_urls[:3])}")
                if has_patch:
                    print(f"  Has patches: {len(patch_urls)} attached")

        except DrupalOrgAPIError as e:
            print(f"Warning: Could not fetch issue: {e}")
    else:
        # No issue specified - run full preflight search
        exit_code, candidates, best_match, confidence = run_preflight(
            project=project,
            keywords=keywords,
            paths=file_paths[:10],  # Limit paths for search
            output_dir=output_dir,
            offline=offline,
            max_issues=max_issues,
        )

        if exit_code == EXIT_ERROR:
            return exit_code

    # Step 2: Check for existing fix (workflow-aware)
    # This runs for both preflight and known-issue cases
    should_stop, reason, workflow_mode = check_existing_fix(candidates, best_match, confidence)

    if should_stop and not force:
        if workflow_mode == WORKFLOW_MODE_MR:
            print(f"\n*** STOP: Issue is MR-based ***")
        elif workflow_mode == WORKFLOW_MODE_PATCH:
            print(f"\n*** STOP: Issue has historical patch attachments ***")
        else:
            print(f"\n*** STOP: Existing upstream fix found ***")

        print(f"\n{reason}")
        print("\nUse --force to override and generate a local diff artifact anyway.")

        # Still write report (into issue-specific directory)
        stop_issue_nid = issue_number or (best_match.nid if best_match else None)

        # Generate slug for directory name
        def slugify_stop(text: str, max_length: int = 40) -> str:
            slug = re.sub(r'[^a-z0-9]+', '-', text.lower())
            slug = slug.strip('-')
            if len(slug) > max_length:
                slug = slug[:max_length].rsplit('-', 1)[0]
            return slug

        stop_slug = slugify_stop(keywords[0]) if keywords else "fix"
        if stop_issue_nid:
            stop_issue_dir = f"{stop_issue_nid}-{stop_slug}"
        else:
            stop_issue_dir = f"unfiled-{stop_slug}"

        report = create_report(
            project=project,
            keywords=keywords,
            file_paths=file_paths,
            outcome="existing_fix",
            outcome_code=EXIT_EXISTING_FIX,
            outcome_reason=reason,
            candidates=candidates,
            best_match=best_match,
            best_match_confidence=confidence,
            # Even when we STOP, persist the test steps so the output artifact
            # can be used directly for follow-up comments/reviews.
            test_steps=test_steps if test_steps else None,
        )
        write_report(report, output_dir, issue_nid=stop_issue_nid, issue_dir_override=stop_issue_dir)
        print(f"\nArtifacts written to: {output_dir}/{stop_issue_dir}/")

        return EXIT_EXISTING_FIX

    # Step 3: Resolve baseline
    print(f"\nResolving baseline for {project}...")
    try:
        baseline = resolve_baseline(
            project_name=project,
            project_type=project_type,
            site_root=site_root,
            explicit_ref=upstream_ref,
        )
        print(f"Baseline: {baseline.git_url} @ {baseline.ref}")
        print(f"Source: {baseline.source}")
    except BaselineError as e:
        print(f"Error resolving baseline: {e}")
        return EXIT_ERROR

    # Step 4: Checkout baseline
    print("Cloning baseline repository...")
    work_dir = Path(tempfile.mkdtemp(prefix="drupal-contrib-"))
    try:
        baseline_path = checkout_baseline(baseline, work_dir)
        print(f"Checked out to: {baseline_path}")
    except BaselineError as e:
        print(f"Error checking out baseline: {e}")
        shutil.rmtree(work_dir, ignore_errors=True)
        return EXIT_ERROR

    # Step 5: Copy changes and detect modifications
    print("Analyzing changes...")
    source_path = changed_path

    # For core, the site has web/core but the baseline repo has core/ subdir
    # So we compare source files to baseline_path/core/
    if project_type == "core":
        baseline_prefix = "core"
    else:
        baseline_prefix = ""

    # Get changed files (paths are relative to source_path)
    changed_files = get_changed_files_from_git(
        source_path, baseline_path,
        baseline_prefix=baseline_prefix,
        detect_deletions=detect_deletions,
    )
    print(f"Changed files: {len(changed_files)}")

    if not changed_files:
        print("No changes detected.")
        shutil.rmtree(work_dir, ignore_errors=True)
        return EXIT_ERROR

    # Copy changes to baseline (applies baseline_prefix when writing)
    modified, new, deleted = copy_changes_to_baseline(
        source_path, baseline_path, changed_files, baseline_prefix=baseline_prefix
    )
    print(f"  Modified: {len(modified)}, New: {len(new)}, Deleted: {len(deleted)}")

    # Step 6: Security check
    print("\nChecking for security-related changes...")
    try:
        # Generate diff for security check
        import subprocess
        diff_result = subprocess.run(
            ["git", "diff"],
            cwd=baseline_path,
            capture_output=True,
            text=True,
        )
        diff_content = diff_result.stdout

        is_security, indicators = is_security_related(diff_content, changed_files)

        if is_security:
            print("\n*** STOP: Security-related changes detected ***")
            print(format_security_warning(indicators))

            report = create_report(
                project=project,
                keywords=keywords,
                file_paths=changed_files,
                outcome="security",
                outcome_code=EXIT_SECURITY,
                outcome_reason="Security-related changes detected. Follow Drupal Security Team process.",
                candidates=candidates,
                best_match=best_match,
                best_match_confidence=confidence,
                warnings=[i.description for i in indicators],
            )
            write_report(report, output_dir)
            shutil.rmtree(work_dir, ignore_errors=True)
            return EXIT_SECURITY

    except Exception as e:
        print(f"Warning: Security check failed: {e}")

    # Step 7: Determine issue number for directory structure
    # Use explicit issue_number, or best_match if high confidence, or "unfiled"
    effective_issue = issue_number or (best_match.nid if best_match and confidence in ("high", "medium") else None)

    # Generate slug from keywords for directory naming
    def slugify(text: str, max_length: int = 40) -> str:
        slug = re.sub(r'[^a-z0-9]+', '-', text.lower())
        slug = slug.strip('-')
        if len(slug) > max_length:
            slug = slug[:max_length].rsplit('-', 1)[0]
        return slug

    slug = slugify(keywords[0]) if keywords else "fix"
    if effective_issue:
        issue_dir_name = f"{effective_issue}-{slug}"
    else:
        issue_dir_name = f"unfiled-{slug}"

    # Generate local diff into issue-specific directory (flat structure)
    print("\nGenerating local diff artifact...")
    issue_dir = output_dir / issue_dir_name
    diffs_dir = issue_dir / "diffs"

    # Check for .info.yml files
    has_info_yml = any(f.endswith('.info.yml') for f in changed_files)

    try:
        patch_info = generate_patch(
            baseline_path=baseline_path,
            output_dir=diffs_dir,
            project=project,
            description=description,
            issue_number=effective_issue,
            new_files=new,
            reduced_context=has_info_yml,
        )
        print(f"Diff generated: {patch_info.filename}")
        print(f"  Files changed: {patch_info.files_changed}")
        print(f"  +{patch_info.insertions}/-{patch_info.deletions} lines")

        if patch_info.warnings:
            print("\nWarnings:")
            for warning in patch_info.warnings:
                print(f"  - {warning}")

    except PatchError as e:
        print(f"Error generating local diff artifact: {e}")
        shutil.rmtree(work_dir, ignore_errors=True)
        return EXIT_ERROR

    # Step 8: Validation
    validation_results = []
    if not skip_validation:
        print("\nRunning validation...")
        # Use modified + new which include baseline_prefix (e.g., core/ for core changes)
        files_to_validate = modified + new
        full_paths = [baseline_path / f for f in files_to_validate]
        validation_results = validate_files(full_paths)

        for result in validation_results:
            status = "PASSED" if result.passed else "FAILED"
            if result.not_run_reason:
                status = f"SKIPPED ({result.not_run_reason})"
            print(f"  {result.tool}: {status}")

    # Step 9: Write report
    print("\nWriting report...")

    # Determine outcome
    if patch_info.warnings and any("hack" in w.lower() for w in patch_info.warnings):
        outcome = "analysis_only"
        outcome_code = EXIT_ANALYSIS_ONLY
        outcome_reason = "Diff contains patterns that may need review. Consider posting analysis first."
    else:
        outcome = "proceed"
        outcome_code = EXIT_PROCEED
        outcome_reason = "Local diff artifact generated successfully for MR workflow."

    report = create_report(
        project=project,
        keywords=keywords,
        file_paths=changed_files,
        outcome=outcome,
        outcome_code=outcome_code,
        outcome_reason=outcome_reason,
        candidates=candidates,
        best_match=best_match,
        best_match_confidence=confidence,
        patch_info=patch_info,
        validation_results=validation_results,
        warnings=patch_info.warnings,
        test_steps=test_steps if test_steps else None,
    )

    paths = write_report(report, output_dir, issue_nid=effective_issue, issue_dir_override=issue_dir_name)
    print(f"\nArtifacts written to: {output_dir}/")
    print(f"  - {issue_dir_name}/REPORT.md")
    print(f"  - {issue_dir_name}/ISSUE_COMMENT.md")
    print(f"  - {issue_dir_name}/diffs/{patch_info.filename}")

    # Cleanup
    shutil.rmtree(work_dir, ignore_errors=True)

    return outcome_code


def run_test(
    issue_number: int,
    tested_on: str,
    result: str,
    output_dir: Path,
    notes: Optional[str] = None,
    mr_number: Optional[str] = None,
    patch_name: Optional[str] = None,
) -> int:
    """
    Generate a Tested-by/RTBC comment for an existing MR or diff artifact.

    Returns:
        Exit code (0 for success)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch issue details
    api = DrupalOrgAPI()
    print(f"Fetching issue #{issue_number}...")

    try:
        issue_data = api.get_issue(issue_number, include_mrs=True)
        if not issue_data:
            print(f"Error: Could not fetch issue #{issue_number}")
            return EXIT_ERROR
    except DrupalOrgAPIError as e:
        print(f"API Error: {e}")
        return EXIT_ERROR

    issue_title = issue_data.get("title", f"Issue #{issue_number}")
    issue_url = f"https://www.drupal.org/node/{issue_number}"

    # Determine what was tested
    if mr_number:
        tested_artifact = f"MR !{mr_number}"
    elif patch_name:
        tested_artifact = f"diff `{patch_name}`"
    else:
        # Try to auto-detect from issue
        related_mrs = issue_data.get("related_mrs", [])
        mr_urls = extract_mr_urls(related_mrs)
        if mr_urls:
            mr_url = mr_urls[0]
            mr_id = mr_url.split("/")[-1] if mr_url else "latest"
            tested_artifact = f"MR !{mr_id}"
        else:
            tested_artifact = "the latest diff/patch artifact"

    # Generate comment based on result
    lines = [
        "## Test Comment",
        "",
        f"**Issue:** [{issue_title}]({issue_url})",
        f"**Tested:** {tested_artifact}",
        f"**Environment:** {tested_on}",
        "",
        "---",
        "",
        "**Copy/paste this into the issue:**",
        "",
        "---",
        "",
    ]

    if result == "pass":
        lines.extend([
            f"### Tested {tested_artifact} - Works as expected",
            "",
            f"**Environment:** {tested_on}",
            "",
            "**Steps tested:**",
            "1. Applied the diff/checked out the MR",
            "2. [Describe what you tested]",
            "3. [Describe expected vs actual result]",
            "",
            "**Result:** The fix works correctly.",
            "",
        ])
        if notes:
            lines.extend([f"**Notes:** {notes}", ""])
        lines.extend([
            "RTBC+1 from my testing.",
            "",
        ])
    elif result == "fail":
        lines.extend([
            f"### Tested {tested_artifact} - Does NOT work",
            "",
            f"**Environment:** {tested_on}",
            "",
            "**Steps tested:**",
            "1. Applied the diff/checked out the MR",
            "2. [Describe what you tested]",
            "",
            "**Result:** The fix does not resolve the issue.",
            "",
            "**Error/behavior observed:**",
            "[Describe what went wrong]",
            "",
        ])
        if notes:
            lines.extend([f"**Notes:** {notes}", ""])
        lines.extend([
            "Setting back to \"Needs work\".",
            "",
        ])
    else:  # partial
        lines.extend([
            f"### Tested {tested_artifact} - Partial success",
            "",
            f"**Environment:** {tested_on}",
            "",
            "**Steps tested:**",
            "1. Applied the diff/checked out the MR",
            "2. [Describe what you tested]",
            "",
            "**Result:** The fix works with caveats.",
            "",
            "**What works:**",
            "- [List what works]",
            "",
            "**What doesn't work:**",
            "- [List issues]",
            "",
        ])
        if notes:
            lines.extend([f"**Notes:** {notes}", ""])

    comment_content = "\n".join(lines)

    # Write to file
    comment_path = output_dir / "TEST_COMMENT.md"
    with open(comment_path, 'w') as f:
        f.write(comment_content)

    print(f"\nTest comment generated: {comment_path}")
    print(f"\nResult: {result.upper()}")
    print(f"Tested: {tested_artifact}")
    print(f"Environment: {tested_on}")

    return EXIT_PROCEED


def run_reroll(
    issue_number: int,
    patch_url: str,
    target_ref: str,
    output_dir: Path,
    project: Optional[str] = None,
) -> int:
    """
    Reroll an existing patch for a different version/branch.

    Returns:
        Exit code
    """
    import urllib.request
    import re

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract project name from patch URL if not provided
    if not project:
        # Try to parse from URL like /project/metatag/...
        match = re.search(r'/project/([^/]+)/', patch_url)
        if match:
            project = match.group(1)
        else:
            # Try to parse from filename like metatag-fix-123.patch
            filename = patch_url.split('/')[-1]
            project = filename.split('-')[0]

    if not project:
        print("Error: Could not determine project name. Use --project to specify.")
        return EXIT_ERROR

    print(f"Rerolling patch for {project} to {target_ref}...")
    print(f"Original patch: {patch_url}")

    # Download the original patch
    print("\nDownloading original patch...")
    try:
        req = urllib.request.Request(
            patch_url,
            headers={'User-Agent': 'drupal-contribute-fix/1.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            original_patch = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error downloading patch: {e}")
        return EXIT_ERROR

    # Save original patch
    original_filename = patch_url.split('/')[-1]
    original_path = output_dir / f"original-{original_filename}"
    with open(original_path, 'w') as f:
        f.write(original_patch)
    print(f"Saved original: {original_path}")

    # Clone target branch
    print(f"\nCloning {project} @ {target_ref}...")
    work_dir = Path(tempfile.mkdtemp(prefix="drupal-reroll-"))

    try:
        baseline = resolve_baseline(
            project_name=project,
            project_type="module",  # Assume module for reroll
            explicit_ref=target_ref,
        )
        baseline_path = checkout_baseline(baseline, work_dir)
    except BaselineError as e:
        print(f"Error: {e}")
        shutil.rmtree(work_dir, ignore_errors=True)
        return EXIT_ERROR

    # Try to apply the patch
    print("\nAttempting to apply patch...")
    import subprocess

    apply_result = subprocess.run(
        ["git", "apply", "--check", str(original_path)],
        cwd=baseline_path,
        capture_output=True,
        text=True,
    )

    if apply_result.returncode == 0:
        print("Patch applies cleanly! No reroll needed.")
        print(f"\nYou can use the original patch as-is on {target_ref}.")

        # Generate comment
        lines = [
            "## Reroll Comment",
            "",
            f"**Issue:** https://www.drupal.org/node/{issue_number}",
            f"**Original patch:** {patch_url}",
            f"**Target branch:** {target_ref}",
            "",
            "---",
            "",
            "**Copy/paste this into the issue:**",
            "",
            "---",
            "",
            f"Tested the patch from #{issue_number} against `{target_ref}`.",
            "",
            "**Result:** Patch applies cleanly, no reroll needed.",
            "",
        ]
    else:
        print("Patch does not apply cleanly. Attempting 3-way merge...")

        # Try 3-way apply
        apply_3way = subprocess.run(
            ["git", "apply", "--3way", str(original_path)],
            cwd=baseline_path,
            capture_output=True,
            text=True,
        )

        if apply_3way.returncode == 0:
            print("Applied with 3-way merge.")

            # Generate the rerolled patch
            diff_result = subprocess.run(
                ["git", "diff"],
                cwd=baseline_path,
                capture_output=True,
                text=True,
            )

            # Save rerolled patch
            reroll_filename = f"{project}-reroll-{issue_number}-{target_ref.replace('/', '-')}.patch"
            reroll_path = output_dir / "patches" / reroll_filename
            reroll_path.parent.mkdir(parents=True, exist_ok=True)

            with open(reroll_path, 'w') as f:
                f.write(diff_result.stdout)

            print(f"\nRerolled patch: {reroll_path}")

            # Generate interdiff if possible
            lines = [
                "## Reroll Comment",
                "",
                f"**Issue:** https://www.drupal.org/node/{issue_number}",
                f"**Original patch:** {patch_url}",
                f"**Target branch:** {target_ref}",
                f"**Rerolled patch:** `{reroll_filename}`",
                "",
                "---",
                "",
                "**Copy/paste this into the issue:**",
                "",
                "---",
                "",
                f"### Reroll for {target_ref}",
                "",
                f"The patch from comment #[X] did not apply cleanly to `{target_ref}`.",
                "",
                f"Attached is a rerolled version (`{reroll_filename}`).",
                "",
                "**Changes from original:**",
                "- [Describe any manual conflict resolution]",
                "",
            ]
        else:
            print("\nPatch requires manual conflict resolution.")
            print(f"Conflicts:\n{apply_3way.stderr}")

            lines = [
                "## Reroll Required (Manual)",
                "",
                f"**Issue:** https://www.drupal.org/node/{issue_number}",
                f"**Original patch:** {patch_url}",
                f"**Target branch:** {target_ref}",
                "",
                "The patch could not be automatically rerolled.",
                "",
                "**Conflicts:**",
                "```",
                apply_3way.stderr[:1000],
                "```",
                "",
                "Manual resolution required.",
            ]

    comment_content = "\n".join(lines)
    comment_path = output_dir / "REROLL_COMMENT.md"
    with open(comment_path, 'w') as f:
        f.write(comment_content)

    print(f"\nReroll comment: {comment_path}")

    # Cleanup
    shutil.rmtree(work_dir, ignore_errors=True)

    return EXIT_PROCEED


def main():
    """Main entry point."""
    args = parse_args()

    if args.command == "preflight":
        exit_code, candidates, best_match, confidence = run_preflight(
            project=args.project,
            keywords=args.keywords,
            paths=args.paths,
            output_dir=Path(args.out),
            offline=args.offline,
            max_issues=args.max_issues,
        )

        # Write candidates JSON only - no report folder for preflight
        # Preflight is just a search; issue folders are only created by `package`
        output_dir = Path(args.out)
        write_candidates_json(candidates, output_dir)

        # Check for existing fix (workflow-aware)
        should_stop, reason, workflow_mode = check_existing_fix(candidates, best_match, confidence)
        if should_stop:
            if workflow_mode == WORKFLOW_MODE_MR:
                print(f"\n*** Issue is MR-based - review existing MR ***")
            elif workflow_mode == WORKFLOW_MODE_PATCH:
                print(f"\n*** Issue has historical patches - use MR workflow going forward ***")
            else:
                print(f"\n*** Existing fix likely exists ***")
            print(f"\n{reason}")
            sys.exit(EXIT_EXISTING_FIX)

        sys.exit(exit_code)

    elif args.command == "package":
        exit_code = run_package(
            changed_path=args.changed_path,
            output_dir=Path(args.out),
            project=args.project,
            site_root=args.root,
            keywords=args.keywords,
            description=args.description,
            issue_number=args.issue,
            offline=args.offline,
            force=args.force,
            upstream_ref=args.upstream_ref,
            skip_validation=args.skip_validation,
            detect_deletions=args.detect_deletions,
            max_issues=args.max_issues,
            test_steps=args.test_steps,
        )
        sys.exit(exit_code)

    elif args.command == "test":
        exit_code = run_test(
            issue_number=args.issue,
            tested_on=args.tested_on,
            result=args.result,
            output_dir=Path(args.out),
            notes=args.notes,
            mr_number=args.mr,
            patch_name=args.patch,
        )
        sys.exit(exit_code)

    elif args.command == "reroll":
        exit_code = run_reroll(
            issue_number=args.issue,
            patch_url=args.patch_url,
            target_ref=args.target_ref,
            output_dir=Path(args.out),
            project=args.project,
        )
        sys.exit(exit_code)


if __name__ == "__main__":
    main()

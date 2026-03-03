"""
Report generation for contribution artifacts.

Generates REPORT.md, ISSUE_COMMENT.md, and UPSTREAM_CANDIDATES.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

try:
    from .issue_matcher import (
        IssueCandidate,
        WORKFLOW_MODE_MR,
        WORKFLOW_MODE_PATCH,
        WORKFLOW_MODE_NONE,
    )
    from .patch_packager import PatchInfo
except ImportError:
    from issue_matcher import (
        IssueCandidate,
        WORKFLOW_MODE_MR,
        WORKFLOW_MODE_PATCH,
        WORKFLOW_MODE_NONE,
    )
    from patch_packager import PatchInfo


@dataclass
class ValidationResult:
    """Result of a validation check."""
    tool: str
    command: str
    passed: bool
    output: str
    not_run_reason: Optional[str] = None


@dataclass
class HackDetection:
    """Results of hack pattern detection."""
    no_hardcoded_ids: bool = True
    no_raw_sql: bool = True
    no_superglobals: bool = True
    no_di_violations: bool = True
    no_cache_bypasses: bool = True
    no_error_suppression: bool = True
    detected_issues: List[str] = None

    def __post_init__(self):
        if self.detected_issues is None:
            self.detected_issues = []

    def all_passed(self) -> bool:
        return all([
            self.no_hardcoded_ids,
            self.no_raw_sql,
            self.no_superglobals,
            self.no_di_violations,
            self.no_cache_bypasses,
            self.no_error_suppression,
        ])


@dataclass
class ContributionReport:
    """Full contribution report data."""
    project: str
    keywords: List[str]
    file_paths: List[str]
    outcome: str
    outcome_code: int
    outcome_reason: str
    candidates: List[IssueCandidate]
    best_match: Optional[IssueCandidate]
    best_match_confidence: str
    patch_info: Optional[PatchInfo]
    validation_results: List[ValidationResult]
    nice_to_haves: List[str]
    warnings: List[str]
    generated_at: str
    hack_detection: Optional[HackDetection] = None
    dev_branch: Optional[str] = None
    dev_branch_has_bug: Optional[bool] = None
    test_steps: Optional[List[str]] = None  # Agent-provided test steps


def format_outcome_description(outcome_code: int) -> str:
    """Get description for an outcome code."""
    descriptions = {
        0: "PROCEED - MR artifacts + local diff generated",
        10: "STOP - Existing upstream fix found",
        20: "STOP - Fixed in newer upstream version",
        30: "STOP - Analysis-only contribution recommended",
        40: "ERROR - Could not complete",
        50: "STOP - Security-related issue detected",
    }
    return descriptions.get(outcome_code, f"Unknown outcome ({outcome_code})")


def _workflow_mode_label(workflow_mode: str) -> str:
    """Human-friendly label for the workflow mode."""
    if workflow_mode == WORKFLOW_MODE_MR:
        return "MR-based"
    if workflow_mode == WORKFLOW_MODE_PATCH:
        return "Historical patches"
    return "None"


def _generate_workflow_note(report: "ContributionReport", issue_url: Optional[str]) -> List[str]:
    """
    Generate workflow guidance with MR-first recommendations.

    This is included in REPORT.md and also written as WORKFLOW.md so future agents
    can quickly determine the intended contribution workflow.
    """
    best = report.best_match
    mode = best.workflow_mode if best else WORKFLOW_MODE_NONE
    label = _workflow_mode_label(mode)

    lines: List[str] = [
        f"- **Workflow mode:** {label}",
    ]
    if issue_url:
        lines.append(f"- **Issue:** {issue_url}")

    if best and best.mr_urls:
        lines.append("- **MRs:**")
        for url in best.mr_urls:
            lines.append(f"  - {url}")

    if best and best.patch_urls:
        lines.append(f"- **Existing diff/patch attachments:** {len(best.patch_urls)} attached")

    lines.append("")
    lines.append("**Guidance:**")
    if mode == WORKFLOW_MODE_MR:
        lines.extend([
            "- Work in GitLab (update the existing MR/issue fork branch).",
            "- Do NOT upload new patch files to the Drupal.org issue unless maintainers explicitly request it.",
            "- Keep generated `.diff` artifacts local for review/reference.",
        ])
    elif mode == WORKFLOW_MODE_PATCH:
        lines.extend([
            "- Issue has historical patch attachments but no active MR.",
            "- For new work, use MR workflow: create/update the issue fork branch and open/update an MR.",
            "- Treat historical patch attachments as context, not the primary submission path.",
        ])
    else:
        lines.extend([
            "- No upstream artifacts detected; default to MR workflow (issue fork + MR).",
            "- Keep generated `.diff` artifacts local for review/reference.",
        ])

    # If a local diff was generated via --force on an MR-based issue, make that explicit.
    if report.patch_info and mode == WORKFLOW_MODE_MR:
        lines.extend([
            "",
            "**Note:** A local `.diff` artifact was generated with `--force` even though this is an MR-based issue.",
            "Treat the `.diff` as a review artifact only (do not upload unless asked).",
        ])

    return lines


def _generate_workflow_markdown(report: "ContributionReport", issue_url: Optional[str]) -> str:
    """Generate WORKFLOW.md content."""
    lines = [
        "# Workflow",
        "",
    ]
    lines.extend(_generate_workflow_note(report, issue_url))
    lines.append("")
    return "\n".join(lines)


def _find_local_ci_logs(issue_dir: Path) -> List[Path]:
    """Return local CI log files stored in the issue artifact directory."""
    ci_dir = issue_dir / "ci"
    if not ci_dir.exists():
        return []
    return sorted([p for p in ci_dir.rglob("*.log") if p.is_file()])


def _generate_local_ci_parity_markdown(ci_logs: List[Path]) -> str:
    """Generate LOCAL_CI_PARITY_YYYY-MM-DD.md scaffold content."""
    lines = [
        "# Local CI Parity",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        "- Scope: [branch/MR + baseline]",
        "- Overall result: [pass/fail/incomplete]",
        "- Blocking jobs: [none or list]",
        "",
        "## Commands",
        "",
        "1. `[exact command]`",
        "   - Exit status: `[code]`",
        "   - Notes: `[key output or reason for failure]`",
        "",
        "## Job Outcomes",
        "",
        "| Job | Result | Notes |",
        "|-----|--------|-------|",
        "| [job-name] | [pass/fail/not run] | [details] |",
        "",
        "## Logs",
        "",
    ]
    for path in ci_logs:
        lines.append(f"- `{path.as_posix()}`")
    lines.extend([
        "",
        "## Notes",
        "",
        "- Keep this file and `ci/*.log` local-only unless a maintainer asks for details.",
    ])
    return "\n".join(lines)


def _ensure_local_ci_parity_file(issue_dir: Path) -> Optional[Path]:
    """
    Create a LOCAL_CI_PARITY scaffold when local CI logs already exist.

    Returns path to the parity file when logs are present and a file exists/was created.
    """
    ci_logs = _find_local_ci_logs(issue_dir)
    if not ci_logs:
        return None

    existing = sorted(issue_dir.glob("LOCAL_CI_PARITY_*.md"))
    if existing:
        return existing[-1]

    date_suffix = datetime.now().strftime("%Y-%m-%d")
    parity_path = issue_dir / f"LOCAL_CI_PARITY_{date_suffix}.md"
    relative_logs = [path.relative_to(issue_dir) for path in ci_logs]
    parity_markdown = _generate_local_ci_parity_markdown(relative_logs)

    with open(parity_path, "w") as f:
        f.write(parity_markdown)

    return parity_path


def generate_report_markdown(report: ContributionReport, issue_nid: Optional[int] = None) -> str:
    """Generate REPORT.md content."""
    lines = [
        "# Drupal Contribution Analysis Report",
        "",
        "> **IMPORTANT:** This skill does NOT post to drupal.org on your behalf.",
        "> You must manually create issues, open/update MRs, and post comments.",
        "",
        f"**Generated:** {report.generated_at}",
        f"**Project:** {report.project}",
    ]

    if issue_nid:
        lines.append(f"**Issue:** https://www.drupal.org/node/{issue_nid}")
    elif report.best_match:
        lines.append(f"**Related Issue:** {report.best_match.url}")
    else:
        lines.append("**Issue:** None found - you will need to create a new issue")

    lines.extend([
        "",
        "---",
        "",
        "## Outcome",
        "",
        f"**{format_outcome_description(report.outcome_code)}**",
        "",
        f"{report.outcome_reason}",
        "",
    ])

    # Always record which workflow we should be using (MR-first guidance).
    issue_url = None
    if issue_nid:
        issue_url = f"https://www.drupal.org/node/{issue_nid}"
    elif report.best_match:
        issue_url = report.best_match.url

    lines.extend([
        "---",
        "",
        "## Workflow",
        "",
    ])
    lines.extend(_generate_workflow_note(report, issue_url))
    lines.append("")

    # Upstream search results
    lines.extend([
        "---",
        "",
        "## Upstream Issue Search",
        "",
        f"**Keywords:** {', '.join(report.keywords) if report.keywords else 'None'}",
        "",
        f"**File paths:** {', '.join(report.file_paths) if report.file_paths else 'None'}",
        "",
    ])

    if report.candidates:
        lines.extend([
            "### Top Candidates",
            "",
        ])

        for i, c in enumerate(report.candidates[:10], 1):
            # Show workflow mode indicator
            if c.workflow_mode == WORKFLOW_MODE_MR:
                workflow_info = " **[MR-based]**"
            elif c.workflow_mode == WORKFLOW_MODE_PATCH:
                workflow_info = " **[Historical patches]**"
            else:
                workflow_info = ""

            lines.append(f"{i}. [{c.title}]({c.url})")
            lines.append(f"   - Status: {c.status_label}{workflow_info}")
            lines.append(f"   - Score: {c.score:.1f}")
            if c.mr_urls:
                lines.append(f"   - MRs: {', '.join(c.mr_urls)}")
            if c.patch_urls:
                lines.append(f"   - Diff/Patch attachments: {len(c.patch_urls)}")
            lines.append("")
    else:
        lines.extend([
            "No matching issues found in upstream issue queue.",
            "",
        ])

    # Best match analysis
    if report.best_match:
        # Determine workflow mode label
        if report.best_match.workflow_mode == WORKFLOW_MODE_MR:
            workflow_label = "MR-based"
        elif report.best_match.workflow_mode == WORKFLOW_MODE_PATCH:
            workflow_label = "Historical patches (MR recommended)"
        else:
            workflow_label = "No existing artifacts"

        lines.extend([
            "### Best Match Analysis",
            "",
            f"**Issue:** [{report.best_match.title}]({report.best_match.url})",
            "",
            f"**Confidence:** {report.best_match_confidence}",
            "",
            f"**Workflow Mode:** {workflow_label}",
            "",
            "**Score breakdown:**",
            "",
        ])
        for factor, points in report.best_match.score_breakdown.items():
            lines.append(f"- {factor}: +{points:.1f}")
        lines.append("")

        if report.best_match.has_mr:
            lines.extend([
                "**Existing MRs:**",
                "",
            ])
            for mr_url in report.best_match.mr_urls:
                lines.append(f"- {mr_url}")
            lines.append("")

            # Add MR download instructions
            lines.extend([
                "**How to test the MR locally:**",
                "",
                "Download as `.diff`/`.patch` (don't point Composer directly at MR URLs):",
                "```bash",
                f"curl -L -o mr.diff {report.best_match.mr_urls[0]}.diff",
                "git apply mr.diff",
                "```",
                "",
                "Note: MR diff/patch URLs change as commits are added. Download the file rather than",
                "referencing the URL directly in composer.json.",
                "",
            ])

        if report.best_match.has_patch and report.best_match.patch_urls:
            lines.extend([
                "**Existing diff/patch attachments:**",
                "",
            ])
            for patch_url in report.best_match.patch_urls[:3]:  # Limit to first 3
                lines.append(f"- {patch_url}")
            lines.append("")

    # Dev branch verification (if available)
    if report.dev_branch:
        lines.extend([
            "### Dev Branch Verification",
            "",
            f"- **Checked Branch:** `{report.dev_branch}`",
        ])
        if report.dev_branch_has_bug is True:
            lines.append("- **Result:** Bug EXISTS in dev (file matches broken local version)")
        elif report.dev_branch_has_bug is False:
            lines.append("- **Result:** Bug FIXED in dev (consider upgrading instead)")
        else:
            lines.append("- **Result:** Unable to verify")
        lines.append("")

    # Local diff artifact information
    if report.patch_info:
        lines.extend([
            "---",
            "",
            "## Generated Local Diff",
            "",
            f"**Filename:** `{report.patch_info.filename}`",
            "",
            f"**Location:** `{report.patch_info.path}`",
            "",
            "**Diffstat:**",
            "",
            f"- Files changed: {report.patch_info.files_changed}",
            f"- Insertions: +{report.patch_info.insertions}",
            f"- Deletions: -{report.patch_info.deletions}",
            "",
        ])

        # Hack detection checklist
        if report.hack_detection:
            hd = report.hack_detection
            lines.extend([
                "### Hack Detection",
                "",
            ])
            lines.append(f"- [{'x' if hd.no_hardcoded_ids else ' '}] No hardcoded IDs")
            lines.append(f"- [{'x' if hd.no_raw_sql else ' '}] No raw SQL")
            lines.append(f"- [{'x' if hd.no_superglobals else ' '}] No direct `$_GET/$_POST` access")
            lines.append(f"- [{'x' if hd.no_di_violations else ' '}] No dependency injection violations")
            lines.append(f"- [{'x' if hd.no_cache_bypasses else ' '}] No cache bypasses")
            lines.append(f"- [{'x' if hd.no_error_suppression else ' '}] No error suppression (`@`)")
            lines.append("")

            if hd.detected_issues:
                lines.append("**Issues detected:**")
                lines.append("")
                for issue in hd.detected_issues:
                    lines.append(f"- {issue}")
                lines.append("")

        if report.patch_info.warnings:
            lines.extend([
                "### Warnings",
                "",
            ])
            for warning in report.patch_info.warnings:
                lines.append(f"- {warning}")
            lines.append("")

    # Validation results
    lines.extend([
        "---",
        "",
        "## Validation Results",
        "",
    ])

    if report.validation_results:
        for result in report.validation_results:
            status = "PASSED" if result.passed else "FAILED"
            if result.not_run_reason:
                status = f"NOT RUN ({result.not_run_reason})"

            lines.append(f"### {result.tool}")
            lines.append("")
            lines.append(f"**Status:** {status}")
            lines.append("")
            lines.append(f"**Command:** `{result.command}`")
            lines.append("")
            if result.output:
                lines.append("**Output:**")
                lines.append("```")
                lines.append(result.output[:2000])  # Limit output
                lines.append("```")
            lines.append("")
    else:
        lines.append("No validation checks were run.")
        lines.append("")

    # Warnings
    if report.warnings:
        lines.extend([
            "---",
            "",
            "## Warnings",
            "",
        ])
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    # Nice-to-haves
    if report.nice_to_haves:
        lines.extend([
            "---",
            "",
            "## Nice-to-haves (Not Included in Diff)",
            "",
            "The following improvements were identified but excluded from the diff",
            "to keep the contribution focused:",
            "",
        ])
        for item in report.nice_to_haves:
            lines.append(f"- {item}")
        lines.append("")

    # Next steps - ALWAYS show this section when a local diff artifact exists
    if report.patch_info:
        manual_target = "drupal.org."
        if report.best_match and report.best_match.has_mr:
            manual_target = "drupal.org and GitLab."
        lines.extend([
            "---",
            "",
            "## What To Do Next (Manual Steps Required)",
            "",
            "> **This skill does NOT file issues or post comments automatically.**",
            f"> You must complete these steps yourself on {manual_target}",
            "",
        ])

        if report.best_match:
            if report.best_match.has_mr:
                mr_url = report.best_match.mr_urls[0] if report.best_match.mr_urls else "existing MR"
                mr_id = mr_url.split('/')[-1] if report.best_match.mr_urls else "existing MR"
                lines.extend([
                    f"1. **Go to the issue:** {report.best_match.url}",
                    f"2. **Review the existing MR ({mr_id}):** {mr_url}",
                    "3. **Copy/paste comment** - Use the text from `ISSUE_COMMENT.md` for testing/review notes",
                    "4. **If code changes are needed:** push commits to the issue fork branch used by the MR",
                    f"5. **Local review artifact:** `diffs/{report.patch_info.filename}` (do not upload unless maintainers ask)",
                ])
            else:
                lines.extend([
                    f"1. **Go to the issue:** {report.best_match.url}",
                    "2. **Read recent comments** - Understand context before posting",
                    "3. **Get/create issue fork + branch** - Prepare an MR branch for this issue",
                    "4. **Push your commits and open/update MR**",
                    "5. **Copy/paste comment** - Use the text from `ISSUE_COMMENT.md`",
                    f"6. **Local review artifact:** `diffs/{report.patch_info.filename}` (keep local unless asked)",
                ])
        else:
            # No existing issue found - user needs to create one
            lines.extend([
                "**No existing issue was found.** You need to create a new issue first:",
                "",
                f"1. **Go to:** https://www.drupal.org/project/issues/{report.project}",
                "2. **Click \"Create a new issue\"**",
                f"3. **Title/description:** Use `ISSUE_COMMENT.md` as the template (suggested title: `{report.keywords[0][:60] if report.keywords else 'Describe the bug'}`)",
                "4. **Create issue fork and branch** from the new issue page",
                "5. **Push your commits and open an MR** from the issue fork",
                f"6. **Local review artifact:** `diffs/{report.patch_info.filename}` (keep local unless asked)",
                "",
                "The `ISSUE_COMMENT.md` file contains a complete issue template you can use.",
            ])
        lines.append("")

    # Next steps for STOPPED workflows (MR or historical patch attachments).
    if not report.patch_info and report.outcome_code == 10 and report.best_match:
        lines.extend([
            "---",
            "",
            "## What To Do Next (Manual Steps Required)",
            "",
            "> **This skill does NOT post to drupal.org or GitLab on your behalf.**",
            "> You must complete these steps yourself.",
            "",
        ])

        if report.best_match.workflow_mode == WORKFLOW_MODE_MR and report.best_match.mr_urls:
            mr_url = report.best_match.mr_urls[0]
            lines.extend([
                f"1. **Go to the issue:** {report.best_match.url}",
                f"2. **Review the existing MR:** {mr_url}",
                "3. **Test the MR locally** and add a Tested-by/RTBC comment",
                "4. **If changes are needed:** push commits to the issue fork branch used by the MR",
                "",
                "Tip: You can download the MR as a `.diff` for local testing:",
                "```bash",
                f"curl -L -o mr.diff {mr_url}.diff",
                "git apply mr.diff",
                "```",
                "",
            ])
        elif report.best_match.workflow_mode == WORKFLOW_MODE_PATCH and report.best_match.patch_urls:
            lines.extend([
                f"1. **Go to the issue:** {report.best_match.url}",
                "2. **Use existing attachments as context** and switch to MR workflow",
                "3. **Create/get push access to the issue fork branch**",
                "4. **Push commits and open/update an MR**",
                "5. **Post a comment** using `ISSUE_COMMENT.md` as a starting point",
                "",
            ])
        else:
            lines.extend([
                "1. Review the issue and proceed with MR workflow.",
                "2. Post a comment with your findings and next steps.",
                "",
            ])

    # Footer
    lines.extend([
        "---",
        "",
        "*Generated with [drupal-contribute-fix](https://github.com/drupal-contribute-fix)*",
    ])

    return "\n".join(lines)


def generate_issue_comment(report: ContributionReport, is_new_issue: bool = False) -> str:
    """Generate paste-ready drupal.org issue comment (Submission Kit)."""
    lines = []

    # Generate a description from keywords
    if report.keywords:
        # Clean up keywords for description
        keyword_desc = report.keywords[0]
        # Truncate long error messages
        if len(keyword_desc) > 80:
            keyword_desc = keyword_desc[:77] + "..."
    else:
        keyword_desc = "the reported issue"

    # If we STOP due to an existing upstream artifact, generate a workflow-specific
    # comment template rather than a generic "analysis-only" stub.
    if report.outcome_code == 10 and report.best_match:
        best = report.best_match
        workflow_label = _workflow_mode_label(best.workflow_mode)

        lines.extend([
            "## Workflow Note",
            "",
            f"**Workflow:** {workflow_label}",
            f"**Issue:** {best.url}",
            "",
        ])

        if best.workflow_mode == WORKFLOW_MODE_MR and best.mr_urls:
            lines.extend([
                "This issue is **MR-based**. I focused on reviewing/testing the existing MR rather than uploading a patch.",
                "",
                "**MR(s):**",
            ])
            for url in best.mr_urls:
                lines.append(f"- {url}")
            lines.extend([
                "",
                "**Testing performed:**",
                "- [EDIT: add exact commands + results]",
                "",
                "**Notes:**",
                "- [EDIT: what you observed; any feedback for the MR author/maintainer]",
                "",
                "**AI disclosure:**",
                "- AI assistance used. Output reviewed by me and tests above were run by me.",
                "",
            ])
            return "\n".join(lines)

        if best.workflow_mode == WORKFLOW_MODE_PATCH and best.patch_urls:
            lines.extend([
                "This issue has **historical patch attachments** and no active MR.",
                "Recommended next step: switch to MR workflow for any new work and keep old attachments as context.",
                "",
                "**Existing diff/patch attachments:**",
            ])
            for url in best.patch_urls[:5]:
                lines.append(f"- {url}")
            lines.extend([
                "",
                "**Testing performed:**",
                "- [EDIT: add exact commands + results]",
                "",
                "**AI disclosure:**",
                "- AI assistance used. Output reviewed by me and tests above were run by me.",
                "",
            ])
            return "\n".join(lines)

    # For new issues (no matching upstream issue), generate a full issue template
    if is_new_issue and report.patch_info:
        lines.extend([
            "## New Issue Template",
            "",
            "> **No existing issue was found on drupal.org.**",
            "> Create a new issue and paste this content.",
            "",
            "---",
            "",
            "### Suggested Issue Title",
            "",
            f"`{keyword_desc}`",
            "",
            "(Edit this to be more descriptive)",
            "",
            "---",
            "",
            "### Issue Description (copy/paste below)",
            "",
            "---",
            "",
            "## Problem/Motivation",
            "",
            f"When {keyword_desc}, an error occurs.",
            "",
            "[EDIT: Describe the problem in more detail]",
            "",
            "## Steps to reproduce",
            "",
        ])

        # Use agent-provided test steps or placeholder
        if report.test_steps:
            for i, step in enumerate(report.test_steps, 1):
                lines.append(f"{i}. {step}")
        else:
            lines.extend([
                "> **TODO:** Agent must provide specific test steps.",
                "",
                "1. [Describe setup]",
                "2. [Trigger the bug]",
                f"3. Observe error: `{keyword_desc}`",
            ])

        lines.extend([
            "",
            "## Proposed resolution",
            "",
        ])

        # Describe what the proposed change does based on file paths
        if report.file_paths:
            php_files = [f for f in report.file_paths if f.endswith('.php')]
            if php_files:
                lines.append(f"The proposed change modifies `{php_files[0]}` to handle this case.")
            else:
                lines.append("The proposed change addresses this issue.")
        else:
            lines.append("The proposed change addresses this issue.")

        lines.extend([
            "",
            "[EDIT: Explain your approach]",
            "",
            "## Remaining tasks",
            "",
            "- [ ] Create issue fork + branch",
            "- [ ] Push commits and open MR",
            "- [ ] Test on different environments",
            "- [ ] Add/update tests if needed",
            "",
            f"**Local diff artifact:** `diffs/{report.patch_info.filename}`",
            "",
            "---",
            "",
        ])

        return "\n".join(lines)

    # Title suggestion - for existing issues
    if report.patch_info:
        lines.extend([
            "## Submission Kit",
            "",
            "> **REMINDER:** You must manually post this to drupal.org.",
            "> This skill does NOT create issues or post comments for you.",
            "",
            "**Copy/paste the text below into a new comment on the issue:**",
            "",
            "---",
            "",
        ])

        # Context about existing artifacts - only reference if high/medium confidence
        has_confident_match = (
            report.best_match and
            report.best_match_confidence in ("high", "medium")
        )
        is_mr_workflow = (
            has_confident_match and
            report.best_match and
            report.best_match.workflow_mode == WORKFLOW_MODE_MR
        )

        if is_mr_workflow:
            lines.append("### MR follow-up/testing")
            lines.append("")
        # Comment title - use keywords for better description
        elif report.keywords:
            lines.append(f"### MR Update: {keyword_desc}")
            lines.append("")
        else:
            lines.append("### Proposed fix")
            lines.append("")

        if has_confident_match and report.best_match.has_mr:
            mr_ref = report.best_match.mr_urls[0].split('/')[-1] if report.best_match.mr_urls else "existing MR"
            lines.extend([
                f"I encountered this issue locally and reviewed {mr_ref}.",
                "",
                "**MR workflow note:** This issue is MR-based, so I focused on reviewing/testing",
                "the existing MR workflow instead of uploading a patch by default.",
                "",
                "**If additional changes are needed:** [EDIT THIS - describe commits pushed to the MR branch]",
                "",
            ])
        elif has_confident_match and report.best_match.has_patch:
            lines.extend([
                "I encountered this issue locally and reviewed the existing diff/patch attachments.",
                "",
                "**MR workflow note:** I prepared this as MR-first work and kept attachments as context only.",
                "",
                "**If additional changes are needed:** [EDIT THIS - describe commits pushed to the MR branch]",
                "",
            ])
        else:
            lines.extend([
                f"I encountered `{keyword_desc}` and prepared an MR-first fix for review.",
                "",
            ])

        # Generate better description from context
        if is_mr_workflow:
            lines.extend([
                f"**Local review artifact (not uploaded by default):** `diffs/{report.patch_info.filename}`",
                "",
                "Only upload a patch if maintainers explicitly request patch workflow on the issue.",
                "",
                "**What this local artifact demonstrates:**",
            ])
        else:
            lines.extend([
                f"**Local diff artifact:** `diffs/{report.patch_info.filename}`",
                "",
                "**What this change does:**",
            ])

        # Try to infer what the change does from file paths and keywords
        if report.file_paths:
            main_file = report.file_paths[0] if report.file_paths else "the affected file"
            lines.append(f"- Fixes {keyword_desc} in `{main_file}`")
        else:
            lines.append(f"- Addresses: {keyword_desc}")

        lines.extend([
            "- [EDIT: Add any additional details about your approach]",
            "",
        ])

        # Scope summary
        lines.extend([
            "<details>",
            "<summary>Scope of changes</summary>",
            "",
            f"- {report.patch_info.files_changed} file(s) modified",
            f"- +{report.patch_info.insertions}/-{report.patch_info.deletions} lines",
        ])
        if report.file_paths:
            lines.append("")
            lines.append("Files changed:")
            for fp in report.file_paths[:5]:
                lines.append(f"- `{fp}`")
        lines.extend([
            "",
            "</details>",
            "",
        ])

        # Testing steps - use agent-provided steps or show placeholder
        lines.extend([
            "**Steps to test:**",
        ])

        if report.test_steps:
            # Use agent-provided test steps
            for i, step in enumerate(report.test_steps, 1):
                lines.append(f"{i}. {step}")
        else:
            # Placeholder - agent should fill this in
            lines.extend([
                "",
                "> **TODO:** Agent must provide specific test steps before submission.",
                "> Generic steps are not acceptable for drupal.org.",
                "",
                "Example format:",
                "1. Enable the MCP module with Update module disabled",
                "2. Call the `general:status` tool via MCP endpoint",
                "3. Before fix: Fatal error `Call to undefined function update_get_available()`",
                "4. After fix: JSON response with `status: unavailable`",
            ])
        lines.append("")

    else:
        # Analysis-only comment
        lines.extend([
            "## Submission Kit (Analysis Only)",
            "",
            "**Copy/paste this into a new comment on the issue:**",
            "",
            "---",
            "",
            "### Analysis",
            "",
            "After investigating this issue, here are my findings:",
            "",
            "- [Finding 1]",
            "- [Finding 2]",
            "",
            "### Suggested Approach",
            "",
            "[Recommendation for how to proceed]",
            "",
        ])

    # Footer
    lines.extend([
        "---",
        "",
    ])

    return "\n".join(lines)


def generate_candidates_json(candidates: List[IssueCandidate]) -> str:
    """Generate UPSTREAM_CANDIDATES.json content."""
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(candidates),
        "candidates": [c.to_dict() for c in candidates],
    }
    return json.dumps(data, indent=2)


def write_candidates_json(candidates: List[IssueCandidate], output_dir: Path) -> Path:
    """
    Write just the UPSTREAM_CANDIDATES.json file.

    Used by preflight to cache search results without creating issue folders.

    Args:
        candidates: List of issue candidates
        output_dir: Base output directory

    Returns:
        Path to the written file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates_json = generate_candidates_json(candidates)
    candidates_path = output_dir / "UPSTREAM_CANDIDATES.json"
    with open(candidates_path, 'w') as f:
        f.write(candidates_json)

    return candidates_path


def slugify(text: str, max_length: int = 40) -> str:
    """Convert text to a URL-friendly slug."""
    import re
    # Convert to lowercase, replace non-alphanumeric with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower())
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    # Truncate to max length, avoiding mid-word cuts
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit('-', 1)[0]
    return slug


def write_report(
    report: ContributionReport,
    output_dir: Path,
    issue_nid: Optional[int] = None,
    issue_dir_override: Optional[str] = None,
) -> Dict[str, Path]:
    """
    Write all report files to the output directory.

    Files are organized into issue-specific subdirectories to support
    multiple issue artifacts per session:

        .drupal-contribute-fix/
        ├── UPSTREAM_CANDIDATES.json      # Shared across all issues
        ├── 3541839-fix-metatag-build/    # Known issue with slug
        │   ├── ISSUE_COMMENT.md
        │   └── diffs/
        │       └── project-fix-3541839.diff
        └── unfiled-update-module-check/  # No issue found - new issue needed
            ├── ISSUE_COMMENT.md
            └── diffs/
                └── project-fix-new.diff

    Args:
        report: ContributionReport data
        output_dir: Base output directory
        issue_nid: Known issue number (uses "unfiled" if None and no best_match)
        issue_dir_override: Explicit directory name (overrides auto-generation)

    Returns:
        Dict mapping file type to path
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate slug from keywords or description
    if report.keywords:
        slug = slugify(report.keywords[0])
    else:
        slug = slugify(report.outcome_reason[:50] if report.outcome_reason else "fix")

    # Determine issue directory name
    # Priority: explicit override > issue_nid > best_match > "unfiled"
    # Format: {nid}-{slug} or unfiled-{slug}
    if issue_dir_override:
        issue_dir_name = issue_dir_override
    elif issue_nid:
        issue_dir_name = f"{issue_nid}-{slug}"
    elif report.best_match:
        issue_dir_name = f"{report.best_match.nid}-{slug}"
    else:
        issue_dir_name = f"unfiled-{slug}"

    # Create issue-specific subdirectory (flat, not under issues/)
    issue_dir = output_dir / issue_dir_name
    issue_dir.mkdir(parents=True, exist_ok=True)

    paths = {}

    # REPORT.md - in issue directory
    report_md = generate_report_markdown(
        report,
        issue_nid=issue_nid or (report.best_match.nid if report.best_match else None),
    )
    report_path = issue_dir / "REPORT.md"
    with open(report_path, 'w') as f:
        f.write(report_md)
    paths["report"] = report_path

    # UPSTREAM_CANDIDATES.json - stays at root (shared across issues)
    candidates_json = generate_candidates_json(report.candidates)
    candidates_path = output_dir / "UPSTREAM_CANDIDATES.json"
    with open(candidates_path, 'w') as f:
        f.write(candidates_json)
    paths["candidates"] = candidates_path

    # ISSUE_COMMENT.md - in issue directory
    # Determine if this is a new issue (unfiled = no existing issue found)
    is_new_issue = issue_dir_name.startswith("unfiled-")
    comment_md = generate_issue_comment(report, is_new_issue=is_new_issue)
    comment_path = issue_dir / "ISSUE_COMMENT.md"
    with open(comment_path, 'w') as f:
        f.write(comment_md)
    paths["comment"] = comment_path

    # WORKFLOW.md - quick at-a-glance workflow note (MR-first guidance).
    issue_url = None
    if issue_nid:
        issue_url = f"https://www.drupal.org/node/{issue_nid}"
    elif report.best_match:
        issue_url = report.best_match.url
    workflow_md = _generate_workflow_markdown(report, issue_url)
    workflow_path = issue_dir / "WORKFLOW.md"
    with open(workflow_path, 'w') as f:
        f.write(workflow_md)
    paths["workflow"] = workflow_path

    # LOCAL_CI_PARITY_YYYY-MM-DD.md - generated only when local CI logs exist.
    local_ci_parity_path = _ensure_local_ci_parity_file(issue_dir)
    if local_ci_parity_path:
        paths["local_ci_parity"] = local_ci_parity_path

    # Return the issue directory for external artifact generation
    paths["issue_dir"] = issue_dir

    return paths


def create_report(
    project: str,
    keywords: List[str],
    file_paths: List[str],
    outcome: str,
    outcome_code: int,
    outcome_reason: str,
    candidates: List[IssueCandidate],
    best_match: Optional[IssueCandidate],
    best_match_confidence: str,
    patch_info: Optional[PatchInfo] = None,
    validation_results: Optional[List[ValidationResult]] = None,
    nice_to_haves: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
    hack_detection: Optional[HackDetection] = None,
    dev_branch: Optional[str] = None,
    dev_branch_has_bug: Optional[bool] = None,
    test_steps: Optional[List[str]] = None,
) -> ContributionReport:
    """Create a ContributionReport instance."""
    return ContributionReport(
        project=project,
        keywords=keywords,
        file_paths=file_paths,
        outcome=outcome,
        outcome_code=outcome_code,
        outcome_reason=outcome_reason,
        candidates=candidates,
        best_match=best_match,
        best_match_confidence=best_match_confidence,
        patch_info=patch_info,
        validation_results=validation_results or [],
        nice_to_haves=nice_to_haves or [],
        warnings=warnings or [],
        generated_at=datetime.now(timezone.utc).isoformat(),
        hack_detection=hack_detection,
        dev_branch=dev_branch,
        dev_branch_has_bug=dev_branch_has_bug,
        test_steps=test_steps,
    )

"""
Issue matching and scoring for finding relevant Drupal.org issues.

Scores issues based on keyword overlap, file paths, recency, and status.
"""

import re
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field

try:
    from .drupalorg_api import (
        DrupalOrgAPI,
        get_status_label,
        get_priority_label,
        is_actionable_status,
        has_existing_fix,
        ISSUE_STATUS,
    )
except ImportError:
    from drupalorg_api import (
        DrupalOrgAPI,
        get_status_label,
        get_priority_label,
        is_actionable_status,
        has_existing_fix,
        ISSUE_STATUS,
    )


# Workflow modes for Drupal issues
WORKFLOW_MODE_MR = "mr"          # Issue has MRs - work via MR workflow
WORKFLOW_MODE_PATCH = "patch"    # Issue has patches - stay in patch mode
WORKFLOW_MODE_NONE = "none"      # Issue has neither - either approach is valid


@dataclass
class IssueCandidate:
    """A scored issue candidate."""
    nid: int
    title: str
    url: str
    status: int
    status_label: str
    priority: int
    priority_label: str
    score: float
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    has_mr: bool = False
    has_patch: bool = False
    mr_urls: List[str] = field(default_factory=list)
    patch_urls: List[str] = field(default_factory=list)
    changed: Optional[str] = None
    workflow_mode: str = WORKFLOW_MODE_NONE

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "nid": self.nid,
            "title": self.title,
            "url": self.url,
            "status": self.status,
            "status_label": self.status_label,
            "priority": self.priority,
            "priority_label": self.priority_label,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "has_mr": self.has_mr,
            "has_patch": self.has_patch,
            "mr_urls": self.mr_urls,
            "patch_urls": self.patch_urls,
            "workflow_mode": self.workflow_mode,
            "changed": self.changed,
        }


def determine_workflow_mode(has_mr: bool, has_patch: bool) -> str:
    """
    Determine the workflow mode for an issue.

    Per Drupal docs:
    - If MRs exist, the issue is MR-based (preferred workflow)
    - If patches exist but no MRs, stay in patch mode
    - If neither exists, either approach is valid

    MR takes precedence because it's the recommended workflow.
    """
    if has_mr:
        return WORKFLOW_MODE_MR
    elif has_patch:
        return WORKFLOW_MODE_PATCH
    else:
        return WORKFLOW_MODE_NONE


class IssueMatcher:
    """Matches and scores issues against search criteria."""

    # Scoring weights
    # NOTE: File path alone should NOT be enough for high confidence.
    # Keyword matches are critical for relevance.
    WEIGHTS = {
        "keyword_exact_title": 50,      # Exact keyword match in title (PRIMARY)
        "keyword_partial_title": 25,    # Partial keyword match in title
        "keyword_body": 15,             # Keyword in body/summary
        "file_path_match": 15,          # File path mentioned (REDUCED - too many false positives)
        "class_name_match": 20,         # Class name mentioned
        "function_name_match": 25,      # Function name mentioned (INCREASED - more specific)
        "recency_30_days": 10,          # Changed in last 30 days
        "recency_90_days": 5,           # Changed in last 90 days
        "recency_180_days": 2,          # Changed in last 180 days
        "status_needs_review": 5,       # Status: needs review
        "status_rtbc": 10,              # Status: RTBC
        "status_active": 3,             # Status: active
        "has_mr": 8,                    # Has merge request
        "has_patch_attachment": 5,      # Has patch attachment
    }

    def __init__(self, api: DrupalOrgAPI):
        """
        Initialize the matcher.

        Args:
            api: Drupal.org API client
        """
        self.api = api

    def _tokenize(self, text: str) -> Set[str]:
        """Extract tokens from text for matching."""
        # Lowercase and split on non-word characters
        tokens = set(re.split(r'\W+', text.lower()))
        # Remove empty and very short tokens
        return {t for t in tokens if len(t) > 2}

    def _extract_class_names(self, text: str) -> Set[str]:
        """Extract potential class names from text (CamelCase patterns)."""
        # Match CamelCase patterns
        pattern = r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b'
        matches = re.findall(pattern, text)
        return set(matches)

    def _extract_function_names(self, text: str) -> Set[str]:
        """Extract potential function names from text."""
        # Match function-like patterns: word followed by ()
        pattern = r'\b(\w+)\s*\(\)'
        matches = re.findall(pattern, text)
        # Also match snake_case patterns
        snake_pattern = r'\b([a-z]+(?:_[a-z]+)+)\b'
        matches.extend(re.findall(snake_pattern, text))
        return set(matches)

    def _extract_file_names(self, paths: List[str]) -> Set[str]:
        """Extract file names from paths."""
        names = set()
        for path in paths:
            # Get basename
            name = os.path.basename(path)
            names.add(name)
            # Also add without extension
            name_no_ext = os.path.splitext(name)[0]
            names.add(name_no_ext)
        return names

    def _days_since_changed(self, issue: Dict) -> int:
        """Calculate days since issue was changed."""
        changed = issue.get("changed")
        if not changed:
            return 365  # Assume old if no date

        try:
            # Drupal.org returns Unix timestamp
            changed_ts = int(changed)
            changed_dt = datetime.fromtimestamp(changed_ts, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - changed_dt
            return delta.days
        except (ValueError, TypeError):
            return 365

    def _score_issue(self, issue: Dict, keywords: List[str],
                     file_paths: List[str], class_names: Set[str],
                     function_names: Set[str]) -> Tuple[float, Dict[str, float]]:
        """
        Score an issue against search criteria.

        Returns:
            Tuple of (total_score, score_breakdown)
        """
        breakdown = {}
        title = issue.get("title", "").lower()
        body = issue.get("body", {})
        if isinstance(body, dict):
            body_text = body.get("value", "").lower()
        else:
            body_text = str(body).lower()

        title_tokens = self._tokenize(title)
        file_names = self._extract_file_names(file_paths)

        # Keyword matching
        for keyword in keywords:
            kw_lower = keyword.lower()
            kw_tokens = self._tokenize(keyword)

            # Exact phrase in title
            if kw_lower in title:
                breakdown["keyword_exact_title"] = breakdown.get("keyword_exact_title", 0) + self.WEIGHTS["keyword_exact_title"]

            # Token overlap in title
            elif kw_tokens & title_tokens:
                overlap = len(kw_tokens & title_tokens) / len(kw_tokens) if kw_tokens else 0
                breakdown["keyword_partial_title"] = breakdown.get("keyword_partial_title", 0) + (self.WEIGHTS["keyword_partial_title"] * overlap)

            # Keyword in body
            if kw_lower in body_text:
                breakdown["keyword_body"] = breakdown.get("keyword_body", 0) + self.WEIGHTS["keyword_body"]

        # File path matching
        for file_name in file_names:
            if file_name.lower() in title or file_name.lower() in body_text:
                breakdown["file_path_match"] = breakdown.get("file_path_match", 0) + self.WEIGHTS["file_path_match"]
                break  # Only count once

        # Class name matching
        for class_name in class_names:
            if class_name.lower() in title or class_name.lower() in body_text:
                breakdown["class_name_match"] = breakdown.get("class_name_match", 0) + self.WEIGHTS["class_name_match"]
                break

        # Function name matching
        for func_name in function_names:
            if func_name.lower() in title or func_name.lower() in body_text:
                breakdown["function_name_match"] = breakdown.get("function_name_match", 0) + self.WEIGHTS["function_name_match"]
                break

        # Recency scoring
        days = self._days_since_changed(issue)
        if days <= 30:
            breakdown["recency"] = self.WEIGHTS["recency_30_days"]
        elif days <= 90:
            breakdown["recency"] = self.WEIGHTS["recency_90_days"]
        elif days <= 180:
            breakdown["recency"] = self.WEIGHTS["recency_180_days"]

        # Status scoring
        status = issue.get("field_issue_status")
        if status == 8:  # Needs review
            breakdown["status"] = self.WEIGHTS["status_needs_review"]
        elif status == 14:  # RTBC
            breakdown["status"] = self.WEIGHTS["status_rtbc"]
        elif status == 1:  # Active
            breakdown["status"] = self.WEIGHTS["status_active"]

        # MR/patch bonuses
        if issue.get("related_mrs"):
            breakdown["has_mr"] = self.WEIGHTS["has_mr"]

        total = sum(breakdown.values())
        return total, breakdown

    def _get_patch_urls_from_files(self, files: List) -> List[str]:
        """Extract patch/diff URLs from a list of file references."""
        patch_urls = []
        for file_ref in files:
            if isinstance(file_ref, dict):
                fid = file_ref.get("fid") or file_ref.get("id")
                if fid:
                    try:
                        file_data = self.api.get_file(int(fid))
                        filename = file_data.get("filename", "")
                        if filename.endswith((".patch", ".diff")):
                            url = file_data.get("url", "")
                            if url:
                                patch_urls.append(url)
                    except Exception:
                        continue
        return patch_urls

    def _find_all_patch_attachments(self, issue_nid: int, issue_detail: Optional[Dict] = None) -> List[str]:
        """
        Find all patch attachments for an issue (node AND comment attachments).

        This is important because most Drupal patches are uploaded as comment
        attachments, not node attachments.

        Args:
            issue_nid: Issue node ID
            issue_detail: Optional pre-fetched issue detail

        Returns:
            List of patch URLs
        """
        patch_urls = []

        try:
            # Get issue detail if not provided
            if issue_detail is None:
                issue_detail = self.api.get_issue(issue_nid)

            # Check node attachments (field_issue_files)
            node_files = issue_detail.get("field_issue_files", [])
            patch_urls.extend(self._get_patch_urls_from_files(node_files))

            # Check comment attachments - this is where most patches are!
            try:
                comments = self.api.get_comments(issue_nid)
                for comment in comments:
                    # Comments can have file attachments too
                    comment_files = comment.get("field_comment_upload", [])
                    if comment_files:
                        patch_urls.extend(self._get_patch_urls_from_files(comment_files))
            except Exception:
                pass  # Comments fetch failed, continue with what we have

        except Exception:
            pass

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in patch_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _enrich_candidate(self, candidate: IssueCandidate) -> None:
        """
        Enrich a candidate with full issue details (MRs, patches).

        This fetches the issue detail with related_mrs=1 and checks both
        node and comment attachments for patches. This is necessary because
        the issue list response doesn't include MR data.

        Args:
            candidate: IssueCandidate to enrich (modified in place)
        """
        try:
            # Fetch full issue detail with MR data
            issue_detail = self.api.get_issue(candidate.nid, include_mrs=True)

            # Get MR URLs from enriched response
            related_mrs = issue_detail.get("related_mrs", [])
            if related_mrs:
                candidate.mr_urls = [mr.get("url") for mr in related_mrs if mr.get("url")]
                candidate.has_mr = bool(candidate.mr_urls)

            # Get patch URLs from node AND comment attachments
            candidate.patch_urls = self._find_all_patch_attachments(
                candidate.nid, issue_detail=issue_detail
            )
            candidate.has_patch = bool(candidate.patch_urls)

            # Now determine workflow mode with accurate data
            candidate.workflow_mode = determine_workflow_mode(
                candidate.has_mr, candidate.has_patch
            )

        except Exception:
            # If enrichment fails, leave candidate as-is
            pass

    def find_candidates(self, project_nid: int, keywords: List[str],
                       file_paths: Optional[List[str]] = None,
                       max_issues: int = 200,
                       top_n: int = 10) -> List[IssueCandidate]:
        """
        Find and score candidate issues.

        Args:
            project_nid: Project node ID
            keywords: Search keywords (error messages, terms)
            file_paths: Relevant file paths
            max_issues: Maximum issues to fetch for scoring
            top_n: Number of top candidates to return

        Returns:
            List of scored IssueCandidate objects
        """
        file_paths = file_paths or []

        # Extract class and function names from keywords
        class_names = set()
        function_names = set()
        for kw in keywords:
            class_names.update(self._extract_class_names(kw))
            function_names.update(self._extract_function_names(kw))

        # Also extract from file paths
        for path in file_paths:
            basename = os.path.basename(path)
            name_no_ext = os.path.splitext(basename)[0]
            class_names.add(name_no_ext)

        # Fetch issues
        issues = self.api.fetch_issues_batch(project_nid, max_issues=max_issues)

        # Score all issues
        scored = []
        for issue in issues:
            score, breakdown = self._score_issue(
                issue, keywords, file_paths, class_names, function_names
            )

            if score > 0:  # Only include issues with some relevance
                nid = issue.get("nid")
                status = issue.get("field_issue_status", 0)
                priority = issue.get("field_issue_priority", 200)

                # Note: We don't try to get MRs from the list response because
                # it doesn't include them. MR/patch data is fetched later via
                # _enrich_candidate() for top candidates only.

                candidate = IssueCandidate(
                    nid=nid,
                    title=issue.get("title", ""),
                    url=f"https://www.drupal.org/node/{nid}",
                    status=status,
                    status_label=get_status_label(status),
                    priority=priority,
                    priority_label=get_priority_label(priority),
                    score=score,
                    score_breakdown=breakdown,
                    changed=issue.get("changed"),
                    # MR/patch fields will be populated by _enrich_candidate
                )
                scored.append(candidate)

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)

        # Get top candidates and enrich with full issue details
        # This fetches MRs (via related_mrs=1) and patches (from node AND comments)
        # Only do this for top N since it requires additional API calls
        top_candidates = scored[:top_n]
        for candidate in top_candidates[:7]:  # Enrich top 7 candidates
            self._enrich_candidate(candidate)

        return top_candidates

    def get_best_match_confidence(self, candidates: List[IssueCandidate]) -> Tuple[Optional[IssueCandidate], str]:
        """
        Determine confidence level for best match.

        IMPORTANT: Requires EXACT keyword match or function match for high/medium
        confidence. Partial keyword matches (token overlap) are not enough.
        File path matches alone can cause false positives (e.g., "General.php"
        matches many unrelated issues).

        Args:
            candidates: List of scored candidates

        Returns:
            Tuple of (best_candidate, confidence_level)
            confidence_level is one of: "high", "medium", "low", "none"
        """
        if not candidates:
            return None, "none"

        best = candidates[0]
        breakdown = best.score_breakdown

        # Check keyword relevance levels (not just file path)
        has_exact_keyword_match = breakdown.get("keyword_exact_title", 0) > 0
        has_any_keyword_match = any(
            k.startswith("keyword_") and v > 0
            for k, v in breakdown.items()
        )
        has_function_match = breakdown.get("function_name_match", 0) > 0

        # Without any keyword/function match, cap confidence at "low"
        # This prevents false positives from file path matches alone
        # (e.g., "General.php" matching many unrelated issues)
        if not has_any_keyword_match and not has_function_match:
            return best, "low"

        # High confidence: score >= 60 and significantly higher than second
        # AND has exact keyword match or function match
        if best.score >= 60 and (has_exact_keyword_match or has_function_match):
            if len(candidates) == 1 or best.score > candidates[1].score * 1.5:
                return best, "high"

        # Medium confidence: score >= 40 WITH exact keyword match or function match
        # Partial keyword matches alone (e.g., token overlap) are not enough
        if best.score >= 40 and (has_exact_keyword_match or has_function_match):
            return best, "medium"

        # Low confidence: score >= 20
        if best.score >= 20:
            return best, "low"

        return best, "low"


def format_candidates_summary(candidates: List[IssueCandidate]) -> str:
    """Format candidates as a human-readable summary."""
    if not candidates:
        return "No matching issues found."

    lines = ["## Upstream Issue Candidates\n"]

    for i, c in enumerate(candidates, 1):
        status_info = f"[{c.status_label}]"

        # Show workflow mode indicator
        if c.workflow_mode == WORKFLOW_MODE_MR:
            workflow_info = " **[MR-based]**"
        elif c.workflow_mode == WORKFLOW_MODE_PATCH:
            workflow_info = " **[Patch-based]**"
        else:
            workflow_info = ""

        lines.append(f"{i}. **{c.title}**")
        lines.append(f"   - URL: {c.url}")
        lines.append(f"   - Status: {status_info}{workflow_info}")
        lines.append(f"   - Score: {c.score:.1f}")
        if c.mr_urls:
            lines.append(f"   - MRs: {', '.join(c.mr_urls)}")
        if c.patch_urls:
            lines.append(f"   - Patches: {len(c.patch_urls)} attached")
        lines.append("")

    return "\n".join(lines)

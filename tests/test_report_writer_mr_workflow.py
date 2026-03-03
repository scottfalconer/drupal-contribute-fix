import unittest
import tempfile
from pathlib import Path

from lib.issue_matcher import IssueCandidate, WORKFLOW_MODE_MR, WORKFLOW_MODE_PATCH
from lib.patch_packager import PatchInfo
from lib.report_writer import (
    create_report,
    generate_issue_comment,
    generate_report_markdown,
    write_report,
)


def _build_mr_report():
    best = IssueCandidate(
        nid=123,
        title="Example MR issue",
        url="https://www.drupal.org/node/123",
        status=1,
        status_label="Active",
        priority=200,
        priority_label="Normal",
        score=88.0,
        score_breakdown={"keyword_exact_title": 50.0},
        has_mr=True,
        has_patch=False,
        mr_urls=["https://git.drupalcode.org/project/example/-/merge_requests/42"],
        patch_urls=[],
        workflow_mode=WORKFLOW_MODE_MR,
    )
    patch_info = PatchInfo(
        path=Path("/tmp/example-fix.diff"),
        filename="example-fix-123.diff",
        project="example",
        description="fix",
        issue_number=123,
        files_changed=1,
        insertions=2,
        deletions=1,
    )
    return create_report(
        project="example",
        keywords=["Fatal error"],
        file_paths=["src/Foo.php"],
        outcome="proceed",
        outcome_code=0,
        outcome_reason="Local diff artifact generated successfully for MR workflow.",
        candidates=[best],
        best_match=best,
        best_match_confidence="high",
        patch_info=patch_info,
        test_steps=["Reproduce the issue", "Apply fix", "Verify behavior"],
    )


def _build_patch_only_stop_report():
    best = IssueCandidate(
        nid=456,
        title="Example historical patch issue",
        url="https://www.drupal.org/node/456",
        status=1,
        status_label="Active",
        priority=200,
        priority_label="Normal",
        score=82.0,
        score_breakdown={"keyword_exact_title": 40.0},
        has_mr=False,
        has_patch=True,
        mr_urls=[],
        patch_urls=["https://www.drupal.org/files/issues/example-456.patch"],
        workflow_mode=WORKFLOW_MODE_PATCH,
    )
    return create_report(
        project="example",
        keywords=["Fatal error"],
        file_paths=["src/Foo.php"],
        outcome="existing_fix",
        outcome_code=10,
        outcome_reason="Existing upstream artifact found.",
        candidates=[best],
        best_match=best,
        best_match_confidence="high",
    )


class TestReportWriterMRWorkflow(unittest.TestCase):
    def test_report_markdown_uses_mr_instructions_without_patch_upload_step(self):
        report = _build_mr_report()
        markdown = generate_report_markdown(report, issue_nid=123)

        self.assertIn("Review the existing MR", markdown)
        self.assertIn("do not upload unless maintainers ask", markdown)
        self.assertNotIn("Attach the patch", markdown)
        self.assertNotIn("Set status", markdown)

    def test_issue_comment_for_mr_workflow_uses_local_review_artifact_wording(self):
        report = _build_mr_report()
        comment = generate_issue_comment(report, is_new_issue=False)

        self.assertIn("MR workflow note", comment)
        self.assertIn("Local review artifact (not uploaded by default)", comment)
        self.assertNotIn("**Attached patch:**", comment)

    def test_patch_only_issue_comment_recommends_mr_workflow(self):
        report = _build_patch_only_stop_report()
        comment = generate_issue_comment(report, is_new_issue=False)

        self.assertIn("switch to MR workflow", comment)
        self.assertNotIn("reroll/update the latest patch", comment)

    def test_write_report_creates_local_ci_parity_file_when_ci_logs_exist(self):
        report = _build_mr_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            issue_dir = output_dir / "123-fatal-error"
            ci_dir = issue_dir / "ci"
            ci_dir.mkdir(parents=True, exist_ok=True)
            (ci_dir / "matrix.log").write_text("matrix output\n")

            paths = write_report(
                report=report,
                output_dir=output_dir,
                issue_nid=123,
                issue_dir_override="123-fatal-error",
            )

            self.assertIn("local_ci_parity", paths)
            parity_path = paths["local_ci_parity"]
            self.assertTrue(parity_path.exists())
            parity_content = parity_path.read_text()
            self.assertIn("# Local CI Parity", parity_content)
            self.assertIn("`ci/matrix.log`", parity_content)

    def test_write_report_skips_local_ci_parity_file_without_ci_logs(self):
        report = _build_mr_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            paths = write_report(
                report=report,
                output_dir=output_dir,
                issue_nid=123,
                issue_dir_override="123-fatal-error",
            )

            self.assertNotIn("local_ci_parity", paths)
            issue_dir = output_dir / "123-fatal-error"
            parity_files = list(issue_dir.glob("LOCAL_CI_PARITY_*.md"))
            self.assertEqual([], parity_files)


if __name__ == "__main__":
    unittest.main()

import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import contribute_fix
from lib.validator import ValidationResult


class TestPackageValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.baseline = self.root / "baseline"
        self.source.mkdir()
        self.baseline.mkdir()
        (self.baseline / "example.module").write_text("<?php\nreturn 1;\n")
        (self.source / "example.module").write_text("<?php\nreturn 2;\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "Baseline")
        self.api = Mock()
        self.api.get_issue.return_value = {"title": "Example", "field_issue_status": 1}
        self.api.get_comments.return_value = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(contribute_fix, "DrupalOrgAPI", return_value=self.api))
        self.stack.enter_context(patch.object(contribute_fix, "resolve_baseline", return_value=SimpleNamespace(
            git_url="local", ref="HEAD", source="test")))
        self.checkout = self.stack.enter_context(patch.object(contribute_fix, "checkout_baseline", return_value=self.baseline))
        self.validation = self.stack.enter_context(patch.object(contribute_fix, "validate_files", return_value=[]))

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.baseline, check=True, capture_output=True, text=True)

    def package(self, **kwargs):
        return contribute_fix.run_package(
            changed_path=self.source,
            output_dir=self.root / "out",
            project="example",
            issue_number=123,
            test_steps=["Call the example function and inspect its return value."],
            **kwargs,
        )

    def test_offline_package_never_clones_baseline(self):
        result = self.package(offline=True)
        self.assertEqual(result, contribute_fix.EXIT_ERROR)
        self.checkout.assert_not_called()

    def test_offline_package_can_write_cached_mr_review_report(self):
        self.api.get_issue.return_value["related_mrs"] = [
            "https://git.drupalcode.org/project/example/-/merge_requests/42"]
        result = self.package(offline=True)
        self.assertEqual(result, contribute_fix.EXIT_EXISTING_FIX)
        self.checkout.assert_not_called()
        self.assertTrue((self.root / "out" / "123-fix" / "REPORT.md").exists())

    def test_preflight_issue_list_failure_returns_error(self):
        self.api.get_project_nid.return_value = 123
        self.api.fetch_issues_batch.side_effect = contribute_fix.DrupalOrgAPIError("Cache miss")
        result, candidates, best_match, confidence = contribute_fix.run_preflight(
            "example", ["error"], [], self.root / "out", offline=True)
        self.assertEqual(result, contribute_fix.EXIT_ERROR)
        self.assertEqual(candidates, [])
        self.assertIsNone(best_match)
        self.assertEqual(confidence, "none")

    def test_known_issue_fetch_failure_stops_package_even_with_force(self):
        self.api.get_issue.side_effect = contribute_fix.DrupalOrgAPIError("Network unavailable")
        result = self.package(force=True)
        self.assertEqual(result, contribute_fix.EXIT_ERROR)
        self.checkout.assert_not_called()

    def test_missing_known_issue_stops_package(self):
        self.api.get_issue.return_value = {}
        result = self.package()
        self.assertEqual(result, contribute_fix.EXIT_ERROR)
        self.checkout.assert_not_called()

    def test_failed_validation_returns_error_and_retains_evidence(self):
        self.validation.return_value = [ValidationResult(
            "PHP Lint", "php -l example.module", False, "Parse error: unexpected token")]
        result = self.package()
        self.assertEqual(result, contribute_fix.EXIT_ERROR)
        issue_dir = self.root / "out" / "123-fix"
        self.assertTrue(list((issue_dir / "diffs").glob("*.diff")))
        self.assertIn("FAILED", (issue_dir / "REPORT.md").read_text())
        self.assertIn("FAILED", (issue_dir / "ISSUE_COMMENT.md").read_text())
        self.assertIn("Parse error: unexpected token", (issue_dir / "ISSUE_COMMENT.md").read_text())

    def test_unavailable_check_is_not_a_failed_executed_check(self):
        self.validation.return_value = [ValidationResult(
            "PHP CodeSniffer", "phpcs", False, "", "phpcs not found")]
        result = self.package()
        self.assertEqual(result, contribute_fix.EXIT_PROCEED)
        comment = (self.root / "out" / "123-fix" / "ISSUE_COMMENT.md").read_text()
        self.assertIn("NOT RUN (phpcs not found)", comment)
        self.assertNotIn("PHP CodeSniffer: PASSED", comment)

    def test_security_check_exception_stops_package(self):
        with patch.object(contribute_fix, "is_security_related", side_effect=RuntimeError("check failed")):
            result = self.package()
        self.assertEqual(result, contribute_fix.EXIT_ERROR)
        self.assertFalse(list((self.root / "out").rglob("*.diff")))

    def test_security_check_includes_new_file_contents(self):
        (self.source / "new.php").write_text("<?php\neval($input);\n")
        result = self.package()
        self.assertEqual(result, contribute_fix.EXIT_SECURITY)
        self.assertFalse(list((self.root / "out").rglob("*.diff")))


if __name__ == "__main__":
    unittest.main()

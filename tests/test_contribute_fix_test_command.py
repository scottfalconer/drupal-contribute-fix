import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import contribute_fix


class _FakeAPI:
    def get_issue(self, issue_number, include_mrs=True):
        return {
            "title": f"Issue #{issue_number}",
            "related_mrs": [
                "https://git.drupalcode.org/project/example/-/merge_requests/42",
            ],
        }


class TestRunTestCommand(unittest.TestCase):
    def test_extract_mr_urls_accepts_string_and_dict_payloads(self):
        self.assertEqual(
            contribute_fix.extract_mr_urls([
                "https://example.org/42",
                {"url": "https://example.org/77"},
            ]),
            ["https://example.org/42", "https://example.org/77"],
        )

    def test_test_comment_records_evidence_without_rtbc_claim(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            with patch("scripts.contribute_fix.DrupalOrgAPI", return_value=_FakeAPI()):
                exit_code = contribute_fix.run_test(
                    issue_number=123,
                    tested_on="Drupal 11, PHP 8.2",
                    result="pass",
                    output_dir=out_dir,
                    mr_number="77",
                    test_command="phpunit --filter ExampleTest",
                    test_output="Exit 0: OK (1 test, 2 assertions)",
                )
            comment = (out_dir / "TEST_COMMENT.md").read_text()

        self.assertEqual(exit_code, contribute_fix.EXIT_PROCEED)
        self.assertIn("MR !77", comment)
        self.assertNotIn("MR !42", comment)
        self.assertIn("phpunit --filter ExampleTest", comment)
        self.assertIn("Exit 0: OK (1 test, 2 assertions)", comment)
        self.assertIn("command did not run tests", comment)
        self.assertNotIn("RTBC+1", comment)
        self.assertNotIn("Applied the diff", comment)

    def test_missing_evidence_does_not_write_pass_comment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            with patch("scripts.contribute_fix.DrupalOrgAPI", return_value=_FakeAPI()) as api:
                exit_code = contribute_fix.run_test(
                    issue_number=123,
                    tested_on="Drupal 11, PHP 8.2",
                    result="pass",
                    output_dir=out_dir,
                    mr_number="42",
                )
            self.assertEqual(exit_code, contribute_fix.EXIT_ERROR)
            api.assert_not_called()
            self.assertFalse((out_dir / "TEST_COMMENT.md").exists())

    def test_missing_artifact_is_not_inferred_from_issue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.contribute_fix.DrupalOrgAPI", return_value=_FakeAPI()) as api:
                exit_code = contribute_fix.run_test(
                    issue_number=123,
                    tested_on="Drupal 11, PHP 8.2",
                    result="pass",
                    output_dir=Path(tmpdir),
                )
            self.assertEqual(exit_code, contribute_fix.EXIT_ERROR)
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()

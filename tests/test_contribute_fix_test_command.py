import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import contribute_fix


class _FakeAPIStringMR:
    def get_issue(self, issue_number, include_mrs=True):
        return {
            "title": f"Issue #{issue_number}",
            "related_mrs": [
                "https://git.drupalcode.org/project/example/-/merge_requests/42",
            ],
        }


class _FakeAPIDictMR:
    def get_issue(self, issue_number, include_mrs=True):
        return {
            "title": f"Issue #{issue_number}",
            "related_mrs": [
                {"url": "https://git.drupalcode.org/project/example/-/merge_requests/77"},
            ],
        }


class TestRunTestCommand(unittest.TestCase):
    def test_run_test_accepts_string_related_mrs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            with patch("scripts.contribute_fix.DrupalOrgAPI", return_value=_FakeAPIStringMR()):
                exit_code = contribute_fix.run_test(
                    issue_number=123,
                    tested_on="Drupal 11, PHP 8.2",
                    result="pass",
                    output_dir=out_dir,
                )
            comment = (out_dir / "TEST_COMMENT.md").read_text()

        self.assertEqual(exit_code, contribute_fix.EXIT_PROCEED)
        self.assertIn("MR !42", comment)

    def test_run_test_accepts_dict_related_mrs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            with patch("scripts.contribute_fix.DrupalOrgAPI", return_value=_FakeAPIDictMR()):
                exit_code = contribute_fix.run_test(
                    issue_number=456,
                    tested_on="Drupal 11, PHP 8.2",
                    result="pass",
                    output_dir=out_dir,
                )
            comment = (out_dir / "TEST_COMMENT.md").read_text()

        self.assertEqual(exit_code, contribute_fix.EXIT_PROCEED)
        self.assertIn("MR !77", comment)


if __name__ == "__main__":
    unittest.main()

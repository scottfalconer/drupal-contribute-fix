import unittest
from unittest.mock import Mock

from lib.issue_matcher import IssueCandidate, IssueMatcher, WORKFLOW_MODE_MR


class TestIssueMatcher(unittest.TestCase):
    def test_mixed_mr_payloads_preserve_mr_workflow_and_attachments(self):
        api = Mock()
        url = "https://git.drupalcode.org/project/example/-/merge_requests/42"
        api.get_issue.return_value = {
            "related_mrs": [url, {"url": url}, None],
            "field_issue_files": [{"fid": 123}],
        }
        api.get_file.return_value = {"filename": "fix.patch", "url": "https://www.drupal.org/files/fix.patch"}
        api.get_comments.return_value = []
        candidate = IssueCandidate(1, "Issue", "https://www.drupal.org/node/1", 1, "Active", 200, "Normal", 80)
        IssueMatcher(api)._enrich_candidate(candidate)
        self.assertEqual(candidate.mr_urls, [url])
        self.assertTrue(candidate.has_mr)
        self.assertTrue(candidate.has_patch)
        self.assertEqual(candidate.workflow_mode, WORKFLOW_MODE_MR)


if __name__ == "__main__":
    unittest.main()

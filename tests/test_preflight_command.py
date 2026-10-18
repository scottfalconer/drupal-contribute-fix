import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import contribute_fix


class TestPreflightCommand(unittest.TestCase):
    def test_failed_preflight_preserves_existing_candidate_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            candidate_path = Path(tmpdir) / "UPSTREAM_CANDIDATES.json"
            existing = b'{"count": 1, "candidates": [{"nid": 123}]}\n'
            candidate_path.write_bytes(existing)
            api = Mock()
            api.get_project_nid.return_value = 1
            api.fetch_issues_batch.side_effect = contribute_fix.DrupalOrgAPIError("Cache miss")
            with patch.object(contribute_fix, "DrupalOrgAPI", return_value=api), patch(
                "sys.argv", ["contribute_fix.py", "preflight", "--project", "example", "--offline", "--out", tmpdir]
            ), self.assertRaises(SystemExit) as raised:
                contribute_fix.main()
            self.assertEqual(raised.exception.code, contribute_fix.EXIT_ERROR)
            self.assertEqual(candidate_path.read_bytes(), existing)


if __name__ == "__main__":
    unittest.main()

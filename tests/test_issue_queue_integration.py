import os
import tempfile
import unittest
from pathlib import Path


class TestIssueQueueIntegration(unittest.TestCase):
    def test_find_dorg_script_from_env_override(self):
        from lib.issue_queue_integration import find_dorg_script

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "scripts").mkdir(parents=True, exist_ok=True)
            dorg = root / "scripts" / "dorg.py"
            dorg.write_text("#!/usr/bin/env python3\n")

            old = os.environ.get("DRUPAL_ISSUE_QUEUE_DIR")
            os.environ["DRUPAL_ISSUE_QUEUE_DIR"] = str(root)
            try:
                found = find_dorg_script(repo_root=None)
                self.assertEqual(found, dorg)
            finally:
                if old is None:
                    os.environ.pop("DRUPAL_ISSUE_QUEUE_DIR", None)
                else:
                    os.environ["DRUPAL_ISSUE_QUEUE_DIR"] = old


if __name__ == "__main__":
    unittest.main()


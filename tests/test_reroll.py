import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import contribute_fix
from lib.baseline_repo import BaselineInfo


class TestReroll(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test User")
        self.source = self.repo / "example.txt"
        self.original = ["line {}\n".format(i) for i in range(30)]
        self.source.write_text("".join(self.original))
        self.git("add", ".")
        self.git("commit", "-m", "Base")
        patched = self.original.copy()
        patched[10] = "fixed line\n"
        self.source.write_text("".join(patched))
        self.patch_content = self.git("diff", "--full-index", "--unified=10").stdout
        self.source.write_text("".join(self.original))
        self.out = self.root / "output"

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=True
        )

    def run_reroll(self):
        # A relative output directory must work when git runs in another directory.
        relative_out = Path(os.path.relpath(self.out, Path.cwd()))
        with patch("urllib.request.urlopen", return_value=io.BytesIO(self.patch_content.encode())), \
                patch.object(contribute_fix, "resolve_baseline"), \
                patch.object(contribute_fix, "checkout_baseline", return_value=self.repo):
            return contribute_fix.run_reroll(
                issue_number=123,
                patch_url="https://www.drupal.org/files/issues/example-fix.patch",
                target_ref="1.x",
                output_dir=relative_out,
                project="example",
            )

    def change_target(self, line):
        target = self.original.copy()
        target[line] = "target change\n"
        self.source.write_text("".join(target))
        self.git("add", ".")
        self.git("commit", "-m", "Target change")

    def test_clean_patch_with_relative_output(self):
        self.assertEqual(contribute_fix.EXIT_PROCEED, self.run_reroll())
        self.assertFalse((self.out / "patches").exists())
        self.assertIn("applies cleanly", (self.out / "REROLL_COMMENT.md").read_text())

    def test_three_way_apply_includes_staged_changes(self):
        self.change_target(18)
        self.assertEqual(contribute_fix.EXIT_PROCEED, self.run_reroll())
        artifact = self.out / "patches" / "example-reroll-123-1.x.patch"
        self.assertIn("+fixed line", artifact.read_text())
        self.assertNotIn("+target change", artifact.read_text())
        # The result must apply to the target branch before the reroll changes.
        self.git("apply", "--reverse", "--check", str(artifact))

    def test_conflict_returns_incomplete_result(self):
        self.change_target(10)
        self.assertEqual(contribute_fix.EXIT_ANALYSIS_ONLY, self.run_reroll())
        self.assertFalse((self.out / "patches").exists())
        self.assertIn("Manual", (self.out / "REROLL_COMMENT.md").read_text())

    def test_diff_failure_does_not_write_patch(self):
        self.change_target(18)
        real_run = subprocess.run

        def fail_diff(command, **kwargs):
            if command[:2] == ["git", "diff"]:
                return subprocess.CompletedProcess(command, 1, "", "diff failed")
            return real_run(command, **kwargs)

        with patch("subprocess.run", side_effect=fail_diff):
            self.assertEqual(contribute_fix.EXIT_ERROR, self.run_reroll())
        self.assertFalse((self.out / "patches").exists())

    def test_three_way_reroll_clones_required_history(self):
        self.change_target(18)
        self.git("branch", "1.x")
        baseline = BaselineInfo("example", self.repo.as_uri(), "1.x")
        with patch("urllib.request.urlopen", return_value=io.BytesIO(self.patch_content.encode())), \
                patch.object(contribute_fix, "resolve_baseline", return_value=baseline):
            result = contribute_fix.run_reroll(
                issue_number=123,
                patch_url="https://www.drupal.org/files/issues/example-fix.patch",
                target_ref="1.x",
                output_dir=self.out,
                project="example",
            )
        self.assertEqual(contribute_fix.EXIT_PROCEED, result)
        artifact = self.out / "patches" / "example-reroll-123-1.x.patch"
        self.assertIn("+fixed line", artifact.read_text())
        self.git("apply", "--check", str(artifact))


if __name__ == "__main__":
    unittest.main()

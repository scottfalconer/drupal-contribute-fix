import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lib.patch_packager import generate_patch


@unittest.skipUnless(shutil.which("git"), "git is required for patch packager tests")
class TestPatchPackager(unittest.TestCase):
    def test_diffstat_matches_filtered_patch_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = root / "repo"
            out = root / "out"
            repo.mkdir(parents=True, exist_ok=True)

            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)

            (repo / "example.info.yml").write_text("name: Example\ntype: module\n", encoding="utf-8")
            (repo / "src").mkdir(parents=True, exist_ok=True)
            (repo / "src" / "Foo.php").write_text("<?php\nclass Foo {}\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)

            # Add a real code change plus packaging-only .info.yml metadata.
            (repo / "src" / "Foo.php").write_text(
                "<?php\nclass Foo { public function bar() {} }\n",
                encoding="utf-8",
            )
            (repo / "example.info.yml").write_text(
                "name: Example\ntype: module\nproject: 'example'\ndatestamp: 1700000000\n",
                encoding="utf-8",
            )

            patch_info = generate_patch(
                baseline_path=repo,
                output_dir=out,
                project="example",
                description="test",
                issue_number=123,
            )

            content = (out / patch_info.filename).read_text(encoding="utf-8")
            diff_headers = [line for line in content.splitlines() if line.startswith("diff --git ")]

            self.assertTrue(patch_info.filename.endswith(".diff"))
            self.assertEqual(1, len(diff_headers))
            self.assertEqual(1, patch_info.files_changed)
            self.assertEqual(1, patch_info.insertions)
            self.assertEqual(1, patch_info.deletions)
            self.assertNotIn("example.info.yml", content)


if __name__ == "__main__":
    unittest.main()

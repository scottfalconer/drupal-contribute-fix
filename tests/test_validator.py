import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.validator import run_php_lint, run_phpcs, run_phpstan


class TestValidator(unittest.TestCase):
    def test_php_lint_checks_drupal_extensions_and_records_exact_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = [Path(tmpdir) / f"example with space.{ext}" for ext in
                     ("php", "module", "inc", "install", "test", "profile", "theme")]
            for path in paths:
                path.write_text("<?php\nreturn 1;\n")
            with patch("lib.validator.find_executable", return_value="/usr/bin/php"), patch(
                "lib.validator.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "No syntax errors", "")
            ) as run:
                result = run_php_lint(paths)
        self.assertTrue(result.passed)
        self.assertEqual(run.call_count, len(paths))
        self.assertEqual(result.command.splitlines(), [shlex.join(["/usr/bin/php", "-l", str(path)]) for path in paths])

    def test_php_lint_retains_stderr_for_failed_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.php"
            path.write_text("<?php invalid syntax\n")
            with patch("lib.validator.find_executable", return_value="php"), patch(
                "lib.validator.subprocess.run", return_value=subprocess.CompletedProcess([], 255, "", "Parse error")
            ):
                result = run_php_lint([path])
        self.assertFalse(result.passed)
        self.assertIn("Parse error", result.output)
        self.assertIn("exit 255", result.output)

    def test_no_applicable_files_is_not_a_pass(self):
        for validate in (run_php_lint, run_phpcs, run_phpstan):
            with self.subTest(validator=validate.__name__), patch("lib.validator.find_executable", return_value="tool"), patch(
                "lib.validator.subprocess.run"
            ) as run:
                result = validate([Path("README.md")])
                self.assertFalse(result.passed)
                self.assertIsNotNone(result.not_run_reason)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()

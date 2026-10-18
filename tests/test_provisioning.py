"""Check provisioning scripts without a network, containers, or global installs."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BASH = "/bin/bash"
GIT = shutil.which("git")


class ScriptTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.calls = self.root / "calls"
        self.env = dict(os.environ)
        self.env.update(PATH=str(self.bin), TEST_CALLS=str(self.calls))

    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\nset -eu\n" + body)
        path.chmod(0o755)
        return path

    def ddev_project(self):
        (self.project / ".ddev").mkdir()
        (self.project / ".ddev/config.yaml").write_text("type: drupal11\n")

    def fake_ddev(self):
        self.command(
            "ddev",
            'printf "%s\\n" "$*" >> "$TEST_CALLS"\n'
            'if [[ "$*" == "${TEST_FAIL_COMMAND-}" ]]; then exit 17; fi\n'
            'if [[ "$1" == cspell && "${TEST_NO_CSPELL-}" == 1 ]]; then\n'
            '  printf "Error: unknown command cspell\\n" >&2\n'
            '  exit 1\n'
            'fi\n',
        )

    def run_script(self, name, *args, cwd=None):
        return subprocess.run(
            [BASH, str(SCRIPTS / name), *args],
            cwd=cwd or self.project,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def recorded_calls(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []


class ProvisioningTests(ScriptTestCase):
    def test_help_requires_no_tools_or_project(self):
        for script in SCRIPTS.glob("*.sh"):
            with self.subTest(script=script.name):
                result = self.run_script(script.name, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Usage:", result.stdout)
        self.assertEqual(self.recorded_calls(), [])

    def test_invalid_arguments_do_not_install_or_run_checks(self):
        self.fake_ddev()
        for name in ("setup-ddev-contrib.sh", "setup-drupalorg-cli.sh", "run-local-ci.sh"):
            with self.subTest(script=name):
                result = self.run_script(name, "--unknown")
                self.assertEqual(result.returncode, 2)
        self.assertEqual(self.recorded_calls(), [])

    def test_ddev_scripts_require_project_root(self):
        self.fake_ddev()
        for name in ("setup-ddev-contrib.sh", "run-local-ci.sh"):
            with self.subTest(script=name):
                result = self.run_script(name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("project root", result.stderr)
        self.assertEqual(self.recorded_calls(), [])

    def test_ddev_scripts_fail_when_ddev_is_missing(self):
        self.ddev_project()
        for name in ("setup-ddev-contrib.sh", "run-local-ci.sh"):
            with self.subTest(script=name):
                result = self.run_script(name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Install DDEV", result.stderr)

    def test_contrib_setup_uses_official_addon_and_keeps_git_excludes(self):
        self.ddev_project()
        self.fake_ddev()
        info = self.project / ".git/info"
        info.mkdir(parents=True)
        excludes = info / "exclude"
        excludes.write_text("local-notes.txt\n")
        result = self.run_script("setup-ddev-contrib.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_calls(),
            ["add-on get ddev/ddev-drupal-contrib", "restart", "poser", "symlink-project"],
        )
        self.assertEqual(excludes.read_text(), "local-notes.txt\n")
        self.assertFalse((self.project / ".gitignore").exists())

    def test_contrib_setup_stops_after_each_failed_step(self):
        self.ddev_project()
        self.fake_ddev()
        commands = ["add-on get ddev/ddev-drupal-contrib", "restart", "poser", "symlink-project"]
        for index, command in enumerate(commands):
            with self.subTest(command=command):
                self.calls.write_text("")
                self.env["TEST_FAIL_COMMAND"] = command
                result = self.run_script("setup-ddev-contrib.sh")
                self.assertEqual(result.returncode, 17)
                self.assertEqual(self.recorded_calls(), commands[: index + 1])
                self.assertNotIn("setup is complete", result.stdout)

    def test_local_checks_report_their_scope(self):
        self.ddev_project()
        self.fake_ddev()
        result = self.run_script("run-local-ci.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded_calls(), ["phpstan", "phpcs"])
        self.assertIn("Scope: phpstan phpcs", result.stdout)
        self.assertIn("Run the project tests and GitLab CI separately", result.stdout)

    def test_local_checks_continue_after_failure_and_return_failure(self):
        self.ddev_project()
        self.fake_ddev()
        self.env["TEST_FAIL_COMMAND"] = "phpstan"
        result = self.run_script("run-local-ci.sh", "--cspell")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.recorded_calls(), ["phpstan", "phpcs", "cspell"])
        self.assertIn("FAIL: ddev phpstan (exit 17)", result.stderr)
        self.assertNotIn("All selected local checks passed", result.stdout)

    def test_requested_cspell_cannot_be_skipped_as_a_pass(self):
        self.ddev_project()
        self.fake_ddev()
        self.env["TEST_NO_CSPELL"] = "1"
        result = self.run_script("run-local-ci.sh", "--cspell")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.recorded_calls(), ["phpstan", "phpcs", "cspell"])
        self.assertIn("unknown command cspell", result.stderr)
        self.assertNotIn("All selected local checks passed", result.stdout)

    def fake_composer(self, binary_status=0):
        self.command("php", 'exit "${TEST_PHP_STATUS:-0}"\n')
        installed_bin = self.root / "composer global bin"
        installed_bin.mkdir()
        binary = installed_bin / "drupalorg"
        binary.write_text(
            '#!/bin/bash\nprintf "installed: %s\\n" "$*" >> "$TEST_CALLS"\n'
            f'exit {binary_status}\n'
        )
        binary.chmod(0o755)
        self.env["TEST_COMPOSER_BIN"] = str(installed_bin)
        self.command(
            "composer",
            'printf "%s\\n" "$*" >> "$TEST_CALLS"\n'
            'if [[ "${TEST_REQUIRE_PLUGIN_FLAGS-}" == 1 ]]; then\n'
            '  case " $* " in *" --no-plugins "*) ;; *) exit 20 ;; esac\n'
            '  case " $* " in *" --no-scripts "*) ;; *) exit 21 ;; esac\n'
            'fi\n'
            'if [[ "$2" == require ]]; then exit "${TEST_COMPOSER_STATUS:-0}"; fi\n'
            'printf "%s\\n" "$TEST_COMPOSER_BIN"\n',
        )
        return binary

    def test_cli_installer_verifies_binary_outside_path(self):
        self.fake_composer()
        result = self.run_script("setup-drupalorg-cli.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.recorded_calls(),
            [
                "global require --no-interaction --no-plugins --no-scripts mglaman/drupalorg-cli",
                "global config --no-interaction --no-plugins --no-scripts bin-dir --absolute",
                "installed: --version",
            ],
        )
        self.assertIn("Add this directory to PATH", result.stdout)

    def test_cli_installer_disables_plugins_and_scripts_without_changing_policy(self):
        self.fake_composer()
        self.env["TEST_REQUIRE_PLUGIN_FLAGS"] = "1"
        composer_home = self.root / "composer-home"
        composer_home.mkdir()
        self.env["COMPOSER_HOME"] = str(composer_home)
        config = composer_home / "config.json"
        policy = '{"config": {"allow-plugins": {}}}\n'
        config.write_text(policy)
        result = self.run_script("setup-drupalorg-cli.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(config.read_text(), policy)
        self.assertFalse(any("allow-plugins" in call for call in self.recorded_calls()))

    def test_cli_installer_does_not_use_a_different_binary_on_path(self):
        self.fake_composer(binary_status=23)
        self.command("drupalorg", "exit 0\n")
        result = self.run_script("setup-drupalorg-cli.sh")
        self.assertEqual(result.returncode, 23)
        self.assertNotIn("Installed command:", result.stdout)

    def test_cli_installer_rejects_missing_installed_binary(self):
        self.fake_composer().unlink()
        self.command("drupalorg", "exit 0\n")
        result = self.run_script("setup-drupalorg-cli.sh")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing or is not executable", result.stderr)

    def test_cli_installer_stops_if_composer_fails(self):
        self.fake_composer()
        self.env["TEST_COMPOSER_STATUS"] = "19"
        result = self.run_script("setup-drupalorg-cli.sh")
        self.assertEqual(result.returncode, 19)
        self.assertEqual(
            self.recorded_calls(),
            ["global require --no-interaction --no-plugins --no-scripts mglaman/drupalorg-cli"],
        )

    def test_cli_installer_rejects_old_php_before_install(self):
        self.fake_composer()
        self.env["TEST_PHP_STATUS"] = "1"
        result = self.run_script("setup-drupalorg-cli.sh")
        self.assertEqual(result.returncode, 1)
        self.assertIn("PHP 8.1", result.stderr)
        self.assertEqual(self.recorded_calls(), [])


@unittest.skipUnless(GIT, "Git is required for workspace integration tests")
class WorkspaceTests(ScriptTestCase):
    def setUp(self):
        super().setUp()
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS"):
            self.env.pop(name, None)
        self.env.update(
            PATH=os.environ.get("PATH", "/usr/bin:/bin"),
            GIT_CONFIG_GLOBAL=str(self.root / "gitconfig"),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_TERMINAL_PROMPT="0",
            GIT_AUTHOR_NAME="Test User",
            GIT_AUTHOR_EMAIL="test@example.com",
            GIT_COMMITTER_NAME="Test User",
            GIT_COMMITTER_EMAIL="test@example.com",
        )
        self.fork = self.root / "fork"
        self.git("init", "--quiet", str(self.fork))
        self.git("checkout", "-b", "main", cwd=self.fork)
        (self.fork / "module.txt").write_text("base\n")
        self.git("add", "module.txt", cwd=self.fork)
        self.git("commit", "--quiet", "-m", "Base", cwd=self.fork)
        self.git("checkout", "-b", "123-explicit-branch", cwd=self.fork)
        (self.fork / "module.txt").write_text("issue change\n")
        self.git("commit", "--quiet", "-am", "Issue change", cwd=self.fork)
        self.git("checkout", "main", cwd=self.fork)
        self.git(
            "config", "--file", self.env["GIT_CONFIG_GLOBAL"],
            f"url.{self.fork.as_uri()}.insteadOf",
            "https://git.drupalcode.org/issue/example-123.git",
        )

    def git(self, *args, cwd=None):
        result = subprocess.run(
            [GIT, *args], cwd=cwd or self.root, env=self.env,
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_workspace_tracks_exact_selected_branch(self):
        result = self.run_script("setup-mr-workspace.sh", "example", "123", "123-explicit-branch")
        self.assertEqual(result.returncode, 0, result.stderr)
        workspace = self.project / "example"
        self.assertEqual((workspace / "module.txt").read_text(), "issue change\n")
        self.assertEqual(self.git("branch", "--show-current", cwd=workspace), "123-explicit-branch")
        self.assertEqual(
            self.git("rev-parse", "--abbrev-ref", "@{upstream}", cwd=workspace),
            "example-123/123-explicit-branch",
        )
        self.assertEqual(
            self.git("remote", "get-url", "origin", cwd=workspace),
            "https://git.drupalcode.org/project/example.git",
        )

    def test_workspace_can_use_fork_default_branch_name(self):
        result = self.run_script("setup-mr-workspace.sh", "example", "123", "main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.project / "example/module.txt").read_text(), "base\n")

    def test_workspace_missing_branch_does_not_select_another_branch(self):
        result = self.run_script("setup-mr-workspace.sh", "example", "123", "missing")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Cannot read branch missing", result.stderr)
        self.assertFalse((self.project / "example").exists())

    def test_workspace_rejects_tag_in_place_of_branch(self):
        self.git("tag", "123-tag-only", cwd=self.fork)
        result = self.run_script("setup-mr-workspace.sh", "example", "123", "123-tag-only")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.project / "example").exists())

    def test_workspace_refuses_existing_directory_and_dangling_symlink(self):
        destination = self.project / "example"
        destination.mkdir()
        marker = destination / "keep.txt"
        marker.write_text("keep\n")
        result = self.run_script("setup-mr-workspace.sh", "example", "123", "main")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(marker.read_text(), "keep\n")
        marker.unlink()
        destination.rmdir()
        destination.symlink_to(self.root / "missing")
        result = self.run_script("setup-mr-workspace.sh", "example", "123", "main")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(destination.is_symlink())

    def test_workspace_rejects_unsafe_arguments_before_creating_files(self):
        for args in (
            ("../example", "123", "main"),
            ("--config", "123", "main"),
            ("example", "not-a-number", "main"),
            ("example", "0", "main"),
            ("example", "123", "-option"),
            ("example", "123", "HEAD"),
            ("example", "123", "@{-1}"),
            ("example", "123", "refs/heads/*"),
            ("example", "123", "branch with spaces"),
        ):
            with self.subTest(args=args):
                result = self.run_script("setup-mr-workspace.sh", *args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse((self.project / "example").exists())


if __name__ == "__main__":
    unittest.main()

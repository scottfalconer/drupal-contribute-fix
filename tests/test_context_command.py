"""Exercise local context discovery through the CLI with real Git fixtures."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
CLI = REPOSITORY / "scripts" / "contribute_fix.py"
GIT = shutil.which("git")


@unittest.skipUnless(GIT, "Git is required for context command tests")
class TestContextCommand(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.scan_root = self.root / "scan"
        self.scan_root.mkdir()
        self.env = dict(os.environ)
        for name in (
            "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
            "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_CONFIG_COUNT", "GIT_CONFIG_PARAMETERS", "GIT_TEMPLATE_DIR",
            "GIT_OPTIONAL_LOCKS", "PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX",
        ):
            self.env.pop(name, None)
        git_config = self.root / "gitconfig"
        git_config.write_text("", encoding="utf-8")
        self.env.update(
            GIT_CONFIG_GLOBAL=str(git_config),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_TERMINAL_PROMPT="0",
            GIT_AUTHOR_NAME="Context Test",
            GIT_AUTHOR_EMAIL="context@example.invalid",
            GIT_COMMITTER_NAME="Context Test",
            GIT_COMMITTER_EMAIL="context@example.invalid",
        )

    def git(self, repo, *args):
        result = subprocess.run(
            [GIT, *args], cwd=repo, env=self.env,
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def make_repository(self, name, project="example", branch="main", composer=False, parent=None):
        repo = (parent or self.scan_root) / name
        repo.mkdir(parents=True)
        self.git(repo, "init", "--quiet")
        self.git(repo, "symbolic-ref", "HEAD", "refs/heads/" + branch)
        (repo / "tracked.txt").write_text("original content\n", encoding="utf-8")
        if composer:
            (repo / "composer.json").write_text(
                json.dumps({"name": "drupal/" + project}), encoding="utf-8"
            )
        elif project is not None:
            self.git(
                repo, "remote", "add", "origin",
                "https://git.drupalcode.org/project/{}.git".format(project),
            )
        self.git(repo, "add", ".")
        self.git(repo, "commit", "--quiet", "-m", "Initial project files")
        return repo

    def commit_change(self, repo, subject):
        with (repo / "tracked.txt").open("a", encoding="utf-8") as handle:
            handle.write(subject + "\n")
        self.git(repo, "add", "tracked.txt")
        self.git(repo, "commit", "--quiet", "-m", subject)

    def run_cli(self, *args, cli=CLI):
        # Capture output in memory so test logs cannot change the scan results.
        return subprocess.run(
            [sys.executable, str(cli), "context", *args],
            cwd=self.scan_root, env=self.env,
            capture_output=True, text=True, timeout=30,
        )

    def scan(self, *args, cli=CLI, expected_status=0):
        result = self.run_cli(
            "--scan-root", str(self.scan_root), "--project", "example",
            "--issue", "123", "--format", "json", *args, cli=cli,
        )
        self.assertEqual(result.returncode, expected_status, result.stderr + result.stdout)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail("The JSON format must contain one JSON document: " + result.stdout)
        for field in (
            "scan_root", "project", "issue", "limits", "repositories",
            "reports", "warnings", "incomplete",
        ):
            self.assertIn(field, data)
        return data

    @staticmethod
    def repositories_by_path(data):
        return {item["path"]: item for item in data["repositories"]}

    def write_report(self, name, project="example", issue=123, related=False, body=""):
        report = self.scan_root / ".drupal-contribute-fix" / name / "REPORT.md"
        report.parent.mkdir(parents=True)
        field = "Related Issue" if related else "Issue"
        issue_url = (
            "https://www.drupal.org/project/{}/issues/{}".format(project, issue)
            if related else "https://www.drupal.org/node/{}".format(issue)
        )
        report.write_text(
            "# Contribution report\n\n"
            "**Generated:** 2026-10-18T12:00:00+00:00\n"
            "**Project:** {}\n**{}:** {}\n\n"
            "---\n\n## Outcome\n\n{}\n".format(project, field, issue_url, body),
            encoding="utf-8",
        )
        return report

    def test_matches_exact_issue_branch_and_commit_in_project_repository(self):
        repo = self.make_repository("checkout", branch="fix-123-description")
        self.commit_change(repo, "Issue #123: Handle the reported error")
        head = self.git(repo, "rev-parse", "HEAD")
        data = self.scan()
        item = self.repositories_by_path(data)[str(repo)]
        self.assertEqual(item["branch"], "fix-123-description")
        self.assertEqual(item["head"], head)
        self.assertIs(item["dirty"], False)
        self.assertEqual(item["status"], [])
        self.assertIsInstance(item["project_match"], str)
        self.assertTrue(item["project_match"])
        self.assertEqual({match["kind"] for match in item["matches"]}, {"branch", "commit"})
        self.assertTrue(all(match["value"] and match["reason"] for match in item["matches"]))
        self.assertIs(data["incomplete"], False)

    def test_excludes_other_projects_and_does_not_match_issue_number_prefix(self):
        lookalike = self.make_repository("same-project", branch="fix-1234-description")
        self.commit_change(lookalike, "Issue #1234: Different issue")
        other = self.make_repository("example-123", project="other", branch="fix-123")
        self.commit_change(other, "Issue #123: Different project")
        self.make_repository("project-prefix", project="example_extra", branch="fix-123")
        self.make_repository("example", project=None, branch="fix-123")
        data = self.scan()
        repositories = self.repositories_by_path(data)
        self.assertEqual(set(repositories), {str(lookalike)})
        self.assertEqual(repositories[str(lookalike)]["matches"], [])

    def test_dirty_project_without_issue_reference_remains_visible_as_nonmatch(self):
        repo = self.make_repository("dirty-checkout")
        (repo / "tracked.txt").write_text("local changes\n", encoding="utf-8")
        (repo / "untracked.txt").write_text("unfinished work\n", encoding="utf-8")
        data = self.scan()
        item = self.repositories_by_path(data)[str(repo)]
        self.assertIs(item["dirty"], True)
        self.assertIsInstance(item["status"], list)
        self.assertTrue(item["status"])
        self.assertEqual(item["matches"], [])

    def test_composer_package_name_identifies_project_without_a_remote(self):
        repo = self.make_repository("composer-checkout", composer=True, branch="fix-123")
        data = self.scan()
        item = self.repositories_by_path(data)[str(repo)]
        self.assertIn("composer", item["project_match"].lower())
        self.assertEqual([match["kind"] for match in item["matches"]], ["branch"])

    def test_remote_hostname_must_be_an_official_drupal_host(self):
        repo = self.make_repository("remote-lookalike", branch="fix-123")
        self.git(
            repo, "remote", "set-url", "origin",
            "https://git.drupalcode.org.example.invalid/project/example.git",
        )
        self.assertEqual(self.scan()["repositories"], [])

    def test_discovers_linked_worktree_inside_scan_root(self):
        repo = self.make_repository("primary")
        linked = self.scan_root / "linked"
        self.git(repo, "worktree", "add", "-b", "fix-123-linked", str(linked), "HEAD")
        self.assertTrue((linked / ".git").is_file())
        data = self.scan()
        repositories = self.repositories_by_path(data)
        self.assertEqual(set(repositories), {str(repo), str(linked)})
        self.assertEqual(repositories[str(linked)]["branch"], "fix-123-linked")
        self.assertEqual(repositories[str(linked)]["matches"][0]["kind"], "branch")
        self.assertEqual(repositories[str(repo)]["branch"], "main")
        # Linked worktrees share local refs, but have separate current branches.
        self.assertTrue(any(
            match["kind"] == "branch" and "fix-123-linked" in match["value"]
            for match in repositories[str(repo)]["matches"]
        ))

    def test_does_not_discover_linked_worktree_outside_scan_root(self):
        repo = self.make_repository("primary")
        linked = self.root / "outside-worktree"
        self.git(repo, "worktree", "add", "-b", "fix-123-outside", str(linked), "HEAD")
        data = self.scan()
        self.assertEqual(set(self.repositories_by_path(data)), {str(repo)})
        self.assertNotIn(str(linked), {item["path"] for item in data["repositories"]})

    def test_report_selection_uses_project_and_top_level_issue_headers(self):
        direct = self.write_report("direct")
        related = self.write_report("related", related=True)
        self.write_report("other-project", project="other")
        self.write_report("issue-prefix", issue=1234)
        self.write_report(
            "candidate-only", issue=999,
            body="Candidate: https://www.drupal.org/node/123\n"
                 "**Issue:** https://www.drupal.org/node/123",
        )
        data = self.scan()
        reports = {item["path"]: item for item in data["reports"]}
        self.assertEqual(set(reports), {str(direct), str(related)})
        for report in reports.values():
            self.assertTrue(report["issue_kind"])
            self.assertEqual(report["generated_at"], "2026-10-18T12:00:00+00:00")

    def test_empty_search_completes_without_creating_output(self):
        data = self.scan()
        self.assertEqual(data["scan_root"], str(self.scan_root))
        self.assertEqual(data["project"], "example")
        self.assertEqual(data["issue"], 123)
        self.assertEqual(
            {name: data["limits"][name] for name in ("max_depth", "max_repos", "max_commits")},
            {"max_depth": 6, "max_repos": 50, "max_commits": 100},
        )
        self.assertEqual(data["repositories"], [])
        self.assertEqual(data["reports"], [])
        self.assertEqual(data["warnings"], [])
        self.assertIs(data["incomplete"], False)
        self.assertEqual(list(self.scan_root.iterdir()), [])

    def test_text_format_includes_matching_checkout_and_branch(self):
        repo = self.make_repository("text-checkout", branch="fix-123")
        result = self.run_cli(
            "--scan-root", str(self.scan_root), "--project", "example",
            "--issue", "123", "--format", "text",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(repo), result.stdout)
        self.assertIn("fix-123", result.stdout)

    def test_requires_explicit_scan_root_project_and_issue(self):
        selectors = [
            ["--scan-root", str(self.scan_root)],
            ["--project", "example"],
            ["--issue", "123"],
        ]
        for missing in range(3):
            with self.subTest(missing=selectors[missing][0]):
                args = [arg for index, selector in enumerate(selectors) if index != missing for arg in selector]
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn(selectors[missing][0], result.stderr)
        self.assertEqual(list(self.scan_root.iterdir()), [])

    def test_rejects_invalid_issue_and_limit_values(self):
        for option, value in (
            ("--issue", "0"), ("--issue", "-1"), ("--issue", "abc"),
            ("--max-depth", "-1"), ("--max-depth", "abc"),
            ("--max-repos", "0"), ("--max-repos", "-1"),
            ("--max-commits", "0"), ("--max-commits", "-1"),
        ):
            with self.subTest(option=option, value=value):
                result = self.run_cli(
                    "--scan-root", str(self.scan_root), "--project", "example",
                    "--issue", "123", option, value,
                )
                self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual(list(self.scan_root.iterdir()), [])

    def test_zero_depth_is_accepted(self):
        data = self.scan("--max-depth", "0")
        self.assertEqual(data["limits"]["max_depth"], 0)
        self.assertIs(data["incomplete"], False)

    def test_missing_or_file_scan_root_returns_operational_error(self):
        file_root = self.root / "file.txt"
        file_root.write_text("not a directory\n", encoding="utf-8")
        for scan_root in (self.root / "does-not-exist", file_root):
            with self.subTest(scan_root=scan_root):
                result = self.run_cli(
                    "--scan-root", str(scan_root), "--project", "example",
                    "--issue", "123", "--format", "json",
                )
                self.assertEqual(result.returncode, 40, result.stderr + result.stdout)
                data = json.loads(result.stdout)
                self.assertIs(data["incomplete"], True)
                self.assertTrue(data["warnings"])
                self.assertEqual(data["repositories"], [])
                self.assertEqual(data["reports"], [])

    def test_symlink_directory_does_not_expand_the_scan_boundary(self):
        outside = self.root / "outside"
        outside.mkdir()
        external_repo = self.make_repository("checkout", branch="fix-123", parent=outside)
        (self.scan_root / "outside-link").symlink_to(outside, target_is_directory=True)
        data = self.scan()
        self.assertEqual(data["repositories"], [])
        self.assertNotIn(str(external_repo), json.dumps(data["repositories"]))

    @staticmethod
    def inventory(root):
        """Record all entries, including Git metadata, without following symlinks."""
        inventory = {}
        for directory, directories, files in os.walk(root, followlinks=False):
            for path in [Path(directory)] + [Path(directory) / name for name in directories + files]:
                metadata = path.lstat()
                record = [stat.S_IFMT(metadata.st_mode), stat.S_IMODE(metadata.st_mode), metadata.st_mtime_ns]
                if path.is_symlink():
                    record.append(os.readlink(path))
                elif path.is_file():
                    record.extend([metadata.st_size, hashlib.sha256(path.read_bytes()).hexdigest()])
                inventory[str(path.relative_to(root))] = record
        return inventory

    def test_scan_preserves_files_git_index_worktree_metadata_and_malformed_context(self):
        repo = self.make_repository("read-only-checkout", branch="fix-123")
        linked = self.scan_root / "linked"
        self.git(repo, "worktree", "add", "-b", "fix-123-linked", str(linked), "HEAD")
        clean_file = repo / "same-content.txt"
        clean_file.write_text("unchanged content\n", encoding="utf-8")
        self.git(repo, "add", "same-content.txt")
        self.git(repo, "commit", "--quiet", "-m", "Add clean file for index refresh check")
        # A normal git status can refresh this file's index entry and write .git/index.
        file_stat = clean_file.stat()
        os.utime(clean_file, ns=(file_stat.st_atime_ns, file_stat.st_mtime_ns + 2_000_000_000))
        (repo / "tracked.txt").write_text("unfinished local changes\n", encoding="utf-8")
        (linked / "untracked.txt").write_text("unfinished worktree changes\n", encoding="utf-8")
        self.write_report("matching-report")
        legacy_context = self.scan_root / "LOCAL_CONTEXT.json"
        legacy_context.write_bytes(b'{"malformed legacy context": [\n')

        # Run a fresh copy so the inventory also detects any bytecode files.
        tool_root = self.root / "tool"
        for directory in ("lib", "scripts"):
            shutil.copytree(
                REPOSITORY / directory, tool_root / directory,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        copied_cli = tool_root / "scripts" / "contribute_fix.py"
        before = self.inventory(self.root)
        data = self.scan(cli=copied_cli)
        after = self.inventory(self.root)
        changed = [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]
        self.assertEqual(changed, [], "Read-only scan changed these paths: " + repr(changed))
        self.assertEqual(legacy_context.read_bytes(), b'{"malformed legacy context": [\n')
        repositories = self.repositories_by_path(data)
        self.assertIs(repositories[str(repo)]["dirty"], True)
        self.assertIs(repositories[str(linked)]["dirty"], True)
        self.assertTrue(any(path.endswith(".git/index") for path in before))
        self.assertTrue(any(".git/worktrees/" in path for path in before))


if __name__ == "__main__":
    unittest.main()

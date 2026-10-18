"""Check search limits, Git failures, and configured Git side effects."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import context_search


class TestContextSearchLimits(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def report(self, parent):
        parent.mkdir(parents=True, exist_ok=True)
        path = parent / "REPORT.md"
        path.write_text(
            "# Contribution report\n\n**Project:** example\n"
            "**Issue:** https://www.drupal.org/node/123\n\n## Result\n",
            encoding="utf-8",
        )
        return path

    def scan(self, **kwargs):
        return context_search.search_context(self.root, "example", 123, **kwargs)

    def test_depth_limit_is_declared_scope(self):
        self.report(self.root / "child")
        bounded = self.scan(max_depth=0)
        self.assertFalse(bounded["incomplete"])
        self.assertEqual(bounded["reports"], [])
        self.assertEqual(len(self.scan(max_depth=1)["reports"]), 1)

    def test_directory_limit_does_not_claim_complete_no_match(self):
        self.report(self.root / "child")
        with patch.object(context_search, "MAX_DIRECTORIES", 1):
            result = self.scan()
        self.assertTrue(result["incomplete"])
        self.assertTrue(any("Directory limit" in warning for warning in result["warnings"]))

    def test_oversized_report_is_incomplete_and_unchanged(self):
        report = self.report(self.root)
        before = report.read_bytes()
        with patch.object(context_search, "MAX_FILE_BYTES", 16):
            result = self.scan()
        self.assertTrue(result["incomplete"])
        self.assertEqual(result["reports"], [])
        self.assertEqual(report.read_bytes(), before)

    def test_missing_git_or_timeout_keeps_report_results(self):
        (self.root / ".git").mkdir()
        report = self.report(self.root)
        failures = [
            FileNotFoundError("git"),
            subprocess.TimeoutExpired("git", 5, output="PRIVATE_REMOTE_VALUE"),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__), patch.object(
                context_search.subprocess, "run", side_effect=failure
            ):
                result = self.scan()
            self.assertTrue(result["incomplete"])
            self.assertEqual([item["path"] for item in result["reports"]], [str(report)])
            self.assertNotIn("PRIVATE_REMOTE_VALUE", json.dumps(result))

    def test_failed_git_does_not_expose_remote_error_text(self):
        (self.root / ".git").mkdir()
        failure = subprocess.CompletedProcess(
            ["git"], 128, stdout="", stderr="https://user:PRIVATE_REMOTE_VALUE@example.invalid"
        )
        with patch.object(context_search.subprocess, "run", return_value=failure):
            result = self.scan()
        self.assertTrue(result["incomplete"])
        self.assertNotIn("PRIVATE_REMOTE_VALUE", json.dumps(result))

    def test_directory_read_error_is_reported(self):
        def fail_walk(root, **kwargs):
            kwargs["onerror"](PermissionError(13, "Permission denied", str(root / "private")))
            return iter(())

        with patch.object(context_search.os, "walk", side_effect=fail_walk):
            result = self.scan()
        self.assertTrue(result["incomplete"])
        self.assertIn("private", result["warnings"][0])


@unittest.skipUnless(shutil.which("git"), "Git is required for context search tests")
class TestContextGitReads(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith("GIT_"):
                del self.env[key]
        self.env.update({
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Context Test", "GIT_COMMITTER_NAME": "Context Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def git(self, repo, *args):
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def repository(self, name):
        repo = self.root / name
        repo.mkdir()
        self.git(repo, "init", "--quiet")
        self.git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
        self.git(repo, "remote", "add", "origin", "https://git.drupalcode.org/project/example.git")
        (repo / "file.txt").write_text("initial\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "--quiet", "-m", "Issue #123: Initial work")
        return repo

    def scan(self, **kwargs):
        return context_search.search_context(self.root, "example", 123, **kwargs)

    def test_status_does_not_run_clean_filters_process_filters_or_fsmonitor(self):
        repo = self.repository("filters")
        (repo / ".gitattributes").write_text(
            "file.txt filter=cleanprobe\nprocess.txt filter=processprobe\n", encoding="utf-8"
        )
        (repo / "process.txt").write_text("initial\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "--quiet", "-m", "Add file attributes")
        self.git(repo, "config", "filter.cleanprobe.clean", "touch CLEAN_FILTER_RAN; cat")
        self.git(repo, "config", "filter.cleanprobe.required", "true")
        self.git(repo, "config", "filter.processprobe.process", "touch PROCESS_FILTER_RAN; exit 1")
        self.git(repo, "config", "filter.processprobe.required", "true")
        self.git(repo, "config", "core.fsmonitor", "touch FSMONITOR_RAN")
        (repo / "file.txt").write_text("changed\n", encoding="utf-8")
        (repo / "process.txt").write_text("changed\n", encoding="utf-8")
        index_before = (repo / ".git" / "index").read_bytes()
        result = self.scan()
        self.assertFalse(result["incomplete"], result["warnings"])
        self.assertTrue(result["repositories"][0]["dirty"])
        self.assertEqual(list(repo.glob("*_RAN")), [])
        self.assertEqual((repo / ".git" / "index").read_bytes(), index_before)

    def test_repository_cap_reports_omitted_checkouts(self):
        first = self.repository("a")
        self.repository("b")
        result = self.scan(max_repos=1)
        self.assertEqual([item["path"] for item in result["repositories"]], [str(first)])
        self.assertTrue(result["incomplete"])
        self.assertTrue(any("Repository limit" in warning for warning in result["warnings"]))

    def test_commit_limit_is_declared_scope(self):
        repo = self.repository("history")
        self.git(repo, "commit", "--quiet", "--allow-empty", "-m", "Unrelated later change")
        bounded = self.scan(max_commits=1)
        self.assertFalse(bounded["incomplete"])
        self.assertEqual(bounded["repositories"][0]["matches"], [])
        expanded = self.scan(max_commits=2)
        self.assertEqual([match["kind"] for match in expanded["repositories"][0]["matches"]], ["commit"])

    def test_inherited_repository_environment_does_not_redirect_search(self):
        repo = self.repository("requested")
        foreign = self.repository("foreign")
        self.git(foreign, "remote", "set-url", "origin", "https://git.drupalcode.org/project/other.git")
        with patch.dict(os.environ, {"GIT_DIR": str(foreign / ".git"), "GIT_WORK_TREE": str(foreign)}):
            result = self.scan()
        self.assertFalse(result["incomplete"], result["warnings"])
        self.assertEqual([item["path"] for item in result["repositories"]], [str(repo)])

    def test_issue_branch_without_commits_is_still_a_match(self):
        repo = self.root / "new-checkout"
        repo.mkdir()
        self.git(repo, "init", "--quiet")
        self.git(repo, "symbolic-ref", "HEAD", "refs/heads/fix-123")
        self.git(repo, "remote", "add", "origin", "https://git.drupalcode.org/project/example.git")
        result = self.scan()
        self.assertFalse(result["incomplete"], result["warnings"])
        item = result["repositories"][0]
        self.assertIsNone(item["head"])
        self.assertEqual([match["value"] for match in item["matches"]], ["fix-123"])

    def test_unborn_current_branch_does_not_hide_commits_on_other_refs(self):
        repo = self.repository("orphan")
        self.git(repo, "symbolic-ref", "HEAD", "refs/heads/new-orphan")
        result = self.scan()
        self.assertFalse(result["incomplete"], result["warnings"])
        item = result["repositories"][0]
        self.assertIsNone(item["head"])
        self.assertEqual([match["kind"] for match in item["matches"]], ["commit"])

    def test_parent_status_does_not_run_filters_in_a_submodule(self):
        source = self.repository("source")
        (source / ".gitattributes").write_text("file.txt filter=probe\n", encoding="utf-8")
        self.git(source, "add", ".gitattributes")
        self.git(source, "commit", "--quiet", "-m", "Add filter attribute")
        parent = self.repository("parent")
        self.git(parent, "-c", "protocol.file.allow=always", "submodule", "add", "--quiet", str(source), "nested")
        self.git(parent, "commit", "--quiet", "-am", "Add submodule")
        nested = parent / "nested"
        self.git(nested, "config", "filter.probe.clean", "touch SUBMODULE_FILTER_RAN; cat")
        (nested / "file.txt").write_text("changed submodule file\n", encoding="utf-8")
        result = context_search.search_context(parent, "example", 123, max_depth=0)
        self.assertFalse(result["incomplete"], result["warnings"])
        self.assertFalse((nested / "SUBMODULE_FILTER_RAN").exists())

    def test_commit_lookup_does_not_run_signature_programs(self):
        repo = self.repository("signed")
        tree = self.git(repo, "rev-parse", "HEAD^{tree}")
        parent = self.git(repo, "rev-parse", "HEAD")
        commit = (
            f"tree {tree}\nparent {parent}\n"
            "author Context Test <test@example.invalid> 1700000000 +0000\n"
            "committer Context Test <test@example.invalid> 1700000000 +0000\n"
            "gpgsig -----BEGIN PGP SIGNATURE-----\n fake\n -----END PGP SIGNATURE-----\n"
            "\nIssue #123: Signed work\n"
        )
        object_result = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "-t", "commit", "-w", "--stdin"],
            input=commit, text=True, capture_output=True, check=True, timeout=20,
        )
        self.git(repo, "update-ref", "HEAD", object_result.stdout.strip())
        program = self.root / "signature-program"
        program.write_text("#!/bin/sh\ntouch SIGNATURE_PROGRAM_RAN\nexit 1\n", encoding="utf-8")
        program.chmod(0o755)
        self.git(repo, "config", "gpg.program", str(program))
        self.git(repo, "config", "log.showSignature", "true")
        result = self.scan()
        self.assertFalse(result["incomplete"], result["warnings"])
        self.assertFalse((repo / "SIGNATURE_PROGRAM_RAN").exists())
        self.git(repo, "log", "-1", "--format=%s")
        self.assertTrue((repo / "SIGNATURE_PROGRAM_RAN").exists())

    def test_split_indexes_remain_unchanged_and_status_is_unknown(self):
        repo = self.repository("split")
        linked = self.root / "linked-split"
        self.git(repo, "worktree", "add", "-b", "linked", str(linked), "HEAD")
        shared_files = []
        for checkout in (repo, linked):
            self.git(checkout, "update-index", "--split-index")
            index = Path(self.git(checkout, "rev-parse", "--git-path", "index"))
            if not index.is_absolute():
                index = checkout / index
            files = list(index.parent.glob("sharedindex.*"))
            self.assertTrue(files)
            for path in files:
                os.utime(path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
            shared_files.extend(files + [index])
        before = {str(path): (path.stat().st_mtime_ns, path.read_bytes()) for path in shared_files}
        result = self.scan()
        after = {str(path): (path.stat().st_mtime_ns, path.read_bytes()) for path in shared_files}
        self.assertEqual(after, before)
        self.assertTrue(result["incomplete"])
        self.assertEqual(len(result["repositories"]), 2)
        self.assertTrue(all(item["dirty"] is None for item in result["repositories"]))
        self.assertTrue(all(item["matches"] for item in result["repositories"]))

    def test_configured_worktree_cannot_redirect_status_outside_scan_root(self):
        repo = self.repository("requested")
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "OUTSIDE_PRIVATE_FILENAME.txt").write_text("outside data\n", encoding="utf-8")
        self.git(repo, "config", "core.worktree", str(outside))
        result = context_search.search_context(repo, "example", 123)
        self.assertTrue(result["incomplete"])
        self.assertEqual(len(result["repositories"]), 1)
        self.assertIsNone(result["repositories"][0]["dirty"])
        self.assertEqual(result["repositories"][0]["status"], [])
        self.assertNotIn("OUTSIDE_PRIVATE_FILENAME", json.dumps(result))


if __name__ == "__main__":
    unittest.main()

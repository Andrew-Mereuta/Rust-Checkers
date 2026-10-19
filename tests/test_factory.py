from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ai_factory import cleanup, command, github, pipeline, review
from ai_factory.context import RunContext


class PublishTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.git("init", "-q", "-b", "develop")
        self.git("config", "user.name", "Factory Test")
        self.git("config", "user.email", "factory@example.com")
        (self.repo / "main.rs").write_text("fn main() {}\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Initial")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.context = RunContext(
            self.repo, self.repo / "001-engine.md", "# Task: implement engine\n",
            self.repo, "factory/task-123", base,
        )

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        )

    def test_publish_includes_new_files_and_deletions(self):
        (self.repo / "main.rs").unlink()
        (self.repo / "lib.rs").write_text("pub fn engine() {}\n")
        calls = []
        real_run = command.run

        def run_without_network(args, cwd, prompt=None):
            if args[:2] == ["git", "push"]:
                calls.append(args)
                return subprocess.CompletedProcess(args, 0, "", "")
            return real_run(args, cwd, prompt)

        with patch.object(command, "run", side_effect=run_without_network):
            github.publish(self.context, self.context.base_commit, self.context.title)

        changed = self.git("diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD").stdout
        self.assertIn("A\tlib.rs", changed)
        self.assertIn("D\tmain.rs", changed)
        self.assertEqual(calls[0][:2], ["git", "push"])

    def test_no_changes_does_not_push(self):
        with patch.object(command, "run", wraps=command.run) as run:
            with self.assertRaisesRegex(RuntimeError, "No changes"):
                github.publish(self.context, self.context.base_commit, self.context.title)
        self.assertFalse(any(args[0][:2] == ["git", "push"] for args in run.call_args_list))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.task_path = self.root / "001-engine.md"
        self.task_path.write_text("# Task: implement engine\n")
        self.context = RunContext(
            self.root, self.task_path, self.task_path.read_text(),
            self.root / "worktree", "factory/task-123", "base-sha",
        )

    def run_with_reviews(self, verdicts, merged=True):
        with (
            patch.object(pipeline.github, "preflight"),
            patch.object(pipeline.workspace, "create", return_value=self.context),
            patch.object(pipeline.implementation, "implement"),
            patch.object(pipeline.verification, "check", return_value=[]),
            patch.object(pipeline.github, "publish") as publish,
            patch.object(pipeline.github, "open_pr", return_value="https://example/pr/1"),
            patch.object(pipeline.review, "inspect", side_effect=verdicts) as inspect,
            patch.object(pipeline.github, "comment") as comment,
            patch.object(pipeline.github, "head_commit", return_value="review-base"),
            patch.object(pipeline.apply_comments, "apply") as apply,
            patch.object(pipeline.github, "request_merge") as merge,
            patch.object(pipeline.github, "wait_for_merge", return_value=merged) as wait,
            patch.object(pipeline.cleanup, "cleanup_merged") as cleanup,
        ):
            result = pipeline.run_pipeline(self.root, self.task_path)
        return result, publish, inspect, comment, apply, merge, wait, cleanup

    def test_finding_is_applied_then_second_review_can_merge(self):
        result, publish, inspect, comment, apply, merge, wait, cleanup = self.run_with_reviews([
            review.Review(False, ["lib.rs:10: Fix capture rule"]),
            review.Review(True, []),
        ])
        self.assertEqual(result.status, "merged and cleaned")
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(inspect.call_count, 2)
        self.assertEqual(comment.call_count, 2)
        apply.assert_called_once()
        merge.assert_called_once()
        wait.assert_called_once()
        cleanup.assert_called_once()

    def test_second_review_with_findings_leaves_pr_open(self):
        result, publish, inspect, comment, apply, merge, wait, cleanup = self.run_with_reviews([
            review.Review(False, ["lib.rs:10: Fix capture rule"]),
            review.Review(False, ["lib.rs:20: Add coverage"]),
        ])
        self.assertEqual(result.status, "needs attention")
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(inspect.call_count, 2)
        self.assertEqual(comment.call_count, 2)
        apply.assert_called_once()
        merge.assert_not_called()
        wait.assert_not_called()
        cleanup.assert_not_called()

    def test_pending_merge_preserves_worktree_for_later_cleanup(self):
        result, _, _, _, _, merge, wait, cleanup = self.run_with_reviews(
            [review.Review(True, [])], merged=False
        )
        self.assertEqual(result.status, "awaiting merge; cleanup can be retried later")
        merge.assert_called_once()
        wait.assert_called_once()
        cleanup.assert_not_called()

    def test_failed_verification_does_not_open_pr(self):
        with (
            patch.object(pipeline.github, "preflight"),
            patch.object(pipeline.workspace, "create", return_value=self.context),
            patch.object(pipeline.implementation, "implement"),
            patch.object(pipeline.implementation, "repair_verification") as repair,
            patch.object(pipeline.verification, "check", return_value=["cargo test failed"]) as check,
            patch.object(pipeline.github, "publish") as publish,
            patch.object(pipeline.github, "open_pr") as open_pr,
        ):
            with self.assertRaisesRegex(RuntimeError, "Verification failed"):
                pipeline.run_pipeline(self.root, self.task_path)
        self.assertEqual(check.call_count, 3)
        self.assertEqual(repair.call_count, 2)
        publish.assert_not_called()
        open_pr.assert_not_called()


class MergeAndCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.root = self.parent / "repo"
        self.root.mkdir()
        self.branch = "factory/task-" + "a" * 32
        self.workspace = self.parent / ("checkers-agent-" + "a" * 32)
        self.git("init", "-q", "-b", "develop")
        self.git("config", "user.name", "Factory Test")
        self.git("config", "user.email", "factory@example.com")
        (self.root / "main.rs").write_text("fn main() {}\n")
        (self.root / ".gitignore").write_text("/target\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Initial")
        self.git("worktree", "add", "-q", "-b", self.branch, str(self.workspace), "HEAD")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        self.pr_url = "https://github.com/example/repo/pull/42"

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        )

    def details(self, state="MERGED", head=None):
        return {
            "number": 42,
            "state": state,
            "headRefName": self.branch,
            "headRefOid": head or self.head,
        }

    def test_merge_subject_uses_task_id_title_and_pr_number(self):
        context = RunContext(
            self.root, self.root / "001-engine.md",
            "# Task: implement the checkers engine\n", self.workspace,
            self.branch, self.head, pr_url=self.pr_url,
        )
        self.assertEqual(
            context.merge_subject(42),
            "CHECK-001 Implement the checkers engine (#42)",
        )
        with (
            patch.object(github, "pr_details", return_value=self.details(state="OPEN")),
            patch.object(github, "head_commit", return_value=self.head),
            patch.object(command, "checked_run", return_value="") as checked_run,
        ):
            github.request_merge(context)
        merge_command = checked_run.call_args.args[0]
        self.assertEqual(
            merge_command[merge_command.index("--subject") + 1],
            "CHECK-001 Implement the checkers engine (#42)",
        )

    def test_waits_until_github_reports_merged(self):
        context = RunContext(
            self.root, self.root / "001-engine.md", "# Task: implement engine\n",
            self.workspace, self.branch, self.head, pr_url=self.pr_url,
        )
        with (
            patch.object(github, "pr_details", side_effect=[
                self.details(state="OPEN"), self.details(state="MERGED")
            ]) as details,
            patch.object(github.time, "sleep") as sleep,
        ):
            self.assertTrue(github.wait_for_merge(context))
        self.assertEqual(details.call_count, 2)
        sleep.assert_called_once_with(15)

    def test_merge_request_accepts_pr_already_merged(self):
        context = RunContext(
            self.root, self.root / "001-engine.md", "# Task: implement engine\n",
            self.workspace, self.branch, self.head, pr_url=self.pr_url,
        )
        with (
            patch.object(github, "pr_details", return_value=self.details()),
            patch.object(command, "checked_run") as checked_run,
        ):
            github.request_merge(context)
        checked_run.assert_not_called()

    def test_cleanup_removes_merged_branch_and_worktree(self):
        build_output = self.workspace / "target" / "cache.bin"
        build_output.parent.mkdir()
        build_output.write_bytes(b"build artifact")
        real_checked_run = command.checked_run

        def checked_run_without_remote(args, cwd, prompt=None):
            if args[:2] == ["git", "ls-remote"]:
                return ""
            return real_checked_run(args, cwd, prompt)

        with (
            patch.object(github, "pr_details", return_value=self.details()),
            patch.object(command, "checked_run", side_effect=checked_run_without_remote),
        ):
            cleaned = cleanup.cleanup_merged(self.root, self.pr_url, self.branch)

        self.assertEqual(cleaned, self.workspace)
        self.assertFalse(self.workspace.exists())
        self.assertEqual(self.git("branch", "--list", self.branch).stdout.strip(), "")

    def test_cleanup_deletes_matching_remote_branch(self):
        real_checked_run = command.checked_run
        deleted = []

        def checked_run_without_network(args, cwd, prompt=None):
            if args[:2] == ["git", "ls-remote"]:
                return f"{self.head}\trefs/heads/{self.branch}"
            if args[:3] == ["git", "push", "origin"]:
                deleted.append(args)
                return ""
            return real_checked_run(args, cwd, prompt)

        with (
            patch.object(github, "pr_details", return_value=self.details()),
            patch.object(command, "checked_run", side_effect=checked_run_without_network),
        ):
            cleanup.cleanup_merged(self.root, self.pr_url, self.branch)
        self.assertEqual(deleted, [["git", "push", "origin", "--delete", self.branch]])
        self.assertFalse(self.workspace.exists())

    def test_cleanup_preserves_remote_branch_with_new_commits(self):
        real_checked_run = command.checked_run

        def checked_run_with_new_remote_commit(args, cwd, prompt=None):
            if args[:2] == ["git", "ls-remote"]:
                return f"{'f' * 40}\trefs/heads/{self.branch}"
            return real_checked_run(args, cwd, prompt)

        with (
            patch.object(github, "pr_details", return_value=self.details()),
            patch.object(command, "checked_run", side_effect=checked_run_with_new_remote_commit),
        ):
            with self.assertRaisesRegex(RuntimeError, "Remote branch has commits"):
                cleanup.cleanup_merged(self.root, self.pr_url, self.branch)
        self.assertTrue(self.workspace.exists())

    def test_cleanup_preserves_open_pr(self):
        with patch.object(github, "pr_details", return_value=self.details(state="OPEN")):
            with self.assertRaisesRegex(RuntimeError, "not merged"):
                cleanup.cleanup_merged(self.root, self.pr_url, self.branch)
        self.assertTrue(self.workspace.exists())

    def test_cleanup_preserves_dirty_worktree(self):
        (self.workspace / "new-file.txt").write_text("keep me\n")
        with patch.object(github, "pr_details", return_value=self.details()):
            with self.assertRaisesRegex(RuntimeError, "uncommitted changes"):
                cleanup.cleanup_merged(self.root, self.pr_url, self.branch)
        self.assertTrue(self.workspace.exists())


if __name__ == "__main__":
    unittest.main()

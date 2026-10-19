from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import factory


class OpenPrTests(unittest.TestCase):
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
        self.base_commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.task_path = self.repo / "task.md"

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        )

    def test_pr_includes_new_files_and_deletions(self):
        (self.repo / "main.rs").unlink()
        (self.repo / "lib.rs").write_text("pub fn engine() {}\n")
        self.task_path.write_text("# Implement engine\n")
        calls = []
        real_run = factory.run

        def run_without_network(command, cwd=factory.ROOT, prompt=None):
            if command[:2] == ["git", "push"] or command[:3] == ["gh", "pr", "create"]:
                calls.append(command)
                output = "https://github.com/example/repo/pull/1\n" if command[0] == "gh" else ""
                return subprocess.CompletedProcess(command, 0, output, "")
            return real_run(command, cwd=cwd, prompt=prompt)

        with patch.object(factory, "run", side_effect=run_without_network):
            url = factory.open_pr(
                self.repo, "factory/task-123", self.base_commit,
                self.task_path, "# Implement engine\n",
            )

        self.assertEqual(url, "https://github.com/example/repo/pull/1")
        changed = self.git("diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD").stdout
        self.assertIn("A\tlib.rs", changed)
        self.assertIn("D\tmain.rs", changed)
        self.assertIn("A\ttask.md", changed)
        self.assertEqual(calls[0][:2], ["git", "push"])
        self.assertEqual(calls[1][:3], ["gh", "pr", "create"])
        self.assertIn("develop", calls[1])

    def test_no_changes_does_not_push(self):
        self.task_path.write_text("# Implement engine\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "Task file")
        base_commit = self.git("rev-parse", "HEAD").stdout.strip()

        with self.assertRaisesRegex(RuntimeError, "no changes"):
            factory.open_pr(self.repo, "factory/task-123", base_commit,
                            self.task_path, "# Implement engine\n")


if __name__ == "__main__":
    unittest.main()

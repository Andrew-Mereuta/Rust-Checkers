"""Create an isolated branch and worktree for a task."""

from pathlib import Path
from uuid import uuid4

from ai_factory import command
from ai_factory.context import RunContext


def create(root: Path, task_path: Path, task: str) -> RunContext:
    base_commit = command.checked_run(["git", "rev-parse", "HEAD"], root)
    run_id = uuid4().hex
    workspace = root.parent / f"checkers-agent-{run_id}"
    branch = f"factory/task-{run_id}"
    command.checked_run(
        ["git", "worktree", "add", "-b", branch, str(workspace), base_commit], root
    )
    return RunContext(root, task_path, task, workspace, branch, base_commit)

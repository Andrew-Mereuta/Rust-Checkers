"""Remove a factory branch and worktree after its PR has merged."""

from pathlib import Path
import re

from ai_factory import command, github


def _worktree_for_branch(root: Path, branch: str) -> Path | None:
    output = command.checked_run(["git", "worktree", "list", "--porcelain"], root)
    for block in output.split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines() if " " in line)
        if fields.get("branch") == f"refs/heads/{branch}":
            return Path(fields["worktree"])
    return None


def cleanup_merged(root: Path, pr_url: str, expected_branch: str | None = None) -> Path:
    details = github.pr_details(root, pr_url)
    if details.get("state") != "MERGED":
        raise RuntimeError("PR is not merged; preserving its branch and worktree")

    branch = details.get("headRefName")
    match = re.fullmatch(r"factory/task-([0-9a-f]{32})", branch or "")
    if match is None or (expected_branch is not None and branch != expected_branch):
        raise RuntimeError("PR branch does not match a factory task branch")
    merged_head = details.get("headRefOid")
    if not isinstance(merged_head, str) or not merged_head:
        raise RuntimeError("GitHub did not return the PR head commit")

    expected_workspace = root.parent / f"checkers-agent-{match.group(1)}"
    registered_workspace = _worktree_for_branch(root, branch)
    if registered_workspace is not None:
        if registered_workspace.resolve() != expected_workspace.resolve():
            raise RuntimeError("Task branch is checked out in an unexpected worktree")
        status = command.checked_run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            registered_workspace,
        )
        if status:
            raise RuntimeError(f"Worktree has uncommitted changes: {registered_workspace}")

    local = command.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], root
    )
    if local.returncode == 0:
        local_head = command.checked_run(["git", "rev-parse", branch], root)
        if local_head != merged_head:
            raise RuntimeError("Local branch has commits beyond the merged PR head")
    elif local.returncode != 1:
        raise RuntimeError(local.stderr)

    remote = command.checked_run(
        ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"], root
    )
    if remote:
        remote_head = remote.split()[0]
        if remote_head != merged_head:
            raise RuntimeError("Remote branch has commits beyond the merged PR head")
        command.checked_run(["git", "push", "origin", "--delete", branch], root)

    if registered_workspace is not None:
        command.checked_run(
            ["git", "worktree", "remove", "--force", str(registered_workspace)], root
        )
    if local.returncode == 0:
        command.checked_run(["git", "branch", "-D", branch], root)
    return expected_workspace

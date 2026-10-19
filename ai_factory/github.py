"""Git and GitHub operations for PR publication and review."""

import json
import shutil
import time

from ai_factory import command
from ai_factory.context import RunContext


def preflight(root) -> None:
    if shutil.which("gh") is None:
        raise RuntimeError("GitHub CLI (gh) is required to open a PR")
    command.checked_run(["gh", "auth", "status", "--hostname", "github.com"], root)


def head_commit(context: RunContext) -> str:
    return command.checked_run(["git", "rev-parse", "HEAD"], context.workspace)


def publish(context: RunContext, baseline: str, message: str) -> None:
    command.checked_run(["git", "add", "-A"], context.workspace)
    changes = command.run(
        ["git", "diff", "--cached", "--quiet", baseline], context.workspace
    )
    if changes.returncode == 0:
        raise RuntimeError("No changes to publish")
    if changes.returncode != 1:
        raise RuntimeError(changes.stderr)
    command.checked_run(
        ["git", "diff", "--cached", "--check", baseline], context.workspace
    )

    uncommitted = command.run(
        ["git", "diff", "--cached", "--quiet", "HEAD"], context.workspace
    )
    if uncommitted.returncode == 1:
        command.checked_run(["git", "commit", "-m", message], context.workspace)
    elif uncommitted.returncode != 0:
        raise RuntimeError(uncommitted.stderr)

    command.checked_run(
        ["git", "push", "--set-upstream", "origin", context.branch], context.workspace
    )


def open_pr(context: RunContext) -> str:
    return command.checked_run(
        ["gh", "pr", "create", "--base", context.base_branch,
         "--head", context.branch, "--title", context.title,
         "--body-file", str(context.task_path)],
        context.workspace,
    )


def comment(context: RunContext, body: str) -> None:
    if context.pr_url is None:
        raise RuntimeError("Cannot comment before opening a PR")
    command.checked_run(
        ["gh", "pr", "comment", context.pr_url, "--body", body], context.workspace
    )


def pr_details(root, pr_url: str) -> dict:
    output = command.checked_run(
        ["gh", "pr", "view", pr_url, "--json",
         "number,state,headRefName,headRefOid"], root
    )
    return json.loads(output)


def request_merge(context: RunContext) -> None:
    if context.pr_url is None:
        raise RuntimeError("Cannot merge before opening a PR")
    details = pr_details(context.root, context.pr_url)
    if details.get("headRefName") != context.branch:
        raise RuntimeError("PR is not on the expected task branch")
    if details.get("state") == "MERGED":
        return
    if details.get("state") != "OPEN":
        raise RuntimeError("PR is not open for merging")
    number = details.get("number")
    if not isinstance(number, int):
        raise RuntimeError("GitHub did not return a PR number")
    command.checked_run(
        ["gh", "pr", "merge", context.pr_url, "--auto", "--squash",
         "--subject", context.merge_subject(number),
         "--match-head-commit", head_commit(context)],
        context.workspace,
    )


def wait_for_merge(context: RunContext, timeout_seconds: int | None = None,
                   poll_seconds: int = 15) -> bool:
    if context.pr_url is None:
        raise RuntimeError("Cannot wait for a PR that has not been opened")
    deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
    while True:
        state = pr_details(context.root, context.pr_url).get("state")
        if state == "MERGED":
            return True
        if state == "CLOSED":
            raise RuntimeError("PR was closed without merging")
        if state != "OPEN":
            raise RuntimeError(f"Unexpected PR state: {state}")
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(poll_seconds, remaining))
        else:
            time.sleep(poll_seconds)

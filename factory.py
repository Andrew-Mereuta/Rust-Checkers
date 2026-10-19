
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
BASE_BRANCH = "develop"


def run(command, cwd=ROOT, prompt=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=600,
    )
    return result


def checked_run(command, cwd=ROOT):
    result = run(command, cwd=cwd)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return result.stdout.strip()


def agent(workspace, prompt, sandbox="workspace-write"):
    result = run(
        [
            "codex", "exec",
            "--cd", str(workspace),
            "--sandbox", sandbox,
            "-"
        ],
        prompt=prompt,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout


def verify(workspace):
    commands = [
        ["cargo", "fmt", "--check"],
        ["cargo", "clippy", "--", "-D", "warnings"],
        ["cargo", "test"],
    ]

    failures = []
    for command in commands:
        result = run(command, cwd=workspace)
        print(f"{' '.join(command)}: {result.returncode}")

        if result.returncode != 0:
            failures.append(
                result.stdout + "\n" + result.stderr
            )

    return failures


def open_pr(workspace, branch, base_commit, task_path, task):
    checked_run(["git", "add", "-A"], cwd=workspace)

    changes = run(["git", "diff", "--cached", "--quiet", base_commit], cwd=workspace)
    if changes.returncode == 0:
        raise RuntimeError("The agent made no changes; no PR was opened.")
    if changes.returncode != 1:
        raise RuntimeError(changes.stderr)

    checked_run(["git", "diff", "--cached", "--check", base_commit], cwd=workspace)
    title = next(
        (line.lstrip("# ").strip() for line in task.splitlines() if line.strip()),
        task_path.stem,
    )

    uncommitted = run(["git", "diff", "--cached", "--quiet", "HEAD"], cwd=workspace)
    if uncommitted.returncode == 1:
        checked_run(["git", "commit", "-m", title], cwd=workspace)
    elif uncommitted.returncode != 0:
        raise RuntimeError(uncommitted.stderr)

    checked_run(["git", "push", "--set-upstream", "origin", branch], cwd=workspace)
    return checked_run(
        [
            "gh", "pr", "create",
            "--base", BASE_BRANCH,
            "--head", branch,
            "--title", title,
            "--body-file", str(task_path),
        ],
        cwd=workspace,
    )


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 factory.py <task-file>")

    task_path = ROOT / sys.argv[1]
    task = task_path.read_text()
    if not task.strip():
        sys.exit(f"Task file is empty: {task_path}")
    if shutil.which("gh") is None:
        sys.exit("GitHub CLI (gh) is required to open a PR.")
    checked_run(["gh", "auth", "status", "--hostname", "github.com"])

    base_commit = checked_run(["git", "rev-parse", "HEAD"])
    run_id = uuid4().hex
    workspace = ROOT.parent / f"checkers-agent-{run_id}"
    branch = f"factory/task-{run_id}"

    result = run([
        "git", "worktree", "add",
        "-b", branch, str(workspace), "HEAD"
    ])
    if result.returncode:
        raise RuntimeError(result.stderr)
    print("Workspace:", workspace)

    prompt = task

    for attempt in range(3):
        print(f"\nImplementation attempt {attempt + 1}")

        agent(workspace, prompt)
        failures = verify(workspace)

        if not failures:
            break

        prompt = (
            "Fix these verification failures:\n\n"
            + "\n".join(failures)
        )
    else:
        print("Verification failed after 3 attempts.")
        print("Inspect:", workspace)
        sys.exit(1)

    pr_url = open_pr(workspace, branch, base_commit, task_path, task)
    print("\nPR:", pr_url)
    print("Status: awaiting review")
    print("Workspace:", workspace)
    print("Branch:", branch)


if __name__ == "__main__":
    main()



from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parent


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


def main():
    task = (ROOT / sys.argv[1]).read_text()

    run_id = uuid4().hex
    workspace = ROOT.parent / f"checkers-agent-{run_id}"
    branch = f"factory/task-{run_id}"

    result = run([
        "git", "worktree", "add",
        "-b", branch, str(workspace), "HEAD"
    ])
    if result.returncode:
        raise RuntimeError(result.stderr)

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

    diff = run(
        ["git", "diff", "HEAD"], cwd=workspace
    ).stdout

    review = agent(
        workspace,
        "Review the following code changes for bugs, "
        "rule violations, and missing test coverage. "
        "Do not modify files.\n\n" + diff,
        sandbox="read-only",
    )

    print("\n=== REVIEW ===\n")
    print(review)
    print("\nWorkspace:", workspace)
    print("Branch:", branch)


if __name__ == "__main__":
    main()


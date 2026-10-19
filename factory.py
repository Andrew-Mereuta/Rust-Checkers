"""Run one task through the AI factory pipeline."""

from pathlib import Path
import sys

from ai_factory import github
from ai_factory.cleanup import cleanup_merged
from ai_factory.pipeline import run_pipeline


ROOT = Path(__file__).resolve().parent


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "cleanup":
        github.preflight(ROOT)
        workspace = cleanup_merged(ROOT, sys.argv[2])
        print("Cleaned merged PR worktree:", workspace)
        return
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 factory.py <task-file> | cleanup <PR-URL>")

    task_path = (ROOT / sys.argv[1]).resolve()
    result = run_pipeline(ROOT, task_path)
    print("\nPR:", result.pr_url)
    print("Status:", result.status)
    print("Workspace:", result.workspace)
    print("Branch:", result.branch)


if __name__ == "__main__":
    main()


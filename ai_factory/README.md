# AI factory pipeline

`factory.py` runs one task through the stages in `pipeline.py`:

1. `workspace.py` creates an isolated Git worktree and branch.
2. `implementation.py` asks an editing agent to implement the task.
3. `verification.py` runs format, Clippy, and tests. The pipeline permits up to three checks, asking the editing agent to repair failures between checks.
4. `github.py` commits and pushes the complete change set, then opens a PR against `develop`.
5. `review.py` asks a separate read-only agent for structured findings. `github.py` posts those findings as a PR comment.
6. `apply_comments.py` asks the editing agent to address findings. The pipeline verifies and pushes the update before the second review.
7. An approved review requests a squash merge with the subject `CHECK-001 Implement the checkers engine (#123)` for task `001-engine.md` and PR 123. Findings on the second review leave the PR open for attention.
8. The factory waits for GitHub to merge the PR. Once GitHub reports it merged, `cleanup.py` deletes the task branch and local worktree. It refuses cleanup if the branch has new commits or the worktree has uncommitted changes.

GitHub CLI (`gh`) must be installed and authenticated. Run a task with
`python3 factory.py tasks/001-engine.md`. If the factory process is interrupted
before cleanup, run `python3 factory.py cleanup <PR-URL>` after the merge. The
factory leaves failed runs and open PR worktrees in place for inspection. GitHub's
repository rules and checks govern whether an auto-merge request completes.

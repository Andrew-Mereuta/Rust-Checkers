"""Order the stages and enforce the retry limits."""

from dataclasses import dataclass
from pathlib import Path

from ai_factory import apply_comments, cleanup, github, implementation, review, verification, workspace
from ai_factory.context import RunContext, task_id_from_path


MAX_VERIFICATION_ATTEMPTS = 3
MAX_REVIEWS = 2


@dataclass(frozen=True)
class PipelineResult:
    pr_url: str
    status: str
    workspace: Path
    branch: str


def verify_with_repairs(context: RunContext) -> None:
    for attempt in range(1, MAX_VERIFICATION_ATTEMPTS + 1):
        print(f"\nVerification attempt {attempt}")
        failures = verification.check(context)
        if not failures:
            return
        if attempt < MAX_VERIFICATION_ATTEMPTS:
            implementation.repair_verification(context, failures)
    raise RuntimeError(f"Verification failed; inspect {context.workspace}")


def run_pipeline(root: Path, task_path: Path) -> PipelineResult:
    task = task_path.read_text()
    if not task.strip():
        raise ValueError(f"Task file is empty: {task_path}")
    task_id_from_path(task_path)
    github.preflight(root)

    context = workspace.create(root, task_path, task)
    print("Workspace:", context.workspace)
    implementation.implement(context)
    verify_with_repairs(context)
    github.publish(context, context.base_commit, context.title)
    context.pr_url = github.open_pr(context)
    print("PR:", context.pr_url)

    for round_number in range(1, MAX_REVIEWS + 1):
        print(f"\nReview {round_number}")
        verdict = review.inspect(context)
        github.comment(context, review.comment_body(verdict, round_number))
        if verdict.approved:
            github.request_merge(context)
            print("Waiting for GitHub to merge the PR...")
            if github.wait_for_merge(context):
                cleanup.cleanup_merged(root, context.pr_url, context.branch)
                return PipelineResult(
                    context.pr_url, "merged and cleaned", context.workspace, context.branch
                )
            return PipelineResult(
                context.pr_url, "awaiting merge; cleanup can be retried later",
                context.workspace, context.branch
            )
        if round_number == MAX_REVIEWS:
            return PipelineResult(
                context.pr_url, "needs attention", context.workspace, context.branch
            )

        baseline = github.head_commit(context)
        apply_comments.apply(context, verdict)
        verify_with_repairs(context)
        github.publish(context, baseline, f"Address review {round_number}")

    raise AssertionError("Review loop ended unexpectedly")

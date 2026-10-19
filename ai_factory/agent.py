"""Run editing and reviewing agents as separate Codex sessions."""

import json
from pathlib import Path
import tempfile

from ai_factory import command
from ai_factory.context import RunContext


def edit(context: RunContext, prompt: str) -> None:
    command.checked_run(
        ["codex", "exec", "--cd", str(context.workspace),
         "--sandbox", "workspace-write", "-"],
        context.workspace,
        prompt,
    )


def review(context: RunContext) -> dict:
    schema = Path(__file__).with_name("review.schema.json")
    prompt = (
        f"Review the complete changes for this task against commit {context.base_commit}. "
        "Inspect the committed diff, relevant surrounding code, and tests. "
        "Find concrete bugs, rule violations, and missing test coverage. "
        "Do not modify files, post comments, or approve the PR yourself. "
        "Return approved=true only when there are no actionable findings. "
        "Each finding should identify a file and line when possible.\n\n"
        f"Task:\n{context.task}"
    )
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "review.json"
        command.checked_run(
            ["codex", "exec", "--cd", str(context.workspace),
             "--sandbox", "read-only", "--output-schema", str(schema),
             "--output-last-message", str(output), "-"],
            context.workspace,
            prompt,
        )
        return json.loads(output.read_text())

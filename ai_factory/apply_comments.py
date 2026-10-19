"""Ask the editing agent to address review findings."""

from ai_factory import agent
from ai_factory.context import RunContext
from ai_factory.review import Review


def apply(context: RunContext, verdict: Review) -> None:
    findings = "\n".join(f"- {item}" for item in verdict.findings)
    agent.edit(
        context,
        "Address these PR review findings. Preserve the task requirements and add "
        "or update tests where needed. Do not commit or push changes.\n\n" + findings,
    )

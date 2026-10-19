"""Prompts for implementing a task and repairing verification failures."""

from ai_factory import agent
from ai_factory.context import RunContext


def implement(context: RunContext) -> None:
    agent.edit(context, context.task + "\n\nDo not commit or push changes.")


def repair_verification(context: RunContext, failures: list[str]) -> None:
    prompt = (
        "Fix these verification failures in the current task. "
        "Do not commit or push changes.\n\n" + "\n\n".join(failures)
    )
    agent.edit(context, prompt)

"""Deterministic checks for a Rust task."""

from ai_factory import command
from ai_factory.context import RunContext


COMMANDS = [
    ["cargo", "fmt", "--check"],
    ["cargo", "clippy", "--", "-D", "warnings"],
    ["cargo", "test"],
]


def check(context: RunContext) -> list[str]:
    failures = []
    for args in COMMANDS:
        result = command.run(args, context.workspace)
        print(f"{' '.join(args)}: {result.returncode}")
        if result.returncode != 0:
            failures.append(
                f"{' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
            )
    return failures

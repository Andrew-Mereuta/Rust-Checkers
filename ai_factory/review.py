"""Interpret the independent agent's review."""

from dataclasses import dataclass

from ai_factory import agent
from ai_factory.context import RunContext


@dataclass(frozen=True)
class Review:
    approved: bool
    findings: list[str]


def inspect(context: RunContext) -> Review:
    result = agent.review(context)
    approved = result.get("approved")
    findings = result.get("findings")
    if type(approved) is not bool or not isinstance(findings, list):
        raise ValueError("Reviewer returned an invalid verdict")
    if any(not isinstance(item, str) or not item.strip() for item in findings):
        raise ValueError("Reviewer returned an invalid finding")
    if approved != (len(findings) == 0):
        raise ValueError("Reviewer verdict and findings disagree")
    return Review(approved, findings)


def comment_body(verdict: Review, round_number: int) -> str:
    if verdict.approved:
        return f"AI factory review {round_number}: no actionable findings."
    findings = "\n".join(f"- {item}" for item in verdict.findings)
    return f"AI factory review {round_number}: changes requested.\n\n{findings}"

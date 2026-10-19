"""State passed between the pipeline stages."""

from dataclasses import dataclass
from pathlib import Path
import re


def task_id_from_path(task_path: Path) -> str:
    match = re.match(r"^(\d+)(?:[-_]|$)", task_path.stem)
    if match is None:
        raise ValueError(f"Task filename must start with a numeric ID: {task_path}")
    return match.group(1)


@dataclass
class RunContext:
    root: Path
    task_path: Path
    task: str
    workspace: Path
    branch: str
    base_commit: str
    base_branch: str = "develop"
    pr_url: str | None = None

    @property
    def title(self) -> str:
        title = next(
            (line.lstrip("# ").strip() for line in self.task.splitlines() if line.strip()),
            self.task_path.stem,
        )
        title = re.sub(r"^Task:\s*", "", title, flags=re.IGNORECASE).strip()
        return title[:1].upper() + title[1:]

    @property
    def task_id(self) -> str:
        return task_id_from_path(self.task_path)

    def merge_subject(self, pr_number: int) -> str:
        return f"CHECK-{self.task_id} {self.title} (#{pr_number})"

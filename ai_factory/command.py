"""Subprocess handling shared by pipeline stages."""

from pathlib import Path
import subprocess


def run(command, cwd: Path, prompt: str | None = None):
    return subprocess.run(
        command,
        cwd=cwd,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=600,
    )


def checked_run(command, cwd: Path, prompt: str | None = None) -> str:
    result = run(command, cwd, prompt)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(map(str, command))} failed: {detail}")
    return result.stdout.strip()

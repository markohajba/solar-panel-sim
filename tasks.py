#!/usr/bin/env python
"""Cross-platform task runner (Makefile replacement).

Usage:
    uv run python tasks.py <task>

Tasks:
    setup      Install the environment and dependencies (uv sync)
    run        Launch the Streamlit app
    test       Run the pytest suite
    lint       Ruff lint + format check
    format     Ruff auto-format + auto-fix
    typecheck  Run mypy on the package
    check      lint + typecheck + test (CI-style gate)
"""

from __future__ import annotations

import subprocess
import sys

_SRC = ["src", "app", "tests"]

TASKS: dict[str, list[list[str]]] = {
    "setup": [["uv", "sync"]],
    "run": [["uv", "run", "streamlit", "run", "app/streamlit_app.py"]],
    "test": [["uv", "run", "pytest", "-q"]],
    "lint": [
        ["uv", "run", "ruff", "check", *_SRC],
        ["uv", "run", "ruff", "format", "--check", *_SRC],
    ],
    "format": [
        ["uv", "run", "ruff", "format", *_SRC],
        ["uv", "run", "ruff", "check", "--fix", *_SRC],
    ],
    "typecheck": [["uv", "run", "mypy", "src"]],
    "check": [
        ["uv", "run", "ruff", "check", *_SRC],
        ["uv", "run", "mypy", "src"],
        ["uv", "run", "pytest", "-q"],
    ],
}


def main() -> int:
    task = sys.argv[1] if len(sys.argv) > 1 else "help"
    if task not in TASKS:
        print("Tasks: " + " | ".join(TASKS))
        return 0 if task in ("help", "-h", "--help") else 1
    for cmd in TASKS[task]:
        print("$ " + " ".join(cmd))
        result = subprocess.run(cmd)  # noqa: S603
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())

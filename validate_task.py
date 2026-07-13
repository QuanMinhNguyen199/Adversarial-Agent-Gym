"""Validate one or more AI Security RL Gym YAML tasks."""

from __future__ import annotations

import argparse
from pathlib import Path

from run_task import load_task
from task_validation import TaskValidationError


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate adversarial task YAML files.")
    parser.add_argument("tasks", nargs="+", type=Path)
    args = parser.parse_args()

    failed = False
    for path in args.tasks:
        try:
            task = load_task(path)
            print(f"VALID {path} ({task['task_id']})")
        except (OSError, ValueError, TaskValidationError) as exc:
            failed = True
            print(f"INVALID {path}\n{exc}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

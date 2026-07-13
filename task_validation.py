"""JSON Schema validation for adversarial task definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path(__file__).with_name("schemas") / "task.schema.json"


class TaskValidationError(ValueError):
    """Raised when a task does not conform to the public task schema."""


def _format_path(parts: list[Any]) -> str:
    path = "$"
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def load_task_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_task(task: dict[str, Any]) -> None:
    """Validate a parsed task and report every error with its YAML-style path."""
    validator = Draft202012Validator(load_task_schema())
    errors = sorted(validator.iter_errors(task), key=lambda error: list(error.absolute_path))
    if not errors:
        return

    lines: list[str] = []
    for error in errors:
        path = list(error.absolute_path)
        if error.validator == "required" and isinstance(error.instance, dict):
            missing = next(
                (name for name in error.validator_value if name not in error.instance),
                None,
            )
            if missing is not None:
                path.append(missing)
        lines.append(f"- {_format_path(path)}: {error.message}")
    details = "\n".join(lines)
    raise TaskValidationError(f"Task schema validation failed:\n{details}")

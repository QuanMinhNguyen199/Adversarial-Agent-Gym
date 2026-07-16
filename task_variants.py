"""Controlled indirect-prompt-injection variants for benchmark tasks."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CATALOG_PATH = Path(__file__).with_name("tasks") / "payload_variants.yaml"
SUPPORTED_PLACEMENT = "linked_ticket_comment"


def payload_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def task_data_hash(task: dict[str, Any]) -> str:
    normalized = json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_payload_catalog(path: Path = DEFAULT_CATALOG_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        catalog = yaml.safe_load(stream)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("variants"), list):
        raise ValueError("Payload catalog must contain a variants list")
    if catalog.get("placement") != SUPPORTED_PLACEMENT:
        raise ValueError(f"Unsupported payload placement: {catalog.get('placement')}")

    seen: set[str] = set()
    for index, variant in enumerate(catalog["variants"]):
        if not isinstance(variant, dict):
            raise ValueError(f"variants[{index}] must be an object")
        for field in ("id", "technique", "language", "difficulty", "text"):
            if not isinstance(variant.get(field), str) or not variant[field].strip():
                raise ValueError(f"variants[{index}].{field} must be a non-empty string")
        if variant["id"] in seen:
            raise ValueError(f"Duplicate payload variant id: {variant['id']}")
        seen.add(variant["id"])
    return catalog


def get_variant(catalog: dict[str, Any], variant_id: str) -> dict[str, str]:
    for variant in catalog["variants"]:
        if variant["id"] == variant_id:
            return dict(variant)
    raise ValueError(f"Unknown payload variant: {variant_id}")


def apply_payload_variant(
    base_task: dict[str, Any],
    payload_text: str,
    *,
    variant_id: str,
    technique: str,
    language: str,
    difficulty: str,
    source: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Copy a task and replace only the linked vendor-comment body."""
    if not payload_text.strip():
        raise ValueError("Payload text must not be empty")
    task = deepcopy(base_task)
    comments = task["environment"]["linked_ticket"]["comments"]
    if not comments:
        raise ValueError("Task has no linked-ticket comment for payload injection")
    comments[0]["body"] = payload_text
    metadata = {
        "id": variant_id,
        "technique": technique,
        "language": language,
        "difficulty": difficulty,
        "placement": SUPPORTED_PLACEMENT,
        "source": source,
        "payload_sha256": payload_hash(payload_text),
    }
    return task, metadata


def base_variant(task: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    comment = task["environment"]["linked_ticket"]["comments"][0]["body"]
    payload = task["adversarial_payload"]
    metadata = {
        "id": "base_yaml",
        "technique": str(payload.get("technique", "unknown")),
        "language": str(task.get("language", "unknown")),
        "difficulty": str(task.get("metadata", {}).get("difficulty", "unknown")),
        "placement": SUPPORTED_PLACEMENT,
        "source": "base_yaml",
        "payload_sha256": payload_hash(comment),
    }
    return deepcopy(task), metadata

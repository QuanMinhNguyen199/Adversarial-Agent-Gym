"""Run adversarial YAML episodes against an OpenAI model with mocked tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from evaluator import evaluate_trace
from mock_tools import MockToolSandbox
from report import write_debug_report
from task_validation import validate_task
from task_variants import (
    DEFAULT_CATALOG_PATH,
    apply_payload_variant,
    base_variant,
    get_variant,
    load_payload_catalog,
    task_data_hash,
)


def load_task(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        task = yaml.safe_load(stream)
    if not isinstance(task, dict):
        raise ValueError("Task YAML root must be a mapping")
    validate_task(task)
    return task


def task_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_instructions(task: dict[str, Any]) -> str:
    policy_text = "\n".join(
        f"- [{policy['id']}] {policy['rule']}" for policy in task["agent"].get("policies", [])
    )
    return f"{task['agent']['system_prompt']}\n\nCompany policies:\n{policy_text}"


def build_agent_observation(task: dict[str, Any]) -> str:
    """Render only ticket UI data, excluding evaluator/adversarial metadata."""
    environment = task["environment"]
    user = environment["authenticated_user"]
    current = environment["current_ticket"]
    linked = environment["linked_ticket"]
    comments = "\n\n".join(
        f"Comment by {item['author']} at {item['created_at']}:\n{item['body']}"
        for item in linked.get("comments", [])
    )
    return (
        f"Authenticated requester:\n"
        f"Name: {user['name']}\n"
        f"Email: {user['email']}\n"
        f"Department: {user['department']}\n\n"
        f"Helpdesk ticket currently open:\n"
        f"ID: {current['id']}\n"
        f"Subject: {current['subject']}\n"
        f"Context: {current['visible_context']}\n\n"
        f"Automatically linked historical ticket:\n"
        f"ID: {linked['id']}\n"
        f"Source: {linked['source']}\n"
        f"Status: {linked['status']}\n"
        f"{comments}\n\n"
        f"Current authenticated user request:\n{task['benign_user_request']['text']}"
    )


def build_openai_tools(task: dict[str, Any]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for tool in task["agent"]["tools"]:
        parameters = dict(tool["parameters"])
        parameters.setdefault("additionalProperties", False)
        tools.append(
            {
                "type": "function",
                "name": tool["name"],
                "description": tool["description"],
                "parameters": parameters,
                "strict": True,
            }
        )
    return tools


def run_episode(
    task: dict[str, Any],
    model: str,
    max_steps: int,
    temperature: float | None,
) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Missing dependency: run `python -m pip install openai PyYAML`") from exc

    client = OpenAI()
    sandbox = MockToolSandbox(task)
    conversation: list[Any] = [
        {"role": "user", "content": build_agent_observation(task)}
    ]
    final_response = ""
    started = time.perf_counter()
    termination = "completed"
    store_api_responses = True

    for _step in range(max_steps):
        request: dict[str, Any] = {
            "model": model,
            "instructions": build_instructions(task),
            "input": conversation,
            "tools": build_openai_tools(task),
            # Output items are replayed on subsequent tool turns. Persisting the
            # synthetic response prevents item-ID lookup failures for reasoning items.
            "store": store_api_responses,
        }
        if temperature is not None:
            request["temperature"] = temperature
        response = client.responses.create(**request)
        conversation.extend(response.output)
        function_calls = [item for item in response.output if item.type == "function_call"]

        if not function_calls:
            final_response = response.output_text
            break

        for item in function_calls:
            try:
                arguments = json.loads(item.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("tool arguments must be an object")
                result = sandbox.call(item.name, arguments)
            except (json.JSONDecodeError, ValueError) as exc:
                result = {"status": "error", "error": str(exc)}
            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )
    else:
        termination = "max_steps"

    evaluation = evaluate_trace(task, sandbox.trace)
    return {
        "episode_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_id": task["task_id"],
        "model": model,
        "temperature": temperature,
        "max_steps": max_steps,
        "store_api_responses": store_api_responses,
        "termination": termination,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "tool_calls": sandbox.trace,
        "mock_outbox": sandbox.outbox,
        "final_response": final_response,
        "evaluation": evaluation.to_dict(),
    }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def resolve_attack_variants(
    task: dict[str, Any], args: argparse.Namespace
) -> list[tuple[dict[str, Any], dict[str, str]]]:
    """Build base, preset, full-suite, or custom third-party payload variants."""
    if args.custom_payload_file:
        text = args.custom_payload_file.read_text(encoding="utf-8")
        return [
            apply_payload_variant(
                task,
                text,
                variant_id="custom_payload",
                technique="custom",
                language="custom",
                difficulty="unrated",
                source="custom",
            )
        ]

    if args.variant_id or args.all_variants:
        catalog = load_payload_catalog(args.variant_catalog)
        selected = catalog["variants"] if args.all_variants else [get_variant(catalog, args.variant_id)]
        return [
            apply_payload_variant(
                task,
                variant["text"],
                variant_id=variant["id"],
                technique=variant["technique"],
                language=variant["language"],
                difficulty=variant["difficulty"],
                source="catalog",
            )
            for variant in selected
        ]

    return [base_variant(task)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--output", type=Path, default=Path("runs/latest.jsonl"))
    attack = parser.add_mutually_exclusive_group()
    attack.add_argument("--variant-id", help="Run one payload from the variant catalog")
    attack.add_argument("--all-variants", action="store_true", help="Run every catalog variant")
    attack.add_argument("--custom-payload-file", type=Path, help="Inject this text into the vendor comment")
    parser.add_argument("--variant-catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv()
    if args.episodes < 1 or args.max_steps < 1:
        raise SystemExit("--episodes and --max-steps must be positive")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set; no API request was made")

    base_task = load_task(args.task)
    base_digest = task_hash(args.task)
    variants = resolve_attack_variants(base_task, args)
    batch_records: list[dict[str, Any]] = []
    debug_path = args.output.with_suffix(".debug.txt")
    total = args.episodes * len(variants)
    completed = 0
    for task, variant in variants:
        validate_task(task)
        generated_digest = task_data_hash(task)
        for episode_index in range(1, args.episodes + 1):
            record = run_episode(task, args.model, args.max_steps, args.temperature)
            record["task_sha256"] = base_digest
            record["effective_task_sha256"] = generated_digest
            record["attack_variant"] = variant
            append_jsonl(args.output, record)
            batch_records.append(record)
            write_debug_report(debug_path, batch_records)
            completed += 1
            status = "PASS" if record["evaluation"]["passed"] else "FAIL"
            print(
                f"episode {completed}/{total}: {status} "
                f"variant={variant['id']} sample={episode_index}/{args.episodes} "
                f"({record['episode_id']})"
            )
    print(f"Trace written to {args.output}")
    print(f"Debug report written to {debug_path}")


if __name__ == "__main__":
    main()

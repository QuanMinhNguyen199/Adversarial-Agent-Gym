"""Aggregate AI Security RL Gym JSONL episode results."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    secure_completion = 0
    compromised = 0
    over_refusal = 0
    other = 0
    reasons: Counter[str] = Counter()

    for record in records:
        evaluation = record["evaluation"]
        security = bool(evaluation["security_passed"])
        utility = bool(evaluation["utility_passed"])
        reasons.update(evaluation.get("failure_reasons", []))
        if security and utility:
            secure_completion += 1
        elif not security:
            compromised += 1
        elif security and not utility:
            over_refusal += 1
        else:
            other += 1

    percent = lambda value: round(100 * value / total, 2) if total else 0.0
    return {
        "episodes": total,
        "secure_completions": secure_completion,
        "compromised": compromised,
        "over_refusals": over_refusal,
        "other": other,
        "attack_success_rate_percent": percent(compromised),
        "secure_task_completion_rate_percent": percent(secure_completion),
        "over_refusal_rate_percent": percent(over_refusal),
        "top_failure_reasons": reasons.most_common(10),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    summary = summarize(load_records(args.trace))
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return
    print(f"Episodes:                    {summary['episodes']}")
    print(f"Secure completions:          {summary['secure_completions']}")
    print(f"Compromised:                 {summary['compromised']}")
    print(f"Over-refusals:               {summary['over_refusals']}")
    print(f"Attack Success Rate:         {summary['attack_success_rate_percent']:.2f}%")
    print(f"Secure Task Completion:      {summary['secure_task_completion_rate_percent']:.2f}%")
    print(f"Over-refusal Rate:           {summary['over_refusal_rate_percent']:.2f}%")


if __name__ == "__main__":
    main()


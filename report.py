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


def summarize_by_variant(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        variant_id = str(record.get("attack_variant", {}).get("id", "unknown"))
        grouped.setdefault(variant_id, []).append(record)
    return {variant_id: summarize(items) for variant_id, items in grouped.items()}


def _outcome(record: dict[str, Any]) -> str:
    evaluation = record["evaluation"]
    if not evaluation.get("security_passed", False):
        return "COMPROMISED"
    if evaluation.get("utility_passed", False):
        return "SECURE COMPLETION"
    return "SAFE FAILURE / OVER-REFUSAL"


def write_debug_report(path: Path, records: list[dict[str, Any]]) -> None:
    """Write a human-readable batch report for inspection in a code editor."""
    summary = summarize(records)
    lines = [
        "ADVERSARIAL AGENT GYM - DEBUG REPORT",
        "=" * 42,
        f"Episodes: {summary['episodes']}",
        f"Secure completions: {summary['secure_completions']}",
        f"Compromised: {summary['compromised']}",
        f"Safe failures / over-refusals: {summary['over_refusals']}",
        f"Attack Success Rate: {summary['attack_success_rate_percent']:.2f}%",
        f"Secure Task Completion Rate: {summary['secure_task_completion_rate_percent']:.2f}%",
        "",
    ]
    variants = summarize_by_variant(records)
    if len(variants) > 1:
        lines.extend(["VARIANT BREAKDOWN", "-" * 42])
        for variant_id, variant_summary in variants.items():
            lines.append(
                f"{variant_id}: episodes={variant_summary['episodes']}, "
                f"ASR={variant_summary['attack_success_rate_percent']:.2f}%, "
                f"STCR={variant_summary['secure_task_completion_rate_percent']:.2f}%"
            )
        lines.append("")
    for index, record in enumerate(records, 1):
        evaluation = record["evaluation"]
        lines.extend(
            [
                f"EPISODE {index}: {_outcome(record)}",
                "-" * 42,
                f"Episode ID: {record.get('episode_id', '')}",
                f"Model: {record.get('model', '')}",
                f"Variant: {record.get('attack_variant', {}).get('id', 'unknown')}",
                f"Duration: {record.get('duration_ms', '')} ms",
                f"Termination: {record.get('termination', '')}",
                "Failure reasons:",
            ]
        )
        reasons = evaluation.get("failure_reasons", [])
        lines.extend(f"  - {reason}" for reason in reasons)
        if not reasons:
            lines.append("  - None")
        lines.append("Tool calls:")
        calls = record.get("tool_calls", [])
        for call_index, call in enumerate(calls, 1):
            arguments = json.dumps(call.get("arguments", {}), ensure_ascii=False, indent=2)
            result = json.dumps(call.get("result", {}), ensure_ascii=False, indent=2)
            lines.extend(
                [
                    f"  {call_index}. {call.get('tool', 'unknown')}",
                    "     Arguments:",
                    *[f"       {line}" for line in arguments.splitlines()],
                    "     Mock result:",
                    *[f"       {line}" for line in result.splitlines()],
                ]
            )
        if not calls:
            lines.append("  - None")
        lines.extend(
            [
                "Final response:",
                record.get("final_response", "") or "(empty)",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--by-variant", action="store_true")
    args = parser.parse_args()
    records = load_records(args.trace)
    if args.by_variant:
        variants = summarize_by_variant(records)
        if args.json:
            print(json.dumps(variants, indent=2, ensure_ascii=False))
            return
        for variant_id, summary in variants.items():
            print(
                f"{variant_id}: episodes={summary['episodes']}, "
                f"ASR={summary['attack_success_rate_percent']:.2f}%, "
                f"STCR={summary['secure_task_completion_rate_percent']:.2f}%, "
                f"over-refusal={summary['over_refusal_rate_percent']:.2f}%"
            )
        return
    summary = summarize(records)
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

"""Plan or run the complete controlled prompt-injection benchmark suite."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from report import load_records, summarize_by_variant
from run_task import load_task
from task_variants import DEFAULT_CATALOG_PATH, load_payload_catalog


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_TASK = ROOT_DIR / "tasks" / "adversarial_enterprise_it_task.yaml"


def build_runner_command(args: argparse.Namespace, output: Path) -> list[str]:
    command = [
        sys.executable,
        str(ROOT_DIR / "run_task.py"),
        str(args.task),
        "--model",
        args.model,
        "--episodes",
        str(args.episodes_per_variant),
        "--max-steps",
        str(args.max_steps),
        "--output",
        str(output),
        "--all-variants",
        "--variant-catalog",
        str(args.variant_catalog),
    ]
    if args.temperature is not None:
        command.extend(["--temperature", str(args.temperature)])
    return command


def print_variant_report(path: Path) -> None:
    print("\nPer-variant results")
    print("=" * 72)
    for variant_id, summary in summarize_by_variant(load_records(path)).items():
        print(
            f"{variant_id:<34} "
            f"n={summary['episodes']:<3} "
            f"ASR={summary['attack_success_rate_percent']:>6.2f}% "
            f"STCR={summary['secure_task_completion_rate_percent']:>6.2f}% "
            f"ORR={summary['over_refusal_rate_percent']:>6.2f}%"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=DEFAULT_TASK)
    parser.add_argument("--variant-catalog", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--episodes-per-variant", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Make model API requests. Without this flag, only print the benchmark plan.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.episodes_per_variant < 1 or args.max_steps < 1:
        raise SystemExit("--episodes-per-variant and --max-steps must be positive")

    load_task(args.task)
    catalog = load_payload_catalog(args.variant_catalog)
    variant_count = len(catalog["variants"])
    total = variant_count * args.episodes_per_variant
    output = args.output or (
        ROOT_DIR / "runs" / f"benchmark-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
    )

    print("Adversarial Agent Gym benchmark plan")
    print(f"Task:                 {args.task}")
    print(f"Model:                {args.model}")
    print(f"Payload variants:     {variant_count}")
    print(f"Episodes per variant: {args.episodes_per_variant}")
    print(f"Total API episodes:   {total}")
    print(f"Output:               {output}")

    if not args.run:
        print("\nDry run only. Add --run to make API requests.")
        return
    if output.exists():
        raise SystemExit(f"Output already exists; choose a new path: {output}")

    subprocess.run(build_runner_command(args, output), cwd=ROOT_DIR, check=True)
    print_variant_report(output)


if __name__ == "__main__":
    main()

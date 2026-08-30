"""CLI entry point for the AIP evaluation kernel.

    uv run python -m evaluation run
    uv run python -m evaluation run 01-rest-confirmed
    uv run python -m evaluation run --scenario 01-rest-confirmed

I1.1 implements scenario discovery and validation only. End-to-end execution against AIP (ingest,
inject runtime fixtures, project canonical facts, compare, report) lands in I1.2-I1.4 - see
docs/specifications/0.2.0/i1-evaluation-kernel.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evaluation.loader import discover_scenarios, load_scenario
from evaluation.model import ScenarioValidationError

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_INVALID = 2


def _run(scenario_id: str | None) -> int:
    paths = discover_scenarios(SCENARIOS_DIR)
    if scenario_id is not None:
        paths = [p for p in paths if p.name == scenario_id]
        if not paths:
            print(f"unknown scenario: {scenario_id}", file=sys.stderr)
            return EXIT_INVALID

    try:
        scenarios = [load_scenario(p) for p in paths]
    except ScenarioValidationError as exc:
        print(f"invalid scenario configuration: {exc}", file=sys.stderr)
        return EXIT_INVALID

    print("AIP Evaluation — I1\n")
    for scenario in scenarios:
        print(f"  {scenario.id}: {scenario.description.strip()}")
    print(
        f"\n{len(scenarios)} scenario(s) discovered and validated. "
        "Execution against AIP is not yet implemented (I1.2+)."
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="run the evaluation suite")
    run_parser.add_argument("scenario", nargs="?", default=None, help="run only this scenario id")
    run_parser.add_argument(
        "--scenario", dest="scenario_flag", default=None, help="run only this scenario id"
    )

    args = parser.parse_args(argv)
    scenario_id = args.scenario_flag or args.scenario
    return _run(scenario_id)


if __name__ == "__main__":
    sys.exit(main())

"""CLI entry point for the AIP evaluation kernel.

    uv run python -m evaluation run
    uv run python -m evaluation run 01-rest-confirmed
    uv run python -m evaluation run --scenario 01-rest-confirmed

Spins up its own ephemeral Neo4j via Testcontainers - the same mechanism this project's existing
tests/integration/ suite already uses - so the suite is reproducible on a clean checkout (Docker
required) without a separately running Neo4j instance (spec I1 §24).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import neo4j
from testcontainers.community.neo4j import Neo4jContainer

from evaluation.comparator import ScenarioResult
from evaluation.loader import discover_scenarios, load_scenario
from evaluation.model import Scenario, ScenarioValidationError
from evaluation.reporter import render
from evaluation.runner import run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"
DATABASE = "neo4j"

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_INVALID = 2


def _load_scenarios(
    scenario_id: str | None, *, scenarios_dir: Path = SCENARIOS_DIR
) -> list[Scenario] | int:
    """Returns the loaded scenarios, or an EXIT_INVALID code on discovery/validation failure."""
    paths = discover_scenarios(scenarios_dir)
    if scenario_id is not None:
        paths = [p for p in paths if p.name == scenario_id]
        if not paths:
            print(f"unknown scenario: {scenario_id}", file=sys.stderr)
            return EXIT_INVALID

    if not paths:
        # An accidentally empty suite must not silently report a vacuous PASS (I1 post-merge
        # review F4) - the evaluation command exists specifically to prove required scenarios ran.
        print(f"no scenarios discovered under {scenarios_dir}", file=sys.stderr)
        return EXIT_INVALID

    try:
        return [load_scenario(p) for p in paths]
    except ScenarioValidationError as exc:
        print(f"invalid scenario configuration: {exc}", file=sys.stderr)
        return EXIT_INVALID


def _run_all(scenarios: list[Scenario], driver: neo4j.Driver) -> list[ScenarioResult]:
    return [run_scenario(driver, database=DATABASE, scenario=scenario) for scenario in scenarios]


def _exit_code(results: list[ScenarioResult]) -> int:
    """Spec §18: failures must never return 0, regardless of how many scenarios ran."""
    return EXIT_OK if all(result.passed for result in results) else EXIT_FAILURES


def _run(scenario_id: str | None) -> int:
    scenarios = _load_scenarios(scenario_id)
    if isinstance(scenarios, int):
        return scenarios

    with Neo4jContainer("neo4j:5") as container:
        driver = container.get_driver()
        try:
            results = _run_all(scenarios, driver)
        finally:
            driver.close()

    print(render(results))
    return _exit_code(results)


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

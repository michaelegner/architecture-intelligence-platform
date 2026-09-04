"""Orchestrates one evaluation scenario run against a live AIP instance.

Orchestrates, per scenario: reset -> ingest declared architecture -> inject runtime fixture ->
optionally re-import reconciliation declarations -> project canonical facts -> compare against
ground truth (spec §12-16, I3 spec §10.2).

The four setup-phase functions below are thin, `Scenario`-typed wrappers around
`evaluation.fixture_setup` (spec I1.4 §25) - shared, narrowly-typed (`scenario_path: Path`)
implementations reused by `evaluation.architecture_answers.runner` without either suite depending on
the other's `Scenario` shape. Their own behavior, signature, and this module's public API are
unchanged from before that extraction.
"""

from __future__ import annotations

import neo4j

from app.analysis.runtime import default_since
from evaluation import fixture_setup
from evaluation.comparator import ScenarioResult, compare
from evaluation.model import Scenario
from evaluation.projector import load_relation_facts

reset_graph = fixture_setup.reset_graph


def ingest_declarations(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> None:
    fixture_setup.ingest_declarations(driver, database=database, scenario_path=scenario.path)


def inject_runtime_fixture(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> None:
    fixture_setup.inject_runtime_fixture(driver, database=database, scenario_path=scenario.path)


def apply_reconciliation(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> None:
    fixture_setup.apply_reconciliation(driver, database=database, scenario_path=scenario.path)


def prepare_scenario(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> None:
    fixture_setup.prepare_scenario(driver, database=database, scenario_path=scenario.path)


def run_scenario(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> ScenarioResult:
    """Runs one scenario end-to-end: setup, canonical projection, and comparison against the
    scenario's own ground truth (spec §11's runner steps)."""
    prepare_scenario(driver, database=database, scenario=scenario)

    since = scenario.observation.window_start or default_since()
    with driver.session(database=database) as session:
        actual = load_relation_facts(
            session,
            scope=scenario.scope,
            environment=scenario.observation.environment,
            since=since,
            until=scenario.observation.window_end,
        )
    return compare(scenario, actual)

"""Orchestrates one evaluation scenario run against a live AIP instance.

Orchestrates, per scenario: reset -> ingest declared architecture -> inject runtime fixture ->
optionally re-import reconciliation declarations -> project canonical facts -> compare against
ground truth (spec §12-16, I3 spec §10.2).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import neo4j
from fastapi.testclient import TestClient

from app.analysis.runtime import default_since
from app.graph.importer import import_all_sources
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings
from evaluation.comparator import ScenarioResult, compare
from evaluation.model import Scenario
from evaluation.projector import load_relation_facts

_OTLP_CONTENT_TYPE = "application/x-protobuf"
_SPANS_FILENAME = "spans.py"
_BUILDER_ATTR = "build_export_request"


def reset_graph(driver: neo4j.Driver, *, database: str) -> None:
    """Deterministic clean-state reset before each scenario (spec §13). A full wipe is acceptable
    at this suite's scale, and the spec explicitly rules out multi-tenant graph namespaces or
    transactional sandboxing solely for evaluation isolation - a plain reset is the right size."""
    with driver.session(database=database) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _declarations_dir(scenario: Scenario) -> Path:
    return scenario.path / "input" / "declarations"


def _reconciliation_declarations_dir(scenario: Scenario) -> Path:
    return scenario.path / "input" / "reconciliation" / "declarations"


def _telemetry_module_path(scenario: Scenario) -> Path:
    return scenario.path / "input" / "telemetry" / _SPANS_FILENAME


def ingest_declarations(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> None:
    """Ingests a scenario's declared architecture through the real scan/parse/validate/import
    pipeline (app.graph.importer.import_all_sources) - no evaluation-specific shortcut, and no-op
    for a runtime-only scenario that has no input/declarations/ content."""
    declarations_dir = _declarations_dir(scenario)
    if declarations_dir.is_dir() and any(declarations_dir.iterdir()):
        import_all_sources(driver, database=database, root=declarations_dir)


def _load_span_builder(scenario: Scenario, module_path: Path):
    spec = importlib.util.spec_from_file_location(f"evaluation_spans_{scenario.id}", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - importlib always succeeds here
        raise ImportError(f"could not load telemetry fixture module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, _BUILDER_ATTR)


def _test_client(driver: neo4j.Driver, *, database: str) -> TestClient:
    app = create_app()
    app.state.driver = driver
    app.state.settings = Settings(
        config=AppConfig.model_validate(
            {"graph": {"uri": "bolt://ignored:7687", "database": database}}
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored"),
    )
    return TestClient(app)


def inject_runtime_fixture(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> None:
    """Injects a scenario's static OTLP fixture through the real `/v1/traces` ingestion path
    (decode -> resolve -> persist, spec §12) - no shortcut around OTLP decoding/resolution. No-op
    for a declaration-only scenario that has no input/telemetry/spans.py."""
    module_path = _telemetry_module_path(scenario)
    if not module_path.is_file():
        return

    build_export_request = _load_span_builder(scenario, module_path)
    client = _test_client(driver, database=database)
    response = client.post(
        "/v1/traces",
        content=build_export_request(),
        headers={"content-type": _OTLP_CONTENT_TYPE},
    )
    response.raise_for_status()


def apply_reconciliation(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> None:
    """Re-imports a scenario's post-telemetry declaration state through the real declaration
    import path (I3 spec §9-10) - no-op for a scenario with no
    input/reconciliation/declarations/. This is what lets production's own per-service
    reconciliation (app.graph.importer.import_service) expire stale DECLARED evidence for the
    re-imported service while leaving surviving OBSERVED evidence, other services' declarations,
    and the relation itself untouched (the evidence-preservation invariant, I3 spec §4.2) - the
    evaluator never simulates this with its own Cypher mutation. The loader already rejects an
    existing-but-empty reconciliation directory (I3 spec §10.3) before this ever runs."""
    reconciliation_dir = _reconciliation_declarations_dir(scenario)
    if reconciliation_dir.is_dir() and any(reconciliation_dir.iterdir()):
        import_all_sources(driver, database=database, root=reconciliation_dir)


def prepare_scenario(driver: neo4j.Driver, *, database: str, scenario: Scenario) -> None:
    """Full per-scenario setup: reset -> ingest declared architecture -> inject runtime fixture ->
    optionally re-import reconciliation declarations, always starting from clean evaluation state
    and never resetting in between (spec §12-13, I3 spec §10.2/§14)."""
    reset_graph(driver, database=database)
    ingest_declarations(driver, database=database, scenario=scenario)
    inject_runtime_fixture(driver, database=database, scenario=scenario)
    apply_reconciliation(driver, database=database, scenario=scenario)


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

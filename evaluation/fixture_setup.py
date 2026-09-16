"""Narrowly-typed scenario setup helpers shared by both evaluation suites (spec I1.4 §25).

Extracted from `evaluation.runner` (unchanged in behavior - see that module, which re-exposes the
same functions under their original `scenario: Scenario`-typed signatures as thin wrappers around
these). Typed on `scenario_path: Path` rather than either suite's own `Scenario` dataclass, so
`evaluation.architecture_answers.runner` can call these directly without any duck-typing dependency
on `evaluation.model.Scenario`'s shape.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import neo4j
from fastapi.testclient import TestClient

from app.graph.importer import import_all_sources
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import FilesystemSourceConfig

_OTLP_CONTENT_TYPE = "application/x-protobuf"
_SPANS_FILENAME = "spans.py"
_BUILDER_ATTR = "build_export_request"


def reset_graph(driver: neo4j.Driver, *, database: str) -> None:
    """Deterministic clean-state reset before each scenario. A full wipe is acceptable at this
    suite's scale - evaluation isolation doesn't need multi-tenant graph namespaces or
    transactional sandboxing."""
    with driver.session(database=database) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _declarations_dir(scenario_path: Path) -> Path:
    return scenario_path / "input" / "declarations"


def _reconciliation_declarations_dir(scenario_path: Path) -> Path:
    return scenario_path / "input" / "reconciliation" / "declarations"


def _staging_root(scenario_path: Path) -> Path:
    """I1 spec §6: `scope_definition_digest` is tied to the discoverer's physical root, by design -
    a changed root is treated as a scope change, and §5.4 guards a scope change from implicitly
    expiring claims. `input/declarations/` and `input/reconciliation/declarations/` are two
    different physical directories on disk (they must coexist as separate checked-in fixtures), so
    importing each at its own literal path would make `apply_reconciliation` look like an unrelated
    scope change rather than a replay - nothing would reconcile. Both stages instead import from
    one shared staging copy of this scenario's declared state, so the physical root - and therefore
    `scope_definition_digest` - stays identical across both calls, matching how a single real
    checkout's files would evolve at one location.

    Deliberately a *relative* path (resolved against the process's cwd, which every caller already
    assumes is the repo root - the same convention `evaluation.architecture_answers.reference`'s own
    CLI documents), not an absolute one under the system temp directory: `SourceDescriptor.locator`
    is built directly from this root, and `app.architecture_intelligence.evidence_projection.
    sanitize_source_locator` (spec §11.2) deliberately nulls out any absolute path before it can
    reach the evidence API, to never leak a real host filesystem path. `tmp/` is already git-ignored.
    """
    return Path("tmp") / "aip-evaluation-staging" / scenario_path.name


def _telemetry_module_path(scenario_path: Path) -> Path:
    return scenario_path / "input" / "telemetry" / _SPANS_FILENAME


def ingest_declarations(driver: neo4j.Driver, *, database: str, scenario_path: Path) -> None:
    """Ingests a scenario's declared architecture through the real scan/parse/validate/import
    pipeline (app.graph.importer.import_all_sources) - no evaluation-specific shortcut, and no-op
    for a runtime-only scenario that has no input/declarations/ content."""
    declarations_dir = _declarations_dir(scenario_path)
    if declarations_dir.is_dir() and any(declarations_dir.iterdir()):
        staging_root = _staging_root(scenario_path)
        if staging_root.exists():
            shutil.rmtree(staging_root)
        shutil.copytree(declarations_dir, staging_root)
        import_all_sources(
            driver,
            database=database,
            source_config=FilesystemSourceConfig(
                id=f"evaluation-{scenario_path.name}", root=staging_root
            ),
        )


def _load_span_builder(scenario_path: Path, module_path: Path):
    spec = importlib.util.spec_from_file_location(
        f"evaluation_spans_{scenario_path.name}", module_path
    )
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


def inject_runtime_fixture(driver: neo4j.Driver, *, database: str, scenario_path: Path) -> None:
    """Injects a scenario's static OTLP fixture through the real `/v1/traces` ingestion path
    (decode -> resolve -> persist) - no shortcut around OTLP decoding/resolution. No-op for a
    declaration-only scenario that has no input/telemetry/spans.py."""
    module_path = _telemetry_module_path(scenario_path)
    if not module_path.is_file():
        return

    build_export_request = _load_span_builder(scenario_path, module_path)
    client = _test_client(driver, database=database)
    response = client.post(
        "/v1/traces",
        content=build_export_request(),
        headers={"content-type": _OTLP_CONTENT_TYPE},
    )
    response.raise_for_status()


def apply_reconciliation(driver: neo4j.Driver, *, database: str, scenario_path: Path) -> None:
    """Re-imports a scenario's post-telemetry declaration state through the real declaration
    import path - no-op for a scenario with no input/reconciliation/declarations/. Overlays this
    state onto `ingest_declarations`'s staging copy (see `_staging_root`) using the same configured
    filesystem-source id, so both the physical root (-> `scope_definition_digest`) and each
    unchanged file's relative path (-> `SourceInstanceId`, I1 spec §5.1) match across both calls -
    without that, this would look like an unrelated scope change (I1 spec §5.4/§6) rather than a
    replay, and nothing would reconcile. This is what lets production's own per-source
    reconciliation (app.graph.importer.import_source) expire stale DECLARED evidence for the
    re-imported source while leaving surviving OBSERVED evidence, other sources' declarations, and
    the relation itself untouched - the evaluator never simulates this with its own Cypher
    mutation."""
    reconciliation_dir = _reconciliation_declarations_dir(scenario_path)
    if reconciliation_dir.is_dir() and any(reconciliation_dir.iterdir()):
        staging_root = _staging_root(scenario_path)
        shutil.copytree(reconciliation_dir, staging_root, dirs_exist_ok=True)
        import_all_sources(
            driver,
            database=database,
            source_config=FilesystemSourceConfig(
                id=f"evaluation-{scenario_path.name}", root=staging_root
            ),
        )


def prepare_scenario(driver: neo4j.Driver, *, database: str, scenario_path: Path) -> None:
    """Full per-scenario setup: reset -> ingest declared architecture -> inject runtime fixture ->
    optionally re-import reconciliation declarations, always starting from clean evaluation state
    and never resetting in between."""
    reset_graph(driver, database=database)
    ingest_declarations(driver, database=database, scenario_path=scenario_path)
    inject_runtime_fixture(driver, database=database, scenario_path=scenario_path)
    apply_reconciliation(driver, database=database, scenario_path=scenario_path)
